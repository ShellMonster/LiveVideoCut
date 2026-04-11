"""Local faster-whisper client with chunked processing for long audio files."""

import importlib
import logging
import os
import subprocess
import tempfile
from typing import Any, TypedDict, cast

logger = logging.getLogger(__name__)


class TranscriptSegment(TypedDict):
    text: str
    start_time: float
    end_time: float


class AudioChunk(TypedDict):
    path: str
    start_offset: float
    duration: float


class FasterWhisperClient:
    """Local ASR client using faster-whisper.

    Uses the same chunk/merge contract as the previous ASR client so the rest of the
    pipeline can continue consuming `[{text, start_time, end_time}]` without changes.
    """

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ):
        self.model_size = model_size or os.getenv("FASTER_WHISPER_MODEL", "small")
        self.device = device or os.getenv("FASTER_WHISPER_DEVICE", "cpu")
        self.compute_type = compute_type or os.getenv(
            "FASTER_WHISPER_COMPUTE_TYPE", "int8"
        )
        self._model: Any | None = None

    def transcribe(
        self,
        audio_path: str,
        chunk_duration: int = 1800,
        overlap: float = 3.0,
    ) -> list[TranscriptSegment]:
        with tempfile.TemporaryDirectory(prefix="fw_chunks_") as chunk_dir:
            chunks = self._split_audio(audio_path, chunk_duration, overlap, chunk_dir)

            if not chunks:
                return []

            all_transcripts: list[list[TranscriptSegment]] = []
            offsets: list[float] = []

            for chunk_info in chunks:
                chunk_transcript = self._transcribe_chunk(chunk_info["path"])
                offset = chunk_info["start_offset"]
                offsets.append(offset)

                for seg in chunk_transcript:
                    seg["start_time"] += offset
                    seg["end_time"] += offset

                all_transcripts.append(chunk_transcript)

        transcript_merger_module = importlib.import_module(
            "app.services.transcript_merger"
        )
        merger = transcript_merger_module.TranscriptMerger()
        merged = cast(
            list[TranscriptSegment],
            merger.merge(cast(Any, all_transcripts), offsets, overlap),
        )

        logger.info(
            "Transcribed %d chunks with faster-whisper, merged into %d segments",
            len(chunks),
            len(merged),
        )
        return merged

    def _get_model(self):
        try:
            whisper_module = importlib.import_module("faster_whisper")
            whisper_model_cls = whisper_module.WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Add it to backend dependencies."
            ) from exc

        if self._model is None:
            self._model = whisper_model_cls(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return cast(Any, self._model)

    def _split_audio(
        self,
        audio_path: str,
        chunk_duration: int,
        overlap: float,
        output_dir: str,
    ) -> list[AudioChunk]:
        probe_cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        try:
            result = subprocess.run(
                probe_cmd, capture_output=True, text=True, timeout=30
            )
            total_duration = float(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError) as exc:
            logger.error("Failed to probe audio duration: %s", exc)
            return []

        if total_duration <= 0:
            return []

        chunks: list[AudioChunk] = []
        start = 0.0
        idx = 0

        while start < total_duration:
            remaining = total_duration - start
            duration = min(chunk_duration, remaining)

            chunk_path = os.path.join(output_dir, f"chunk_{idx:04d}.wav")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                audio_path,
                "-t",
                str(duration),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-vn",
                chunk_path,
            ]

            try:
                subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
                if os.path.exists(chunk_path):
                    chunks.append(
                        {
                            "path": chunk_path,
                            "start_offset": start,
                            "duration": duration,
                        }
                    )
            except subprocess.TimeoutExpired:
                logger.warning("ffmpeg timeout for chunk starting at %.1f", start)

            start += chunk_duration
            idx += 1

        return chunks

    def _transcribe_chunk(self, chunk_path: str) -> list[TranscriptSegment]:
        model = self._get_model()
        segments, _info = model.transcribe(
            chunk_path,
            language="zh",
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=False,
        )

        normalized: list[TranscriptSegment] = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            normalized.append(
                {
                    "text": text,
                    "start_time": float(seg.start),
                    "end_time": float(seg.end),
                }
            )

        return normalized

    def health_check(self) -> bool:
        try:
            self._get_model()
            return True
        except Exception as exc:  # pragma: no cover - runtime safeguard
            logger.error("faster-whisper model load failed: %s", exc)
            return False
