"""FFmpeg command builder — single-command clip processing with subtitles and BGM."""

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RESOLUTION_SCALE = {
    "1080p": "scale=min(1920\\,iw):-2",
    "4k": "scale=min(3840\\,iw):-2",
}

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
            f":shaping=simple"
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

    @staticmethod
    def _build_atempo_chain(speed: float) -> str:
        """Build atempo filter chain. atempo only supports [0.5, 2.0], so chain for >2.0."""
        if speed == 1.0:
            return "volume=1.0"
        filters = []
        remaining = speed
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        if remaining != 1.0:
            filters.append(f"atempo={remaining:.4f}")
        filters.append("aresample=async=1")
        return ",".join(filters)

    def _build_trim_concat_command(
        self,
        input_path: str,
        start: float,
        duration: float,
        srt_path: str | None,
        bgm_path: str,
        output_path: str,
        filler_cut_ranges: list[dict],
        subtitle_position: str = "bottom",
        subtitle_template: str = "clean",
        custom_position_y: int | None = None,
        video_speed: float = 1.0,
        export_resolution: str = "1080p",
    ) -> list[str]:
        # 1. filler_cut_ranges → keep_ranges (segments to KEEP)
        keep_ranges: list[tuple[float, float]] = []
        prev_end = 0.0
        for fc in filler_cut_ranges:
            fs = fc["start_time"]
            fe = fc["end_time"]
            if fs > prev_end + 0.05:
                keep_ranges.append((prev_end, fs))
            prev_end = fe
        if prev_end < duration - 0.05:
            keep_ranges.append((prev_end, duration))

        # Fallback: if no valid keep ranges, keep the whole clip
        if not keep_ranges:
            keep_ranges = [(0.0, duration)]

        logger.info(
            "Trim-concat: %d filler cuts → %d keep ranges",
            len(filler_cut_ranges),
            len(keep_ranges),
        )

        # 2. Build filter_complex
        filters: list[str] = []

        # trim/atrim for each keep range (timestamps relative to -ss offset)
        for i, (ks, ke) in enumerate(keep_ranges):
            filters.append(
                f"[0:v]trim=start={ks:.6f}:end={ke:.6f},setpts=PTS-STARTPTS[v{i}]"
            )
            filters.append(
                f"[0:a]atrim=start={ks:.6f}:end={ke:.6f},asetpts=PTS-STARTPTS[a{i}]"
            )

        # concat all trimmed segments (video + audio interleaved)
        n = len(keep_ranges)
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
        filters.append(
            f"{concat_inputs}concat=n={n}:v=1:a=1[v_cat][a_cat]"
        )

        # optional resolution scale
        scale_filter = RESOLUTION_SCALE.get(export_resolution)
        if scale_filter:
            filters.append(f"[v_cat]{scale_filter}[v_scaled]")
        else:
            filters.append("[v_cat]copy[v_scaled]")

        # optional subtitle burn
        if srt_path:
            sub_filter = self._build_subtitle_filter(
                subtitle_path=srt_path,
                subtitle_position=subtitle_position,
                subtitle_template=subtitle_template,
                custom_position_y=custom_position_y,
            )
            filters.append(f"[v_scaled]{sub_filter}[v_sub]")
        else:
            filters.append("[v_scaled]copy[v_sub]")

        # optional speed change
        if video_speed != 1.0:
            filters.append(f"[v_sub]setpts=PTS/{video_speed}[v_out]")
            atempo_chain = self._build_atempo_chain(video_speed)
            filters.append(f"[a_cat]{atempo_chain}[a_speed]")
        else:
            filters.append("[v_sub]copy[v_out]")
            filters.append("[a_cat]copy[a_speed]")

        # BGM mix
        filters.append(
            "[1:a]volume=0.25,aloop=loop=-1:size=2e+09[bgm]"
        )
        filters.append(
            "[a_speed][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        filter_complex = ";".join(filters)

        # 3. Calculate effective duration
        total_keep = sum(ke - ks for ks, ke in keep_ranges)
        effective_duration = total_keep / video_speed

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
            str(effective_duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-x264opts",
            "rc-lookahead=5:bframes=1:ref=1",
            "-threads",
            "4",
            "-filter_threads",
            "2",
            "-movflags",
            "+faststart",
            "-fflags",
            "+genpts",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-y",
            output_path,
        ]

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
        filler_cut_ranges: list[dict] | None = None,
        video_speed: float = 1.0,
        export_resolution: str = "1080p",
    ) -> list[str]:
        if filler_cut_ranges:
            return self._build_trim_concat_command(
                input_path, start, duration, srt_path, bgm_path,
                output_path, filler_cut_ranges,
                subtitle_position, subtitle_template, custom_position_y,
                video_speed=video_speed,
                export_resolution=export_resolution,
            )

        video_chain = "[0:v]setpts=PTS-STARTPTS"

        scale_filter = RESOLUTION_SCALE.get(export_resolution)
        if scale_filter:
            video_chain += f",{scale_filter}"

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

        speed_video_suffix = ""
        speed_audio_filter = "[0:a]volume=1.0[orig]"
        effective_duration = duration

        if video_speed != 1.0:
            speed_video_suffix = f",setpts=PTS/{video_speed}"
            atempo_chain = self._build_atempo_chain(video_speed)
            speed_audio_filter = f"[0:a]{atempo_chain}[orig]"
            effective_duration = duration / video_speed

        filter_complex = (
            f"{video_chain};"
            f"[v_sub]copy{speed_video_suffix}[v_out];"
            f"{speed_audio_filter};"
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
            str(effective_duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-x264opts",
            "rc-lookahead=5:bframes=1:ref=1",
            "-threads",
            "4",
            "-filter_threads",
            "2",
            "-movflags",
            "+faststart",
            "-fflags",
            "+genpts",
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
            "-an",
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
        filler_cut_ranges: list[dict] | None = None,
        cover_timestamp: float | None = None,
        video_speed: float = 1.0,
        export_resolution: str = "1080p",
    ) -> dict[str, Any]:
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
            filler_cut_ranges=filler_cut_ranges,
            video_speed=video_speed,
            export_resolution=export_resolution,
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
                filler_cut_ranges=filler_cut_ranges,
                video_speed=video_speed,
                export_resolution=export_resolution,
            )
            result = subprocess.run(
                cut_cmd, capture_output=True, text=True, timeout=600
            )

        if result.returncode != 0:
            logger.error(
                "FFmpeg cut failed: %s", result.stderr[-500:] if result.stderr else ""
            )
            raise RuntimeError(f"FFmpeg cut failed: {result.returncode}")

        thumb_timestamp = cover_timestamp if cover_timestamp is not None else start + duration / 2
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
