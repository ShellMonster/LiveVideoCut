"""Volcengine (火山引擎) VC 字幕生成 ASR client — 逐字时间戳。

Uses the VC (Video Captioning) API which accepts audio via TOS presigned URL
and returns utterances with character-level timestamps.

Flow:
    1. Extract audio from video if needed (FFmpeg)
    2. Upload audio to TOS, get pre-signed URL
    3. POST presigned URL to VC submit endpoint (with appid URL param)
    4. GET VC query endpoint (appid + id in URL params) until complete
    5. Parse utterances with character-level timestamps (ms → seconds)
    6. Clean up TOS object and temp audio file

Auth: x-api-key header (same credential as bigmodel ASR).

Output format (identical to other ASR clients):
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

_VC_SUBMIT_URL = "https://openspeech.bytedance.com/api/v1/vc/submit"
_VC_QUERY_URL = "https://openspeech.bytedance.com/api/v1/vc/query"

# Default submit query params — VC uses appid, not language
_DEFAULT_SUBMIT_PARAMS = {
    "appid": "volcengine_vc",
    "use_itn": "True",
    "use_capitalize": "True",
    "max_lines": "1",
    "words_per_line": "15",
}


class VolcengineVCClient:
    """Cloud ASR client using Volcengine VC API via TOS pre-signed URLs.

    The VC API uses submit+poll pattern similar to the bigmodel API,
    but with different endpoints and request body structure.
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
            logger.error("Volcengine VC credentials not configured (api_key)")
            return []

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        logger.info("Submitting to Volcengine VC: %s (%.1f MB)", audio_path, file_size_mb)

        # Step 1: extract audio from video if needed
        submit_path = self._maybe_extract_audio(audio_path)
        tos_key: str | None = None
        try:
            # Step 2: upload to TOS and get presigned URL
            presigned_url, tos_key = self._upload_to_tos(submit_path)
            if not presigned_url:
                return []

            # Step 3: submit to VC
            request_id = self._submit(presigned_url)
            if not request_id:
                return []

            logger.info("Volcengine VC task submitted: %s", request_id)

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
    # Audio extraction
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
            return None, tos_key

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
    # VC submit
    # ------------------------------------------------------------------

    def _submit(self, presigned_url: str) -> str | None:
        """Submit presigned URL to VC API, return request_id."""
        body = {"url": presigned_url}

        try:
            resp = requests.post(
                _VC_SUBMIT_URL,
                params=_DEFAULT_SUBMIT_PARAMS,
                json=body,
                headers=self._headers,
                timeout=120,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Volcengine VC submit request failed: %s", exc)
            return None

        result = resp.json()
        code = result.get("code")
        message = result.get("message", "")

        # VC submit may return request_id in the response
        request_id = result.get("request_id") or result.get("id") or uuid.uuid4().hex

        if code is not None and code != 0:
            logger.error(
                "Volcengine VC submit returned error: code=%s message=%s",
                code,
                message,
            )
            return None

        logger.info(
            "Volcengine VC submit accepted (request_id=%s): %s",
            request_id,
            resp.text[:200],
        )
        return request_id

    # ------------------------------------------------------------------
    # VC query (poll)
    # ------------------------------------------------------------------

    def _wait_for_result(self, request_id: str) -> dict[str, Any] | None:
        """Poll VC query API until completion or error.

        VC query uses GET with appid + id in URL params (not POST with JSON body).
        """
        start = time.time()
        while time.time() - start < _MAX_WAIT_SECONDS:
            try:
                query_params = {
                    "appid": _DEFAULT_SUBMIT_PARAMS["appid"],
                    "id": request_id,
                    "blocking": "0",
                }
                resp = requests.get(
                    _VC_QUERY_URL,
                    params=query_params,
                    headers=self._headers,
                    timeout=60,
                )
                resp.raise_for_status()
                result = resp.json()
            except Exception as exc:
                logger.warning("Volcengine VC poll error: %s", exc)
                time.sleep(_POLL_INTERVAL_SECONDS)
                continue

            code = result.get("code")
            message = result.get("message", "")
            utterances = self._extract_utterances(result)

            logger.info(
                "Volcengine VC task %s: code=%s message=%s utterances=%d (%.0fs elapsed)",
                request_id,
                code,
                message,
                len(utterances),
                time.time() - start,
            )

            if code is not None and code != 0:
                if code == 2000:
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                logger.error(
                    "Volcengine VC task %s failed: code=%s message=%s",
                    request_id,
                    code,
                    message,
                )
                return None

            if utterances:
                return result

            time.sleep(_POLL_INTERVAL_SECONDS)

        logger.error(
            "Volcengine VC task %s timed out after %ds",
            request_id,
            _MAX_WAIT_SECONDS,
        )
        return None

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_utterances(result: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract utterances list from VC API response.

        VC may nest utterances under different keys depending on the response.
        """
        # Try result.utterances first
        inner = result.get("result", {})
        if isinstance(inner, dict):
            utterances = inner.get("utterances", [])
            if utterances:
                return utterances

        # Try top-level utterances
        utterances = result.get("utterances", [])
        if utterances:
            return utterances

        # Try data.utterances
        data = result.get("data", {})
        if isinstance(data, dict):
            utterances = data.get("utterances", [])
            if utterances:
                return utterances

        return []

    @staticmethod
    def _parse_result(result: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert VC result to pipeline format.

        VC returns utterances[]:
            text, start_time, end_time (ms, integer)
            words[]: {text, start_time, end_time} (ms, integer)

        Pipeline expects seconds (float):
            [{text, start_time, end_time, words: [{text, start_time, end_time, probability}]}]
        """
        # Try result.utterances first
        inner = result.get("result", {})
        utterances = []
        if isinstance(inner, dict):
            utterances = inner.get("utterances", [])
        if not utterances:
            utterances = result.get("utterances", [])
        if not utterances:
            data = result.get("data", {})
            if isinstance(data, dict):
                utterances = data.get("utterances", [])

        if not utterances:
            logger.warning("No utterances in Volcengine VC result")
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
