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
        if not file_url:
            return []

        logger.info("Submitting transcription: model=%s", self.model)
        submit_resp = Transcription.async_call(
            model=self.model,
            file_urls=[file_url],
            parameters={
                "timestamp_alignment_enabled": True,
            },
        )

        if submit_resp.status_code != 200:
            logger.error(
                "DashScope submit failed: status=%s code=%s msg=%s",
                submit_resp.status_code,
                submit_resp.code,
                submit_resp.message,
            )
            return []

        task_id = submit_resp.output.get("task_id", "")
        if not task_id:
            logger.error("No task_id in DashScope response")
            return []

        logger.info("DashScope task submitted: %s", task_id)

        result = self._wait_for_result(Transcription, task_id)
        if result is None:
            return []

        return self._fetch_and_parse(result)

    def _upload_file(self, audio_path: str) -> str | None:
        """Upload local file to DashScope Files API, return public URL."""
        from dashscope import Files

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        logger.info("Uploading to DashScope: %s (%.1f MB)", audio_path, file_size_mb)

        upload_resp = Files.upload(
            file_path=audio_path,
            purpose="inference",
        )

        if upload_resp.status_code != 200:
            logger.error(
                "DashScope upload failed: status=%s code=%s msg=%s",
                upload_resp.status_code,
                upload_resp.code,
                upload_resp.message,
            )
            return None

        uploaded = upload_resp.output.get("uploaded_files", [])
        if not uploaded:
            logger.error("No uploaded_files in response")
            return None

        file_id = uploaded[0].get("file_id", "")
        if not file_id:
            logger.error("No file_id in uploaded file")
            return None

        # Get the public URL for this file
        file_info = Files.get(file_id)
        if file_info.status_code != 200:
            logger.error("Failed to get file info: %s", file_info.message)
            return None

        file_url = file_info.output.get("url", "")
        if not file_url:
            logger.error("No URL in file info")
            return None

        logger.info("File uploaded: file_id=%s", file_id)

        # Schedule cleanup in background (best-effort)
        self._file_id_to_cleanup = file_id

        return file_url

        # Step 2: Poll until complete
        result = self._wait_for_result(Transcription, task_id)
        if result is None:
            return []

        # Step 3: Fetch and parse transcription
        return self._fetch_and_parse(result)

    def _wait_for_result(self, transcription_cls: Any, task_id: str) -> Any | None:
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
                logger.error(
                    "DashScope task %s failed: %s",
                    task_id,
                    json.dumps(resp.output, ensure_ascii=False) if resp.output else "",
                )
                return None

            time.sleep(_POLL_INTERVAL_SECONDS)

        logger.error(
            "DashScope task %s timed out after %ds", task_id, _MAX_WAIT_SECONDS
        )
        return None

    def _fetch_and_parse(self, resp: Any) -> list[dict[str, Any]]:
        """Download transcription JSON and parse into pipeline format."""
        import urllib.request

        results = resp.output.get("results", []) if resp.output else []
        if not results:
            logger.warning("No results in DashScope response")
            return []

        transcription_url = results[0].get("transcription_url", "")
        if not transcription_url:
            logger.error("No transcription_url in DashScope result")
            return []

        # Download the transcription JSON
        logger.info("Fetching transcription from: %s", transcription_url)
        try:
            req = urllib.request.Request(transcription_url)
            with urllib.request.urlopen(req, timeout=60) as f:
                raw = json.loads(f.read().decode("utf-8"))
        except Exception as exc:
            logger.error("Failed to fetch transcription: %s", exc)
            return []

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
