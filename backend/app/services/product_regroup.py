"""Product regroup — identify same-product segments across non-adjacent time ranges."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

Segment = dict[str, Any]


def regroup_segments(
    segments: list[Segment],
    task_path: str | None = None,
    method: str = "name_only",
    threshold: float = 0.85,
) -> list[Segment]:
    """Group segments belonging to the same product.

    For Phase 1, only ``name_only`` method is implemented:
    segments with the same product_name are grouped together,
    each group gets a group_id, and segments within a group
    carry sub_ranges (list of their individual time ranges).

    Future phases will add ``name_clip`` (CLIP visual similarity)
    and ``clip_only``.
    """
    if not segments:
        return segments

    if method not in ("name_only", "name_clip", "clip_only"):
        logger.warning("Unknown merge method '%s', falling back to name_only", method)
        method = "name_only"

    if method == "name_only":
        return _group_by_name(segments)

    logger.info("Method '%s' not yet implemented, falling back to name_only", method)
    return _group_by_name(segments)


def _group_by_name(segments: list[Segment]) -> list[Segment]:
    """Group segments by product_name, merging same-name segments into one."""
    name_groups: dict[str, list[tuple[int, Segment]]] = {}
    for idx, seg in enumerate(segments):
        name = seg.get("product_name", "").strip()
        if not name:
            name = f"_unnamed_{idx}"
        if name not in name_groups:
            name_groups[name] = []
        name_groups[name].append((idx, seg))

    for name in name_groups:
        name_groups[name].sort(key=lambda x: x[1].get("start_time", 0.0))

    result: list[Segment] = []

    for name, group in name_groups.items():
        if len(group) == 1:
            seg = dict(group[0][1])
            seg["group_id"] = _sanitize_group_id(name)
            seg["sub_ranges"] = [{
                "start_time": seg.get("start_time", 0.0),
                "end_time": seg.get("end_time", 0.0),
                "original_index": group[0][0],
            }]
            seg["merged_from_count"] = 1
            result.append(seg)
        else:
            merged = _merge_same_name_group(name, group)
            result.append(merged)

    result.sort(
        key=lambda s: s["sub_ranges"][0]["start_time"]
        if s.get("sub_ranges")
        else s.get("start_time", 0.0)
    )

    logger.info(
        "Product regroup: %d segments -> %d groups (%d merged)",
        len(segments), len(result),
        sum(1 for s in result if s.get("merged_from_count", 1) > 1),
    )

    return result


def _merge_same_name_group(name: str, group: list[tuple[int, Segment]]) -> Segment:
    """Merge multiple segments with the same product_name into one."""
    first_seg = dict(group[0][1])

    sub_ranges = []
    texts = []

    for orig_idx, seg in group:
        sub_ranges.append({
            "start_time": seg.get("start_time", 0.0),
            "end_time": seg.get("end_time", 0.0),
            "original_index": orig_idx,
        })
        text = seg.get("text", "").strip()
        if text:
            texts.append(text)

    first_seg["group_id"] = _sanitize_group_id(name)
    first_seg["sub_ranges"] = sub_ranges
    first_seg["merged_from_count"] = len(group)
    first_seg["start_time"] = sub_ranges[0]["start_time"]
    first_seg["end_time"] = sub_ranges[-1]["end_time"]
    first_seg["text"] = " ".join(texts)

    confidences = [seg.get("confidence", 0) for _, seg in group]
    if confidences:
        first_seg["confidence"] = max(confidences)

    return first_seg


def _sanitize_group_id(name: str) -> str:
    """Create a filesystem-safe group ID from product name."""
    sanitized = re.sub(r'[^\w]', '_', name)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized[:64] if sanitized else "unknown"
