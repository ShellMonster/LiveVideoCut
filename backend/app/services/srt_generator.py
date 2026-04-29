"""Subtitle asset generator supporting basic SRT and karaoke ASS output."""

import logging
import importlib
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SUBTITLE_DOWNGRADE_CHAIN: dict[str, tuple[str, ...]] = {
    "off": ("off",),
    "basic": ("basic", "off"),
    "styled": ("styled", "basic", "off"),
    "karaoke": ("karaoke", "basic", "off"),
}

MAX_CHARS_PER_LINE = 15

KARAOKE_ASS_HEADER_TEMPLATE = """[Script Info]
ScriptType: v4.00+
WrapStyle: 2
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK SC,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,1,{alignment},30,30,{margin_v},1
Style: Highlight,Noto Sans CJK SC,{highlight_font_size},&H0000FFFF,&H0000FFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,1,{alignment},30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def subtitle_alignment_and_margin(
    subtitle_position: str = "bottom",
    custom_position_y: int | None = None,
    play_res_y: int = 1920,
) -> tuple[int, int]:
    """Return ASS/force_style alignment and vertical margin.

    custom_position_y is a 0-100 percentage from top to bottom.
    """
    if subtitle_position == "top":
        return 8, 120
    if subtitle_position == "middle":
        return 5, 0
    if subtitle_position == "custom" and custom_position_y is not None:
        y = min(max(int(custom_position_y), 0), 100)
        return 2, max(0, int(round((100 - y) * play_res_y / 100)))
    return 2, 120


def build_karaoke_ass_header(
    subtitle_position: str = "bottom",
    custom_position_y: int | None = None,
    font_size: int = 60,
    highlight_font_size: int = 72,
) -> str:
    alignment, margin_v = subtitle_alignment_and_margin(
        subtitle_position,
        custom_position_y,
    )
    return KARAOKE_ASS_HEADER_TEMPLATE.format(
        alignment=alignment,
        margin_v=margin_v,
        font_size=font_size,
        highlight_font_size=highlight_font_size,
    )


class SRTGenerator:
    """Generates subtitle files from transcript segments."""

    def __init__(self) -> None:
        try:
            opencc_module = importlib.import_module("opencc")
            self._converter = opencc_module.OpenCC("t2s")
        except Exception:  # pragma: no cover - dependency fallback
            self._converter = None

    def resolve_phase1_export_mode(
        self, requested_mode: str, has_text: bool, has_word_timing: bool = False
    ) -> str:
        if not has_text:
            return "off"

        for mode in self._iter_downgrade_chain(requested_mode):
            if mode == "karaoke":
                if has_word_timing:
                    return "karaoke"
                logger.info(
                    "Subtitle mode '%s' downgraded to basic export due to missing word timings",
                    requested_mode,
                )
                continue
            if mode == "styled":
                logger.info(
                    "Subtitle mode '%s' downgraded to basic export",
                    requested_mode,
                )
                continue
            if mode == "basic":
                return "basic"
            if mode == "off":
                return "off"

        return "off"

    def _iter_downgrade_chain(self, requested_mode: str) -> Iterable[str]:
        return SUBTITLE_DOWNGRADE_CHAIN.get(
            requested_mode,
            SUBTITLE_DOWNGRADE_CHAIN["basic"],
        )

    def generate(
        self,
        segments: list[dict[str, Any]],
        output_path: str,
        mode: str = "basic",
        subtitle_position: str = "bottom",
        custom_position_y: int | None = None,
        font_size: int = 60,
        highlight_font_size: int = 72,
    ) -> str:
        if mode == "karaoke":
            return self.generate_ass(
                segments,
                output_path,
                subtitle_position=subtitle_position,
                custom_position_y=custom_position_y,
                font_size=font_size,
                highlight_font_size=highlight_font_size,
            )
        return self.generate_srt(segments, output_path)

    def generate_srt(self, segments: list[dict[str, Any]], output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if not segments:
            output.write_text("", encoding="utf-8")
            logger.debug("Empty segments, wrote empty SRT: %s", output)
            return str(output.resolve())

        lines: list[str] = []
        srt_idx = 0
        for seg in segments:
            start_ts = self._format_srt_timestamp(float(seg.get("start_time", 0.0)))
            end_ts = self._format_srt_timestamp(float(seg.get("end_time", 0.0)))
            text = self._to_simplified(str(seg.get("text", "")).strip())

            if not text:
                continue

            srt_idx += 1
            lines.append(str(srt_idx))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")

        output.write_text("\n".join(lines), encoding="utf-8")
        return str(output.resolve())

    def generate_ass(
        self,
        segments: list[dict[str, Any]],
        output_path: str,
        subtitle_position: str = "bottom",
        custom_position_y: int | None = None,
        font_size: int = 60,
        highlight_font_size: int = 72,
    ) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        non_overlapping = self._ensure_non_overlapping(segments)

        lines = [
            build_karaoke_ass_header(
                subtitle_position=subtitle_position,
                custom_position_y=custom_position_y,
                font_size=font_size,
                highlight_font_size=highlight_font_size,
            ).rstrip("\n")
        ]
        for seg in non_overlapping:
            is_truncated = seg.pop("_truncated", False)
            for sub in self._split_into_line_segments(seg):
                base = self._build_base_dialogue(sub)
                if base:
                    base_text = base["text"]
                    if is_truncated:
                        base_text = "{\\fad(0,200)}" + base_text
                    lines.append(
                        "Dialogue: 0,{start},{end},Default,,0,0,0,,{text}".format(
                            start=self._format_ass_timestamp(base["start_time"]),
                            end=self._format_ass_timestamp(base["end_time"]),
                            text=base_text,
                        )
                    )
                for overlay in self._build_highlight_overlays(sub):
                    overlay_text = overlay["text"]
                    if is_truncated:
                        overlay_text = "{\\fad(0,200)}" + overlay_text
                    lines.append(
                        "Dialogue: 1,{start},{end},Default,,0,0,0,,{text}".format(
                            start=self._format_ass_timestamp(overlay["start_time"]),
                            end=self._format_ass_timestamp(overlay["end_time"]),
                            text=overlay_text,
                        )
                    )

        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(output.resolve())

    def _split_into_line_segments(
        self, segment: dict[str, Any]
    ) -> list[dict[str, Any]]:
        words = self._expand_words(segment)
        if not words or sum(len(w["text"]) for w in words) <= MAX_CHARS_PER_LINE:
            return [segment]

        line_groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_len = 0
        for w in words:
            wlen = len(w["text"])
            if current and current_len + wlen > MAX_CHARS_PER_LINE:
                line_groups.append(current)
                current = []
                current_len = 0
            current.append(w)
            current_len += wlen
        if current:
            line_groups.append(current)

        seg_start = float(segment.get("start_time", 0.0))
        seg_end = float(segment.get("end_time", 0.0))
        results: list[dict[str, Any]] = []
        for group in line_groups:
            sub = dict(segment)
            sub["start_time"] = group[0]["start_time"]
            sub["end_time"] = group[-1]["end_time"]
            sub["words"] = group
            sub["_tokens"] = [w["text"] for w in group]
            results.append(sub)

        if results:
            results[0]["start_time"] = seg_start
            results[-1]["end_time"] = seg_end
        return results

    @staticmethod
    def _ensure_non_overlapping(
        segments: list[dict[str, Any]],
        min_gap: float = 0.08,
    ) -> list[dict[str, Any]]:
        """Add min_gap between segments AND trim words that fall outside truncated bounds."""
        if not segments:
            return segments
        sorted_segs = sorted(segments, key=lambda s: float(s.get("start_time", 0.0)))
        result: list[dict[str, Any]] = []
        for i, seg in enumerate(sorted_segs):
            seg = dict(seg)
            end = float(seg.get("end_time", 0.0))
            seg["_truncated"] = False

            if i < len(sorted_segs) - 1:
                next_start = float(sorted_segs[i + 1].get("start_time", 0.0))
                max_end = next_start - min_gap
                if end > max_end:
                    seg["end_time"] = max(max_end, float(seg.get("start_time", 0.0)) + 0.1)
                    seg["_truncated"] = True
                if float(seg.get("end_time", 0.0)) > next_start:
                    seg["end_time"] = max(
                        next_start - min_gap,
                        float(seg.get("start_time", 0.0)) + 0.05,
                    )
                    seg["_truncated"] = True

            # Trim words to fit within (possibly truncated) segment bounds
            new_end = float(seg.get("end_time", 0.0))
            if "words" in seg and seg["words"]:
                trimmed = [w for w in seg["words"] if float(w.get("start_time", 0.0)) < new_end]
                if trimmed != seg["words"]:
                    seg["words"] = trimmed
                    seg["_truncated"] = True
                    if trimmed:
                        seg["text"] = "".join(w.get("text", "") for w in trimmed)

            result.append(seg)
        return result

    def _build_highlight_overlays(
        self, segment: dict[str, Any]
    ) -> list[dict[str, Any]]:
        words = self._expand_words(segment)
        if not words:
            return []

        tokens = segment.get("_tokens")
        if tokens is None:
            tokens = [
                str(word["text"]) for word in words if str(word.get("text", "")).strip()
            ]
        if not tokens:
            return []

        separator = self._detect_separator(segment, tokens)
        overlays: list[dict[str, Any]] = []
        for idx, word in enumerate(words):
            overlays.append(
                {
                    "start_time": float(word["start_time"]),
                    "end_time": float(word["end_time"]),
                    "text": self._build_overlay_text(tokens, idx, separator),
                }
            )
        return overlays

    def _build_base_dialogue(
        self, segment: dict[str, Any]
    ) -> dict[str, Any] | None:
        words = self._expand_words(segment)
        seg_start = float(segment.get("start_time", 0.0))
        seg_end = float(segment.get("end_time", 0.0))

        if not words:
            text = self._to_simplified(str(segment.get("text", "")).strip())
            if not text:
                return None
            duration_cs = self._to_centiseconds(seg_end - seg_start)
            if len(text) <= 1:
                return {"start_time": seg_start, "end_time": seg_end,
                        "text": f"{{\\kf{duration_cs}}}{text}"}
            per_char = max(1, duration_cs // len(text))
            remainder = max(0, duration_cs - per_char * len(text))
            parts = []
            for idx, char in enumerate(text):
                cs = per_char + (1 if idx < remainder else 0)
                parts.append(f"{{\\kf{cs}}}{char}")
            return {"start_time": seg_start, "end_time": seg_end,
                    "text": "".join(parts)}

        parts: list[str] = []

        initial_delay = words[0]["start_time"] - seg_start
        if initial_delay > 0.01:
            parts.append(f"{{\\k{self._to_centiseconds(initial_delay)}}}")

        for i, word in enumerate(words):
            if i > 0:
                gap = word["start_time"] - words[i - 1]["end_time"]
                if gap > 0.01:
                    parts.append(f"{{\\k{self._to_centiseconds(gap)}}}")
            duration = word["end_time"] - word["start_time"]
            parts.append(f"{{\\kf{self._to_centiseconds(duration)}}}{word['text']}")

        trailing = seg_end - words[-1]["end_time"]
        if trailing > 0.01:
            parts.append(f"{{\\k{self._to_centiseconds(trailing)}}}")

        return {"start_time": seg_start, "end_time": seg_end, "text": "".join(parts)}

    def _build_overlay_text(
        self, tokens: list[str], active_index: int, separator: str
    ) -> str:
        # All tokens present (invisible) so active token is at correct horizontal position
        parts: list[str] = []
        for idx, token in enumerate(tokens):
            if idx > 0 and separator:
                parts.append("{\\alpha&HFF&}" + separator)
            if idx == active_index:
                parts.append(
                    "{\\alpha&H00&\\rHighlight"
                    "\\t(0,60,\\fscx130\\fscy130)"
                    "\\t(60,120,\\fscx105\\fscy105)"
                    "\\t(120,200,\\fscx100\\fscy100)}"
                    + token
                    + "{\\rDefault\\alpha&HFF&}"
                )
            else:
                parts.append("{\\alpha&HFF&}" + token)
        return "".join(parts)

    def _detect_separator(self, segment: dict[str, Any], tokens: list[str]) -> str:
        if tokens and all(re.fullmatch(r"[\u4e00-\u9fff]", token) for token in tokens):
            return ""
        text = self._to_simplified(str(segment.get("text", "")).strip())
        collapsed = "".join(tokens)
        if text and collapsed and collapsed != text and " " in text:
            return " "
        return ""

    def _expand_words(self, segment: dict[str, Any]) -> list[dict[str, Any]]:
        expanded: list[dict[str, Any]] = []
        for word in segment.get("words", []) or []:
            text = self._to_simplified(str(word.get("text", "")).strip())
            start = float(word.get("start_time", segment.get("start_time", 0.0)))
            end = float(word.get("end_time", segment.get("end_time", 0.0)))
            if not text or end <= start:
                continue

            if self._should_split_to_chars(text):
                expanded.extend(self._split_word_to_chars(text, start, end))
            else:
                expanded.append({"text": text, "start_time": start, "end_time": end})
        return expanded

    def _split_word_to_chars(
        self, text: str, start_time: float, end_time: float
    ) -> list[dict[str, Any]]:
        chars = [char for char in text if char.strip()]
        if not chars:
            return []
        duration = end_time - start_time
        if len(chars) == 1:
            return [{"text": chars[0], "start_time": start_time, "end_time": end_time}]
        weights = [1.0] * len(chars)
        weights[0] = 1.3
        weights[-1] = 0.7
        total_weight = sum(weights)
        pieces = []
        cursor = start_time
        for idx, char in enumerate(chars):
            if idx == len(chars) - 1:
                char_end = end_time
            else:
                char_end = cursor + duration * (weights[idx] / total_weight)
            pieces.append({"text": char, "start_time": cursor, "end_time": char_end})
            cursor = char_end
        return pieces

    def _should_split_to_chars(self, text: str) -> bool:
        return len(text) > 1 and bool(re.fullmatch(r"[\u4e00-\u9fff]+", text))

    def _to_simplified(self, text: str) -> str:
        if not text:
            return ""
        if self._converter is None:
            return text
        return self._converter.convert(text)

    def _to_centiseconds(self, seconds: float) -> int:
        return max(1, int(round(max(0.0, seconds) * 100)))

    def _format_srt_timestamp(self, seconds: float) -> str:
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

    def _format_ass_timestamp(self, seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        total_cs = int(round(seconds * 100))
        hours = total_cs // 360000
        remaining = total_cs % 360000
        minutes = remaining // 6000
        remaining = remaining % 6000
        secs = remaining // 100
        centis = remaining % 100
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
