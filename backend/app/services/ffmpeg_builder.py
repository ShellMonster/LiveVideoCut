"""FFmpeg command builder — single-command clip processing with subtitles, BGM, watermark."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SUBTITLE_STYLE = (
    "FontName=Microsoft YaHei,"
    "FontSize=18,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "Outline=2"
)


class FFmpegBuilder:
    """Builds FFmpeg filter_complex commands for clip processing."""

    def build_cut_command(
        self,
        input_path: str,
        start: float,
        duration: float,
        srt_path: str | None,
        bgm_path: str,
        watermark_path: str,
        output_path: str,
    ) -> list[str]:
        """Build FFmpeg command for cutting + subtitles + BGM + watermark.

        Uses libx264 re-encoding (NOT -c copy) for frame-accurate cuts.
        All processing via filter_complex in a single command.
        """
        video_chain = "[0:v]"
        if srt_path:
            escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:")
            video_chain += f"subtitles=filename={escaped_srt}"
        else:
            video_chain += "null"
        video_chain += "[v_sub]"

        filter_complex = (
            f"{video_chain};"
            f"[v_sub][2:v]overlay=W-w-15:15[v_out];"
            f"[0:a]volume=1.0[orig];"
            f"[1:a]volume=0.25,aloop=loop=-1:size=2e+09[bgm];"
            f"[orig][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        return [
            "ffmpeg",
            "-ss",
            str(start),
            "-i",
            input_path,
            "-i",
            bgm_path,
            "-i",
            watermark_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[v_out]",
            "-map",
            "[aout]",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-y",
            output_path,
        ]

    def build_thumbnail_command(
        self, input_path: str, timestamp: float, output_path: str
    ) -> list[str]:
        """Build FFmpeg command to extract thumbnail at given timestamp."""
        return [
            "ffmpeg",
            "-ss",
            str(timestamp),
            "-i",
            input_path,
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-y",
            output_path,
        ]

    def process_clip(
        self,
        input_path: str,
        segment: dict,
        srt_path: str,
        bgm_path: str,
        watermark_path: str,
        output_path: str,
        thumbnail_path: str,
    ) -> dict:
        """Execute the full clip processing pipeline.

        Returns:
            {"output_path": str, "thumbnail_path": str, "duration": float}
        """
        start = segment.get("start_time", 0.0)
        end = segment.get("end_time", 0.0)
        duration = end - start

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(thumbnail_path).parent.mkdir(parents=True, exist_ok=True)

        cut_cmd = self.build_cut_command(
            input_path=input_path,
            start=start,
            duration=duration,
            srt_path=srt_path,
            bgm_path=bgm_path,
            watermark_path=watermark_path,
            output_path=output_path,
        )

        logger.info("Processing clip: %s → %s", input_path, output_path)
        result = subprocess.run(cut_cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0 and srt_path:
            logger.warning("FFmpeg subtitle burn failed, retrying without subtitles")
            cut_cmd = self.build_cut_command(
                input_path=input_path,
                start=start,
                duration=duration,
                srt_path=None,
                bgm_path=bgm_path,
                watermark_path=watermark_path,
                output_path=output_path,
            )
            result = subprocess.run(
                cut_cmd, capture_output=True, text=True, timeout=600
            )

        if result.returncode != 0:
            logger.error(
                "FFmpeg cut failed: %s", result.stderr[-500:] if result.stderr else ""
            )
            raise RuntimeError(f"FFmpeg cut failed: {result.returncode}")

        thumb_timestamp = start + duration / 2
        thumb_cmd = self.build_thumbnail_command(
            input_path, thumb_timestamp, thumbnail_path
        )

        thumb_result = subprocess.run(
            thumb_cmd, capture_output=True, text=True, timeout=60
        )
        if thumb_result.returncode != 0:
            logger.warning(
                "Thumbnail extraction failed: %s",
                thumb_result.stderr[-200:] if thumb_result.stderr else "",
            )

        return {
            "output_path": str(Path(output_path).resolve()),
            "thumbnail_path": str(Path(thumbnail_path).resolve()),
            "duration": duration,
        }
