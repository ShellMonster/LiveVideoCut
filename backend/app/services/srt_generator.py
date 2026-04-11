"""SRT subtitle generator — converts transcript segments to SRT format."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SRTGenerator:
    """Generates SRT subtitle files from transcript segments."""

    def generate(self, segments: list[dict], output_path: str) -> str:
        """Generate SRT file from transcript segments.

        Args:
            segments: List of dicts with keys: text, start_time, end_time.
            output_path: Path to write the .srt file.

        Returns:
            Absolute path to the generated .srt file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if not segments:
            output.write_text("", encoding="utf-8")
            logger.debug("Empty segments, wrote empty SRT: %s", output)
            return str(output.resolve())

        lines: list[str] = []
        srt_idx = 0
        for seg in segments:
            start_ts = self._format_timestamp(seg.get("start_time", 0.0))
            end_ts = self._format_timestamp(seg.get("end_time", 0.0))
            text = seg.get("text", "").strip()

            if not text:
                continue

            srt_idx += 1
            lines.append(str(srt_idx))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")

        content = "\n".join(lines)
        output.write_text(content, encoding="utf-8")
        logger.debug("Generated SRT with %d segments: %s", len(segments), output)
        return str(output.resolve())

    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
        if seconds < 0:
            seconds = 0.0

        total_ms = int(round(seconds * 1000))
        hours = total_ms // 3_600_000
        remaining = total_ms % 3_600_000
        minutes = remaining // 60_000
        remaining = remaining % 60_000
        secs = remaining // 1000
        millis = remaining % 1000

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
