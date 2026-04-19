"""Segment fusion — merge visual clothing-change candidates with text boundaries."""

import logging

logger = logging.getLogger(__name__)

MERGE_GAP = 10.0  # dedup boundaries within this gap


def fuse_candidates(
    visual_candidates: list[dict],
    text_boundaries: list[dict],
    video_duration: float,
) -> list[dict]:
    """Merge visual candidates and text boundaries into a unified list.

    Uses interval matching: a visual candidate matches a text boundary if the
    candidate's timestamp falls within the text boundary's [start_time, end_time].

    Args:
        visual_candidates: [{timestamp, similarity, frame_idx}]
        text_boundaries: [{start_time, end_time, confidence, product_description,
                           product_type, boundary_reason, key_phrases}]
        video_duration: Total video length in seconds.

    Returns:
        Sorted list of fused boundary points by timestamp ascending, each carrying:
        {timestamp, end_time, similarity, source, confidence,
         product_description, product_type, boundary_reason, key_phrases}
    """
    logger.info(
        "Fusing %d visual candidates + %d text boundaries (duration=%.1fs)",
        len(visual_candidates),
        len(text_boundaries),
        video_duration,
    )

    fused: list[dict] = []
    matched_tb_indices: set[int] = set()

    # Pass 1: match visual candidates against text boundary intervals
    for vc in visual_candidates:
        ts = vc["timestamp"]
        sim = vc.get("similarity", 0.0)
        matched_idx = _find_containing_interval(ts, text_boundaries)

        if matched_idx is not None:
            matched_tb_indices.add(matched_idx)
            tb = text_boundaries[matched_idx]
            fused.append({
                "timestamp": ts,
                "end_time": tb.get("end_time", ts),
                "similarity": max(sim, tb.get("confidence", 0.0)),
                "source": "visual+text",
                "confidence": tb.get("confidence", 0.0),
                "product_description": tb.get("product_description", ""),
                "product_type": tb.get("product_type", ""),
                "boundary_reason": tb.get("boundary_reason", ""),
                "key_phrases": tb.get("key_phrases", []),
            })
        else:
            fused.append({
                "timestamp": ts,
                "end_time": ts,
                "similarity": sim,
                "source": "visual",
                "confidence": 0.0,
                "product_description": "",
                "product_type": "",
                "boundary_reason": "",
                "key_phrases": [],
            })

    # Pass 2: add text boundaries not matched by any visual candidate
    for i, tb in enumerate(text_boundaries):
        if i in matched_tb_indices:
            continue
        ts = tb.get("start_time", 0.0)
        conf = tb.get("confidence", 0.0)
        fused.append({
            "timestamp": ts,
            "end_time": tb.get("end_time", ts),
            "similarity": conf,
            "source": "text",
            "confidence": conf,
            "product_description": tb.get("product_description", ""),
            "product_type": tb.get("product_type", ""),
            "boundary_reason": tb.get("boundary_reason", ""),
            "key_phrases": tb.get("key_phrases", []),
        })

    result = _merge_close_boundaries(fused)

    logger.info(
        "Fusion result: %d segments (%s)",
        len(result),
        _source_summary(result),
    )
    return result


def _find_containing_interval(
    ts: float,
    text_boundaries: list[dict],
) -> int | None:
    """Find the text boundary whose [start_time, end_time] contains *ts*.

    If multiple boundaries contain *ts*, return the one with highest confidence.
    Returns boundary index or None.
    """
    best_idx: int | None = None
    best_conf = -1.0

    for i, tb in enumerate(text_boundaries):
        start = tb.get("start_time", 0.0)
        end = tb.get("end_time", start)
        conf = tb.get("confidence", 0.0)
        if start <= ts <= end and conf > best_conf:
            best_conf = conf
            best_idx = i

    return best_idx


def _merge_close_boundaries(
    boundaries: list[dict],
    gap_seconds: float = MERGE_GAP,
) -> list[dict]:
    """Deduplicate boundaries within *gap_seconds*, keeping highest score."""
    if not boundaries:
        return []

    sorted_b = sorted(boundaries, key=lambda b: b["timestamp"])
    merged: list[dict] = [sorted_b[0]]

    for b in sorted_b[1:]:
        prev = merged[-1]
        if b["timestamp"] - prev["timestamp"] <= gap_seconds:
            prev_score = prev["similarity"] + prev.get("confidence", 0.0)
            curr_score = b["similarity"] + b.get("confidence", 0.0)
            if curr_score > prev_score:
                merged[-1] = b
        else:
            merged.append(b)

    return merged


def _source_summary(segments: list[dict]) -> str:
    """Return a short summary string of source counts."""
    counts: dict[str, int] = {}
    for s in segments:
        src = s.get("source", "unknown")
        counts[src] = counts.get(src, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def fused_to_segments(
    fused: list[dict],
    video_duration: float,
) -> list[dict]:
    """Convert fused boundary points into segment intervals for downstream pipeline.

    Sorts boundaries by timestamp, then pairs consecutive boundaries into
    segments [boundary_i, boundary_{i+1}). Last segment ends at video_duration.

    Returns:
        List of segments in the same format as VLM confirmed_segments:
        {start_time, end_time, confidence, product_info, low_confidence,
         product_name, name_source}
    """
    if not fused:
        return []

    sorted_fused = sorted(fused, key=lambda f: f["timestamp"])
    segments: list[dict] = []

    for i, boundary in enumerate(sorted_fused):
        start_time = boundary["timestamp"]
        end_time = (
            sorted_fused[i + 1]["timestamp"]
            if i + 1 < len(sorted_fused)
            else video_duration
        )
        confidence = boundary.get("confidence", 0.0)
        product_description = boundary.get("product_description", "")
        source = boundary.get("source", "visual")

        # name_source: "llm_fusion" when text contributed, "vlm" otherwise
        name_source = "llm_fusion" if "text" in source else "vlm"

        segments.append({
            "start_time": start_time,
            "end_time": end_time,
            "confidence": confidence,
            "product_info": {},
            "low_confidence": confidence < 0.5,
            "product_name": product_description if product_description else "未命名商品",
            "name_source": name_source,
        })

    logger.info(
        "Converted %d fused boundaries → %d segments (duration=%.1fs)",
        len(fused),
        len(segments),
        video_duration,
    )
    return segments
