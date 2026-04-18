"""Volcengine (火山引擎) bigmodel ASR client — 逐字时间戳。

Uses TOS object storage for audio upload and the cheaper bigmodel API
(¥0.8/hour) instead of the legacy vc/submit binary upload (¥6.5/hour).

Output format (unchanged from previous version):
    [{text, start_time, end_time, words: [{text, start_time, end_time, probability}]}]
"""

import logging
import os
import subprocess
import tempfile
import time
import uuid
from typing import Any

import requests
import tos

logger = logging.getLogger(__name__)

_MAX_WAIT_SECONDS = 600
_POLL_INTERVAL_SECONDS = 10

_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"


class VolcengineASRClient:
    """Cloud ASR client using Volcengine bigmodel API via TOS pre-signed URLs.

    Flow:
        1. Extract audio from video if needed (FFmpeg)
        2. Upload audio to TOS, get pre-signed URL
        3. Submit pre-signed URL to bigmodel API
        4. Poll bigmodel query API until complete
        5. Parse utterances with character-level timestamps (ms → seconds)
        6. Clean up TOS object (best-effort)
    """

    def __init__(
        self,
        api_key: str | None = None,
        tos_ak: str | None = None,
        tos_sk: str | None = None,
        tos_bucket: str | None = None,
        tos_region: str | None = None,
        tos_endpoint: str | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("VOLCENGINE_ASR_API_KEY", "")
        self._tos_ak = tos_ak or os.getenv("TOS_AK", "")
        self._tos_sk = tos_sk or os.getenv("TOS_SK", "")
        self._tos_bucket = tos_bucket or os.getenv("TOS_BUCKET", "mp3-srt")
        self._tos_region = tos_region or os.getenv("TOS_REGION", "cn-beijing")
        self._tos_endpoint = tos_endpoint or os.getenv("TOS_ENDPOINT", "tos-cn-beijing.volces.com")
        self._tos_client: tos.TosClientV2 | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "X-Api-Resource-Id": "volc.seedasr.auc",
            "Content-Type": "application/json",
        }

    @property
    def tos_client(self) -> tos.TosClientV2:
        if self._tos_client is None:
            self._tos_client = tos.TosClientV2(
                ak=self._tos_ak,
                sk=self._tos_sk,
                endpoint=self._tos_endpoint,
                region=self._tos_region,
            )
        return self._tos_client

    @property
    def tos_bucket(self) -> str:
        return self._tos_bucket

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_path: str,
    ) -> list[dict[str, Any]]:
        """Transcribe audio file, return segments with word-level timestamps."""
        if not self._api_key:
            logger.error("Volcengine ASR credentials not configured (api_key)")
            return []

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        logger.info("Submitting to Volcengine bigmodel: %s (%.1f MB)", audio_path, file_size_mb)

        # Step 1: extract audio from video if needed
        submit_path = self._maybe_extract_audio(audio_path)
        tos_key: str | None = None
        try:
            # Step 2: upload to TOS and get presigned URL
            presigned_url, tos_key = self._upload_to_tos(submit_path)
            if not presigned_url:
                return []

            # Step 3: submit to bigmodel
            request_id = self._submit(presigned_url)
            if not request_id:
                return []

            logger.info("Volcengine bigmodel task submitted: %s", request_id)

            # Step 4: poll for result
            result = self._wait_for_result(request_id)
            if result is None:
                return []

            # Step 5: parse
            return self._parse_result(result)
        finally:
            # Clean up local temp audio
            if submit_path != audio_path and os.path.exists(submit_path):
                os.unlink(submit_path)
            # Clean up TOS object
            if tos_key:
                self._cleanup_tos(tos_key)

    def health_check(self) -> bool:
        """Verify credentials are configured."""
        return bool(self._api_key)

    # ------------------------------------------------------------------
    # Audio extraction (unchanged)
    # ------------------------------------------------------------------

    @staticmethod
    def _maybe_extract_audio(audio_path: str) -> str:
        """Extract audio from video if needed; return path to audio-only file."""
        ext = os.path.splitext(audio_path)[1].lower()
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"}
        if ext not in video_exts:
            return audio_path

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        logger.info("Extracting audio from video to: %s", tmp.name)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", audio_path,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                tmp.name,
            ],
            capture_output=True,
            timeout=300,
            check=True,
        )
        extracted_mb = os.path.getsize(tmp.name) / 1024 / 1024
        logger.info("Audio extracted: %.1f MB", extracted_mb)
        return tmp.name

    # ------------------------------------------------------------------
    # TOS upload
    # ------------------------------------------------------------------

    def _upload_to_tos(self, audio_path: str) -> tuple[str | None, str | None]:
        """Upload audio to TOS, return (presigned_url, tos_key).

        Returns (None, None) on failure.
        """
        tos_key = f"audio/{uuid.uuid4().hex}.wav"

        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            audio_mb = len(audio_bytes) / 1024 / 1024
            logger.info("Uploading %.1f MB to TOS: %s", audio_mb, tos_key)

            self.tos_client.put_object(
                bucket=self.tos_bucket,
                key=tos_key,
                content=audio_bytes,
            )

            presigned = self.tos_client.pre_signed_url(
                http_method=tos.HttpMethodType.Http_Method_Get,
                bucket=self.tos_bucket,
                key=tos_key,
                expires=3600,
            )
            url = presigned.signed_url
            logger.info("TOS presigned URL obtained (valid 3600s)")
            return url, tos_key

        except Exception as exc:
            logger.error("TOS upload failed: %s", exc)
            return None, tos_key  # return key so cleanup can still try

    def _cleanup_tos(self, tos_key: str) -> None:
        """Best-effort delete of TOS object."""
        try:
            self.tos_client.delete_object(
                bucket=self.tos_bucket,
                key=tos_key,
            )
            logger.info("Cleaned up TOS object: %s", tos_key)
        except Exception as exc:
            logger.warning("TOS cleanup failed for %s: %s", tos_key, exc)

    # ------------------------------------------------------------------
    # bigmodel submit
    # ------------------------------------------------------------------

    def _submit(self, presigned_url: str) -> str | None:
        """Submit presigned URL to bigmodel API, return request_id."""
        request_id = uuid.uuid4().hex

        body = {
            "user": {"uid": "1"},
            "audio": {
                "url": presigned_url,
                "format": "wav",
            },
            "request": {
                "model_name": "bigmodel",
                "show_utterances": True,
                "result_type": "single",
            },
        }

        headers = {
            **self._headers,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
        }

        try:
            resp = requests.post(
                _SUBMIT_URL,
                json=body,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Volcengine bigmodel submit failed: %s", exc)
            return None

        # bigmodel submit returns empty JSON {} on success;
        # the request_id we generated IS the task identifier
        logger.info(
            "Volcengine bigmodel submit accepted (request_id=%s): %s",
            request_id,
            resp.text[:200],
        )
        return request_id

    # ------------------------------------------------------------------
    # bigmodel query (poll)
    # ------------------------------------------------------------------

    def _wait_for_result(self, request_id: str) -> dict[str, Any] | None:
        """Poll bigmodel query API until completion or error."""
        headers = {
            **self._headers,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
        }

        start = time.time()
        while time.time() - start < _MAX_WAIT_SECONDS:
            try:
                resp = requests.post(
                    _QUERY_URL,
                    json={},
                    headers=headers,
                    timeout=60,
                )
                resp.raise_for_status()
                result = resp.json()
            except Exception as exc:
                logger.warning("Volcengine bigmodel poll error: %s", exc)
                time.sleep(_POLL_INTERVAL_SECONDS)
                continue

            code = result.get("code")
            message = result.get("message", "")
            result_text = result.get("result", {}).get("text", "") if isinstance(result.get("result"), dict) else ""

            logger.info(
                "Volcengine bigmodel task %s: code=%s message=%s has_text=%s (%.0fs elapsed)",
                request_id,
                code,
                message,
                bool(result_text),
                time.time() - start,
            )

            if code is not None and code != 0:
                if code == 2000:
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                logger.error(
                    "Volcengine bigmodel task %s failed: code=%s message=%s",
                    request_id,
                    code,
                    message,
                )
                return None

            if result_text:
                return result

            time.sleep(_POLL_INTERVAL_SECONDS)

        logger.error(
            "Volcengine bigmodel task %s timed out after %ds",
            request_id,
            _MAX_WAIT_SECONDS,
        )
        return None

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_result(result: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert bigmodel result to pipeline format.

        bigmodel returns (nested under result):
            utterances[]:
                text, start_time, end_time (ms, integer)
                words[]: {text, start_time, end_time} (ms, integer)

        Pipeline expects seconds (float):
            [{text, start_time, end_time, words: [{text, start_time, end_time, probability}]}]
        """
        # bigmodel wraps utterances under result.utterances
        inner = result.get("result", {})
        utterances = inner.get("utterances", [])

        # Fallback: some responses may put utterances at top level
        if not utterances:
            utterances = result.get("utterances", [])

        if not utterances:
            logger.warning("No utterances in Volcengine bigmodel result")
            return []

        segments: list[dict[str, Any]] = []

        for utt in utterances:
            text = utt.get("text", "").strip()
            if not text:
                continue

            start_ms = utt.get("start_time", 0)
            end_ms = utt.get("end_time", 0)

            words: list[dict[str, Any]] = []
            for w in utt.get("words", []):
                word_text = w.get("text", "").strip()
                if not word_text:
                    continue
                words.append(
                    {
                        "text": word_text,
                        "start_time": w.get("start_time", 0) / 1000.0,
                        "end_time": w.get("end_time", 0) / 1000.0,
                        "probability": 1.0,
                    }
                )

            seg: dict[str, Any] = {
                "text": text,
                "start_time": start_ms / 1000.0,
                "end_time": end_ms / 1000.0,
            }
            if words:
                seg["words"] = words

            segments.append(seg)

        return segments
