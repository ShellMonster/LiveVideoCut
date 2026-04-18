"""FFmpeg command builder — single-command clip processing with subtitles and BGM."""

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
SUBTITLE_FONTS_DIR = ASSETS_DIR / "fonts"
SUBTITLE_FONT_FAMILY = "Noto Sans CJK SC"

SUBTITLE_STYLE = (
    "FontName=Microsoft YaHei,"
    "FontSize=18,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "Outline=2"
)


class FFmpegBuilder:
    """Builds FFmpeg filter_complex commands for clip processing."""

    def _build_subtitle_filter(
        self,
        subtitle_path: str,
        subtitle_position: str = "bottom",
        subtitle_template: str = "clean",
        custom_position_y: int | None = None,
    ) -> str:
        escaped_subtitle_path = subtitle_path.replace("\\", "\\\\").replace(":", "\\:")
        escaped_fonts_dir = (
            str(SUBTITLE_FONTS_DIR.resolve()).replace("\\", "\\\\").replace(":", "\\:")
        )
        subtitle_filter = (
            f"subtitles=filename={escaped_subtitle_path}:fontsdir={escaped_fonts_dir}"
        )
        if not subtitle_path.lower().endswith(".ass"):
            style = self._build_force_style(
                subtitle_position=subtitle_position,
                subtitle_template=subtitle_template,
                custom_position_y=custom_position_y,
            )
            if style:
                subtitle_filter += f":force_style='{style}'"
        return subtitle_filter

    def _build_force_style(
        self,
        subtitle_position: str,
        subtitle_template: str,
        custom_position_y: int | None,
    ) -> str | None:
        style_parts: list[str] = [f"FontName={SUBTITLE_FONT_FAMILY}"]

        if subtitle_position == "middle":
            style_parts.append("Alignment=10")
        elif subtitle_position == "custom" and custom_position_y is not None:
            margin_v = max(0, int(round((100 - custom_position_y) * 10.8)))
            style_parts.extend(["Alignment=2", f"MarginV={margin_v}"])

        template_styles = {
            "clean": [],
            "ecommerce": ["FontSize=20", "Outline=2", "Bold=1"],
            "bold": ["FontSize=22", "Outline=3", "Bold=1"],
            "karaoke": [
                "FontSize=20",
                "Outline=2",
                "Bold=1",
                "PrimaryColour=&H0000FFFF",
            ],
        }
        style_parts.extend(template_styles.get(subtitle_template, []))

        return ",".join(style_parts)

    def build_cut_command(
        self,
        input_path: str,
        start: float,
        duration: float,
        srt_path: str | None,
        bgm_path: str,
        watermark_path: str,
        output_path: str,
        subtitle_position: str = "bottom",
        subtitle_template: str = "clean",
        custom_position_y: int | None = None,
    ) -> list[str]:
        """Build FFmpeg command for cutting + subtitles + BGM + watermark.

        Uses libx264 re-encoding (NOT -c copy) for frame-accurate cuts.
        All processing via filter_complex in a single command.
        """
        video_chain = "[0:v]setpts=PTS-STARTPTS"
        if srt_path:
            video_chain += "," + self._build_subtitle_filter(
                subtitle_path=srt_path,
                subtitle_position=subtitle_position,
                subtitle_template=subtitle_template,
                custom_position_y=custom_position_y,
            )
        else:
            video_chain += ",copy"
        video_chain += "[v_sub]"

        filter_complex = (
            f"{video_chain};"
            f"[v_sub]copy[v_out];"
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
        segment: dict[str, Any],
        srt_path: str | None,
        bgm_path: str,
        watermark_path: str,
        output_path: str,
        thumbnail_path: str,
        subtitle_mode: str = "basic",
        subtitle_position: str = "bottom",
        subtitle_template: str = "clean",
        custom_position_y: int | None = None,
    ) -> dict[str, Any]:
        """Execute the full clip processing pipeline.

        Returns:
            {"output_path": str, "thumbnail_path": str, "duration": float}
        """
        start = float(segment.get("start_time", 0.0))
        end = float(segment.get("end_time", 0.0))
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
            subtitle_position=subtitle_position,
            subtitle_template=subtitle_template,
            custom_position_y=custom_position_y,
        )

        logger.info("Processing clip: %s → %s", input_path, output_path)
        result = subprocess.run(cut_cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0 and srt_path and subtitle_mode != "off":
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
