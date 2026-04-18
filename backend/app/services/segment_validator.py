"""Segment validator — duration filtering and deduplication rules."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

Segment = dict[str, Any]


class SegmentValidator:
    """Validates and filters segments by duration and deduplication rules."""

    DEFAULT_MIN_DURATION: float = 60.0
    DEFAULT_MAX_DURATION: float = 600.0
    DEFAULT_DEDUP_WINDOW: float = 300.0  # 5 minutes

    def __init__(
        self,
        min_duration: float | None = None,
        dedupe_window: float | None = None,
        allow_returned_product: bool = False,
        max_duration: float | None = None,
    ) -> None:
        self.min_duration: float = (
            float(min_duration)
            if min_duration is not None
            else self.DEFAULT_MIN_DURATION
        )
        self.max_duration: float = (
            float(max_duration)
            if max_duration is not None
            else self.DEFAULT_MAX_DURATION
        )
        self.dedupe_window: float = (
            float(dedupe_window)
            if dedupe_window is not None
            else self.DEFAULT_DEDUP_WINDOW
        )
        self.allow_returned_product: bool = allow_returned_product

    def validate(self, segments: list[Segment], video_duration: float) -> list[Segment]:
        """Filter and validate segments.

        Rules:
        - Remove segments shorter than MIN_DURATION (60s)
        - Truncate segments longer than MAX_DURATION (600s)
        - Deduplicate same-name segments within 5-minute window
        - Ensure segments are within video duration
        """
        if not segments:
            return []

        segments = self._expand_point_segments(segments, video_duration)

        validated = []
        for seg in segments:
            seg = dict(seg)
            start = seg.get("start_time", 0.0)
            end = seg.get("end_time", 0.0)
            duration = end - start

            # 跳过过短的片段
            if duration < self.min_duration:
                logger.debug(
                    "Segment too short (%.1fs < %.1fs): %s",
                    duration,
                    self.min_duration,
                    seg.get("product_name", ""),
                )
                continue

            # 截断过长的片段
            if duration > self.max_duration:
                seg["end_time"] = start + self.max_duration
                logger.debug(
                    "Segment truncated (%.1fs → %.1fs)",
                    duration,
                    self.max_duration,
                )

            # 确保不超过视频总时长
            if seg["end_time"] > video_duration:
                seg["end_time"] = video_duration
            if seg["start_time"] < 0:
                seg["start_time"] = 0.0

            # 截断后可能变太短
            if seg["end_time"] - seg["start_time"] < self.min_duration:
                continue

            validated.append(seg)

        # 去重: 同名片段在5分钟窗口内只保留第一个
        validated = self._deduplicate(validated)

        return validated

    def _expand_point_segments(
        self, segments: list[Segment], video_duration: float
    ) -> list[Segment]:
        """Expand point-in-time detections into exportable ranges.

        Upstream VLM confirmations currently produce product-change points where
        `start_time == end_time`. Convert them into real segments by extending each
        point to the next point, or by anchoring the last point to the video end.
        """
        if not segments:
            return []

        ordered = [dict(seg) for seg in segments]
        ordered.sort(key=lambda s: s.get("start_time", 0.0))

        expanded = []
        for idx, seg in enumerate(ordered):
            start = float(seg.get("start_time", 0.0))
            end = float(seg.get("end_time", start))

            if end > start:
                expanded.append(seg)
                continue

            if idx < len(ordered) - 1:
                next_start = float(ordered[idx + 1].get("start_time", start))
                seg["end_time"] = max(next_start, start)
            else:
                seg["end_time"] = float(video_duration)
                if seg["end_time"] - start < self.min_duration:
                    seg["start_time"] = max(0.0, seg["end_time"] - self.min_duration)

            expanded.append(seg)

        return expanded

    def _deduplicate(self, segments: list[Segment]) -> list[Segment]:
        """Remove duplicate same-name segments within the configured window."""
        if not segments:
            return segments

        # 按开始时间排序
        segments.sort(key=lambda s: s.get("start_time", 0.0))

        seen: dict[str, float] = {}
        result = []
        last_kept_name = ""
        last_kept_start: float | None = None

        for seg in segments:
            name = seg.get("product_name", "")
            start = seg.get("start_time", 0.0)

            if not name:
                result.append(seg)
                continue

            last_seen_time = seen.get(name)
            should_deduplicate = (
                last_seen_time is not None
                and (start - last_seen_time) < self.dedupe_window
            )
            if self.allow_returned_product:
                should_deduplicate = (
                    last_kept_name == name
                    and last_kept_start is not None
                    and (start - last_kept_start) < self.dedupe_window
                )

            if should_deduplicate:
                logger.debug(
                    "Deduplicating segment '%s' at %.1fs (seen at %.1fs)",
                    name,
                    start,
                    last_seen_time if last_seen_time is not None else -1.0,
                )
                continue

            seen[name] = start
            result.append(seg)
            last_kept_name = name
            last_kept_start = start

        return result
