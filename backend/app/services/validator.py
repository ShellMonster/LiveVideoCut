"""Video file validation using ffprobe."""

import json
import subprocess
from pathlib import Path

MAX_FILE_SIZE = 20 * 1024 * 1024 * 1024  # 20GB


class ValidationError(Exception):
    """Raised when video validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class VideoValidator:
    """Validates uploaded video files for processing pipeline."""

    def validate_format(self, filename: str) -> None:
        """Check file has .mp4 extension."""
        if not filename.lower().endswith(".mp4"):
            raise ValidationError(
                f"Unsupported format: {filename}. Only .mp4 files are accepted."
            )

    def validate_size(self, file_size: int) -> None:
        """Check file size <= 20GB."""
        if file_size > MAX_FILE_SIZE:
            gb = file_size / (1024**3)
            raise ValidationError(f"File too large: {gb:.1f}GB. Maximum size is 20GB.")

    def _run_ffprobe(self, file_path: str, args: list[str]) -> str:
        """Run ffprobe command and return stdout. Raises ValidationError on failure."""
        cmd = ["ffprobe", "-v", "quiet", *args, file_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            raise ValidationError("ffprobe not found. Please install FFmpeg.")
        except subprocess.TimeoutExpired:
            raise ValidationError("ffprobe timed out while inspecting file.")
        if result.returncode != 0:
            raise ValidationError(f"ffprobe failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def validate_codec(self, file_path: str) -> None:
        """Check video codec is H.264."""
        output = self._run_ffprobe(
            file_path,
            [
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
            ],
        )
        codec = output.strip()
        if codec != "h264":
            raise ValidationError(
                f"Unsupported video codec: {codec}. Only H.264 is accepted."
            )

    def validate_audio(self, file_path: str) -> None:
        """Check file has at least one audio stream."""
        output = self._run_ffprobe(
            file_path,
            [
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
            ],
        )
        if not output.strip():
            raise ValidationError("No audio stream found. File must contain audio.")

    def get_metadata(self, file_path: str) -> dict:
        """Extract video metadata via ffprobe."""
        output = self._run_ffprobe(
            file_path,
            [
                "-show_entries",
                "format=duration:stream=width,height,r_frame_rate,codec_name,codec_type",
                "-of",
                "json",
            ],
        )
        probe = json.loads(output)

        video_stream = None
        audio_codec = None
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_codec is None:
                audio_codec = stream.get("codec_name")

        if not video_stream:
            raise ValidationError("No video stream found in file.")

        # Parse frame rate (e.g. "30/1" → 30.0)
        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            fps = round(float(num) / float(den), 2)
        except (ValueError, ZeroDivisionError):
            fps = 0.0

        duration_str = probe.get("format", {}).get("duration", "0")
        try:
            duration = round(float(duration_str), 2)
        except ValueError:
            duration = 0.0

        return {
            "duration": duration,
            "width": video_stream.get("width", 0),
            "height": video_stream.get("height", 0),
            "fps": fps,
            "codec": video_stream.get("codec_name", "unknown"),
            "audio_codec": audio_codec or "none",
        }
