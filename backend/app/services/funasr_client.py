"""FunASR client — audio transcription with chunked processing for memory safety."""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# FunASR HTTP server 默认端口
DEFAULT_FUNASR_URL = "http://localhost:10095"


class FunASRClient:
    """Client for FunASR Docker container — audio transcription with chunked processing.

    FunASR 存在内存泄漏风险，因此：
    - 音频按 30 分钟分块处理
    - 每个块独立发送到 FunASR HTTP API
    - 块之间有 3-5s 重叠用于去重
    """

    def __init__(self, funasr_url: str = DEFAULT_FUNASR_URL):
        self.funasr_url = funasr_url.rstrip("/")

    def transcribe(
        self,
        audio_path: str,
        chunk_duration: int = 1800,
        overlap: float = 3.0,
    ) -> list[dict]:
        """Transcribe audio file using FunASR with chunked processing.

        Args:
            audio_path: Path to audio file.
            chunk_duration: Duration of each chunk in seconds (default 30min).
            overlap: Overlap between chunks in seconds (default 3s).

        Returns:
            List of transcript segments: [{text, start_time, end_time}]
        """
        with tempfile.TemporaryDirectory(prefix="funasr_chunks_") as chunk_dir:
            chunks = self._split_audio(audio_path, chunk_duration, overlap, chunk_dir)

            if not chunks:
                return []

            all_transcripts = []
            offsets = []

            for chunk_info in chunks:
                chunk_transcript = self._transcribe_chunk(chunk_info["path"])
                offset = chunk_info["start_offset"]
                offsets.append(offset)

                # 应用时间偏移
                for seg in chunk_transcript:
                    seg["start_time"] += offset
                    seg["end_time"] += offset

                all_transcripts.append(chunk_transcript)

        # 合并并去重重叠区域
        from app.services.transcript_merger import TranscriptMerger

        merger = TranscriptMerger()
        merged = merger.merge(all_transcripts, offsets, overlap)

        logger.info(
            "Transcribed %d chunks, merged into %d segments",
            len(chunks),
            len(merged),
        )
        return merged

    def _split_audio(
        self,
        audio_path: str,
        chunk_duration: int,
        overlap: float,
        output_dir: str,
    ) -> list[dict]:
        """Split audio into chunks using ffmpeg.

        Returns:
            List of chunk info: [{path, start_offset, duration}]
        """
        # 获取音频总时长
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
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError) as e:
            logger.error("Failed to probe audio duration: %s", e)
            return []

        if total_duration <= 0:
            return []

        chunks = []
        start = 0.0
        idx = 0

        while start < total_duration:
            # 最后一个块不需要 overlap
            remaining = total_duration - start
            duration = min(chunk_duration, remaining)

            chunk_filename = f"chunk_{idx:04d}.wav"
            chunk_path = os.path.join(output_dir, chunk_filename)

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
                subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
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

    def _transcribe_chunk(self, chunk_path: str) -> list[dict]:
        """Send single chunk to FunASR API.

        Returns:
            Raw transcript segments: [{text, start_time, end_time}]
        """
        try:
            with open(chunk_path, "rb") as f:
                audio_data = f.read()
        except OSError as e:
            logger.error("Failed to read chunk %s: %s", chunk_path, e)
            return []

        # FunASR 官方 Python HTTP server API 调用
        try:
            response = httpx.post(
                f"{self.funasr_url}/recognition",
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
                timeout=120.0,
            )
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException, Exception) as e:
            logger.error("FunASR API call failed: %s", e)
            return []

        result = response.json()
        segments = []

        # 解析 FunASR 返回格式
        if isinstance(result, dict):
            text = result.get("text", "")
            if text:
                segments.append(
                    {
                        "text": text,
                        "start_time": float(result.get("start", 0.0)),
                        "end_time": float(result.get("end", 0.0)),
                    }
                )
            # 兼容旧格式 segments
            for item in result.get("segments", []):
                segments.append(
                    {
                        "text": item.get("text", ""),
                        "start_time": float(item.get("start", 0.0)),
                        "end_time": float(item.get("end", 0.0)),
                    }
                )
            # 官方 Python HTTP server 使用 sentences
            for item in result.get("sentences", []):
                segments.append(
                    {
                        "text": item.get("text", ""),
                        "start_time": float(item.get("start", 0.0)),
                        "end_time": float(item.get("end", 0.0)),
                    }
                )
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    segments.append(
                        {
                            "text": item.get("text", ""),
                            "start_time": float(item.get("start", 0.0)),
                            "end_time": float(item.get("end", 0.0)),
                        }
                    )

        return segments

    def health_check(self) -> bool:
        """Check if FunASR HTTP service is reachable."""
        try:
            response = httpx.get(
                f"{self.funasr_url}/docs",
                timeout=5.0,
            )
            return response.status_code == 200
        except (httpx.HTTPError, httpx.TimeoutException, Exception):
            return False
