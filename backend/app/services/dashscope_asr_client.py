"""DashScope cloud ASR client — Alibaba Cloud paraformer-v2 with word-level timestamps.

Replaces the local SenseVoice client to avoid OOM issues with large videos.
Uses the same output format so the rest of the pipeline works unchanged:
    [{text, start_time, end_time, words: [{text, start_time, end_time, probability}]}]
"""

import json
import logging
import os
import tempfile
import time
from typing import Any

from app.services.asr_errors import APIError, ASRTimeoutError, AuthError

logger = logging.getLogger(__name__)

# DashScope transcription may take minutes for long audio
_MAX_WAIT_SECONDS = 600
_POLL_INTERVAL_SECONDS = 10


class DashScopeASRClient:
    """Cloud ASR client using Alibaba Cloud DashScope paraformer-v2.

    Flow:
        1. Upload local audio to DashScope Files API
        2. Submit async transcription job
        3. Poll until complete
        4. Parse result into pipeline-compatible format
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "DASHSCOPE_ASR_MODEL",
            "paraformer-v2",
        )
        self._api_key = api_key or os.getenv(
            "DASHSCOPE_API_KEY",
            os.getenv("VLM_API_KEY", ""),
        )
        self._file_id_to_cleanup: str | None = None

    def transcribe(
        self,
        audio_path: str,
    ) -> list[dict[str, Any]]:
        """Transcribe audio file, return segments with word-level timestamps."""
        import dashscope
        from dashscope import Files, Transcription

        dashscope.api_key = self._api_key

        file_url = self._upload_file(audio_path)

        logger.info("Submitting transcription: model=%s", self.model)
        submit_resp = Transcription.async_call(
            model=self.model,
            file_urls=[file_url],
            parameters={
                "timestamp_alignment_enabled": True,
            },
        )

        if submit_resp.status_code != 200:
            msg = f"Submit failed: status={submit_resp.status_code} code={submit_resp.code} msg={submit_resp.message}"
            logger.error("DashScope %s", msg)
            if submit_resp.status_code in (401, 403):
                raise AuthError(msg, provider="dashscope")
            raise APIError(msg, provider="dashscope")

        task_id = submit_resp.output.get("task_id", "")
        if not task_id:
            raise APIError("No task_id in DashScope response", provider="dashscope")

        logger.info("DashScope task submitted: %s", task_id)

        result = self._wait_for_result(Transcription, task_id)

        return self._fetch_and_parse(result)

    def _upload_file(self, audio_path: str) -> str:
        """Upload local file to DashScope Files API, return public URL."""
        from dashscope import Files

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        logger.info("Uploading to DashScope: %s (%.1f MB)", audio_path, file_size_mb)

        upload_resp = Files.upload(
            file_path=audio_path,
            purpose="inference",
        )

        if upload_resp.status_code != 200:
            msg = f"Upload failed: status={upload_resp.status_code} code={upload_resp.code}"
            if upload_resp.status_code in (401, 403):
                raise AuthError(msg, provider="dashscope")
            raise APIError(msg, provider="dashscope")

        uploaded = upload_resp.output.get("uploaded_files", [])
        if not uploaded:
            raise APIError("No uploaded_files in response", provider="dashscope")

        file_id = uploaded[0].get("file_id", "")
        if not file_id:
            raise APIError("No file_id in uploaded file", provider="dashscope")

        file_info = Files.get(file_id)
        if file_info.status_code != 200:
            msg = f"Failed to get file info: {file_info.message}"
            if file_info.status_code in (401, 403):
                raise AuthError(msg, provider="dashscope")
            raise APIError(msg, provider="dashscope")

        file_url = file_info.output.get("url", "")
        if not file_url:
            raise APIError("No URL in file info", provider="dashscope")

        logger.info("File uploaded: file_id=%s", file_id)
        self._file_id_to_cleanup = file_id

        return file_url

    def _wait_for_result(self, transcription_cls: Any, task_id: str) -> Any:
        """Poll DashScope for task completion."""
        start = time.time()
        while time.time() - start < _MAX_WAIT_SECONDS:
            resp = transcription_cls.fetch(task=task_id)

            status = resp.output.get("task_status", "") if resp.output else ""
            logger.info(
                "DashScope task %s status: %s (%.0fs elapsed)",
                task_id,
                status,
                time.time() - start,
            )

            if status == "SUCCEEDED":
                return resp
            if status in ("FAILED", "CANCELED"):
                detail = json.dumps(resp.output, ensure_ascii=False) if resp.output else ""
                raise APIError(f"Task {task_id} {status}: {detail}", provider="dashscope")

            time.sleep(_POLL_INTERVAL_SECONDS)

        raise ASRTimeoutError(f"Task {task_id} timed out after {_MAX_WAIT_SECONDS}s", provider="dashscope")

    def _fetch_and_parse(self, resp: Any) -> list[dict[str, Any]]:
        """Download transcription JSON and parse into pipeline format."""
        import urllib.request

        results = resp.output.get("results", []) if resp.output else []
        if not results:
            logger.warning("No results in DashScope response")
            return []

        transcription_url = results[0].get("transcription_url", "")
        if not transcription_url:
            raise APIError("No transcription_url in DashScope result", provider="dashscope")

        logger.info("Fetching transcription from: %s", transcription_url)
        try:
            req = urllib.request.Request(transcription_url)
            with urllib.request.urlopen(req, timeout=60) as f:
                raw = json.loads(f.read().decode("utf-8"))
        except Exception as exc:
            raise APIError(f"Failed to fetch transcription: {exc}", provider="dashscope") from exc

        return self._parse_dashscope_result(raw)

    @staticmethod
    def _parse_dashscope_result(
        raw: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Convert DashScope transcription JSON to pipeline format.

        DashScope returns:
            transcripts[].sentences[]:
                begin_time, end_time (ms), text, words[]
                words: {begin_time, end_time, word}
        """
        segments: list[dict[str, Any]] = []

        transcripts = raw.get("transcripts", [])
        for transcript in transcripts:
            sentences = transcript.get("sentences", [])
            for sent in sentences:
                text = sent.get("text", "").strip()
                if not text:
                    continue

                start_ms = sent.get("begin_time", 0)
                end_ms = sent.get("end_time", 0)

                # Build word-level timestamps
                words: list[dict[str, Any]] = []
                for w in sent.get("words", []):
                    word_text = w.get("text", "").strip()
                    if not word_text:
                        continue
                    words.append(
                        {
                            "text": word_text,
                            "start_time": w.get("begin_time", 0) / 1000.0,
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

    def health_check(self) -> bool:
        """Verify API key is configured."""
        return bool(self._api_key)
