"""Segment fusion — merge visual clothing-change candidates with text boundaries."""

import logging

logger = logging.getLogger(__name__)

FUSION_WINDOW = 15.0


def fuse_candidates(
    visual_candidates: list[dict],
    text_boundaries: list[dict],
    video_duration: float,
) -> list[dict]:
    """Merge visual candidates and text boundaries into a unified list.

    Args:
        visual_candidates: [{timestamp, similarity, frame_idx}]
        text_boundaries: [{timestamp, confidence, product_description,
                           product_type, boundary_reason}]
        video_duration: Total video length in seconds.

    Returns:
        Sorted list of [{timestamp, similarity, source, confidence,
                         product_description}] by timestamp ascending.
    """
    logger.info(
        "Fusing %d visual candidates + %d text boundaries (duration=%.1fs)",
        len(visual_candidates),
        len(text_boundaries),
        video_duration,
    )

    fused: list[dict] = []

    for vc in visual_candidates:
        ts = vc["timestamp"]
        sim = vc.get("similarity", 0.0)
        near, matched_text = _is_near_visual_candidate(ts, text_boundaries)
        if near and matched_text is not None:
            fused.append(
                {
                    "timestamp": ts,
                    "similarity": max(sim, matched_text.get("confidence", 0.0)),
                    "source": "visual+text",
                    "confidence": matched_text.get("confidence", 0.0),
                    "product_description": matched_text.get("product_description", ""),
                }
            )
        else:
            fused.append(
                {
                    "timestamp": ts,
                    "similarity": sim,
                    "source": "visual",
                    "confidence": 0.0,
                    "product_description": "",
                }
            )

    matched_timestamps = {f["timestamp"] for f in fused if f["source"].startswith("visual+text")}
    for tb in text_boundaries:
        ts = tb["timestamp"]
        if not _is_near(ts, matched_timestamps, FUSION_WINDOW):
            conf = tb.get("confidence", 0.0)
            fused.append(
                {
                    "timestamp": ts,
                    "similarity": conf,
                    "source": "text",
                    "confidence": conf,
                    "product_description": tb.get("product_description", ""),
                }
            )

    result = _merge_close_boundaries(fused)

    logger.info(
        "Fusion result: %d segments (%s)",
        len(result),
        _source_summary(result),
    )
    return result


def _is_near_visual_candidate(
    ts: float,
    text_boundaries: list[dict],
    window: float = FUSION_WINDOW,
) -> tuple[bool, dict | None]:
    """Check if *ts* is within *window* of any text boundary.

    Returns (is_near, matched_boundary_or_None).
    """
    best: dict | None = None
    best_dist = window

    for tb in text_boundaries:
        dist = abs(tb["timestamp"] - ts)
        if dist <= best_dist:
            best_dist = dist
            best = tb

    if best is not None:
        return True, best
    return False, None


def _merge_close_boundaries(
    boundaries: list[dict],
    gap_seconds: float = FUSION_WINDOW,
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


def _is_near(ts: float, timestamps: set[float], window: float) -> bool:
    """Check if *ts* is within *window* of any value in *timestamps*."""
    return any(abs(ts - t) <= window for t in timestamps)
