"""Segment fusion — merge visual clothing-change candidates with text boundaries."""

import logging

logger = logging.getLogger(__name__)

MERGE_GAP = 10.0  # dedup fused candidates within this gap


def fuse_candidates(
    visual_candidates: list[dict],
    text_boundaries: list[dict],
    video_duration: float,
    segment_granularity: str = "single_item",
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
         product_description, product_type, boundary_reason, key_phrases,
         merged_group_id: int | None}
    """
    logger.info(
        "Fusing %d visual candidates + %d text boundaries (duration=%.1fs, granularity=%s)",
        len(visual_candidates),
        len(text_boundaries),
        video_duration,
        segment_granularity,
    )

    if segment_granularity == "outfit":
        merged_regions = _merge_overlapping_boundaries(text_boundaries)
        logger.info(
            "Merged %d text boundaries → %d regions (outfit mode)",
            len(text_boundaries),
            len(merged_regions),
        )
    else:
        merged_regions = _split_overlapping_boundaries(text_boundaries)
        logger.info(
            "Split %d text boundaries → %d regions (single_item mode)",
            len(text_boundaries),
            len(merged_regions),
        )

    fused: list[dict] = []
    matched_region_ids: set[int] = set()

    # Pass 1: match visual candidates against merged text boundary regions
    for vc in visual_candidates:
        ts = vc["timestamp"]
        sim = vc.get("similarity", 0.0)
        region_idx = _find_containing_region(ts, merged_regions)

        if region_idx is not None:
            matched_region_ids.add(region_idx)
            region = merged_regions[region_idx]
            fused.append({
                "timestamp": ts,
                "end_time": region["end_time"],
                "region_start_time": region["start_time"],
                "similarity": max(sim, region.get("confidence", 0.0)),
                "source": "visual+text",
                "confidence": region.get("confidence", 0.0),
                "product_description": region.get("product_description", ""),
                "product_type": region.get("product_type", ""),
                "boundary_reason": region.get("boundary_reason", ""),
                "key_phrases": region.get("key_phrases", []),
                "merged_group_id": region_idx,
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
                "merged_group_id": None,
            })

    # Pass 2: add text regions not matched by any visual candidate
    for i, region in enumerate(merged_regions):
        if i in matched_region_ids:
            continue
        ts = region["start_time"]
        conf = region.get("confidence", 0.0)
        fused.append({
            "timestamp": ts,
            "end_time": region["end_time"],
            "region_start_time": region["start_time"],
            "similarity": conf,
            "source": "text",
            "confidence": conf,
            "product_description": region.get("product_description", ""),
            "product_type": region.get("product_type", ""),
            "boundary_reason": region.get("boundary_reason", ""),
            "key_phrases": region.get("key_phrases", []),
            "merged_group_id": i,
        })

    result = _dedup_close_boundaries(fused)

    logger.info(
        "Fusion result: %d candidates (%s)",
        len(result),
        _source_summary(result),
    )
    return result


def _merge_overlapping_boundaries(
    text_boundaries: list[dict],
) -> list[dict]:
    if not text_boundaries:
        return []

    sorted_tb = sorted(text_boundaries, key=lambda tb: tb.get("start_time", 0.0))
    regions: list[dict] = [_region_from_boundary(sorted_tb[0])]

    for tb in sorted_tb[1:]:
        prev = regions[-1]
        tb_start = tb.get("start_time", 0.0)

        if tb_start < prev["end_time"]:
            prev["end_time"] = max(prev["end_time"], tb.get("end_time", tb_start))
            if tb.get("confidence", 0.0) > prev.get("confidence", 0.0):
                prev["confidence"] = tb.get("confidence", 0.0)
            if len(tb.get("product_description", "")) > len(prev.get("product_description", "")):
                prev["product_description"] = tb.get("product_description", "")
            if tb.get("product_type", ""):
                prev["product_type"] = tb.get("product_type", "")
            if tb.get("boundary_reason", ""):
                prev["boundary_reason"] = tb.get("boundary_reason", "")
            prev["key_phrases"] = list(set(prev.get("key_phrases", []) + tb.get("key_phrases", [])))
        else:
            regions.append(_region_from_boundary(tb))

    return regions


def _split_overlapping_boundaries(
    text_boundaries: list[dict],
) -> list[dict]:
    """Split overlapping text_boundaries into fine-grained non-overlapping pieces.

    Instead of merging overlapping intervals into a giant region (which loses
    granularity), this splits them at every boundary edge. Each resulting piece
    carries the info of the most specific (shortest) boundary that covers it.
    """
    if not text_boundaries:
        return []

    sorted_tb = sorted(text_boundaries, key=lambda tb: tb.get("start_time", 0.0))

    # collect all unique split points (every start and end)
    split_points: set[float] = set()
    for tb in sorted_tb:
        split_points.add(tb.get("start_time", 0.0))
        split_points.add(tb.get("end_time", 0.0))
    splits = sorted(split_points)

    # build non-overlapping pieces by slicing at every split point
    regions: list[dict] = []
    for i in range(len(splits) - 1):
        piece_start = splits[i]
        piece_end = splits[i + 1]
        if piece_end - piece_start < 1.0:
            continue

        # find all boundaries covering this piece, pick the most specific (shortest)
        candidates = [
            tb for tb in sorted_tb
            if tb.get("start_time", 0.0) <= piece_start
            and tb.get("end_time", 0.0) >= piece_end
        ]
        if not candidates:
            continue

        # prefer the shortest (most specific) boundary
        best = min(candidates, key=lambda tb: tb.get("end_time", 0.0) - tb.get("start_time", 0.0))

        regions.append({
            "start_time": piece_start,
            "end_time": piece_end,
            "confidence": best.get("confidence", 0.0),
            "product_description": best.get("product_description", ""),
            "product_type": best.get("product_type", ""),
            "boundary_reason": best.get("boundary_reason", ""),
            "key_phrases": list(best.get("key_phrases", [])),
        })

    return regions


def _region_from_boundary(tb: dict) -> dict:
    """Create a region dict from a text boundary."""
    start = tb.get("start_time", 0.0)
    return {
        "start_time": start,
        "end_time": tb.get("end_time", start),
        "confidence": tb.get("confidence", 0.0),
        "product_description": tb.get("product_description", ""),
        "product_type": tb.get("product_type", ""),
        "boundary_reason": tb.get("boundary_reason", ""),
        "key_phrases": list(tb.get("key_phrases", [])),
    }


def _find_containing_region(
    ts: float,
    regions: list[dict],
) -> int | None:
    """Find the merged region whose [start_time, end_time] contains *ts*.

    If multiple regions contain *ts*, return the one with highest confidence.
    Returns region index or None.
    """
    best_idx: int | None = None
    best_conf = -1.0

    for i, region in enumerate(regions):
        if region["start_time"] <= ts <= region["end_time"]:
            conf = region.get("confidence", 0.0)
            if conf > best_conf:
                best_conf = conf
                best_idx = i

    return best_idx


def _dedup_close_boundaries(
    boundaries: list[dict],
    gap_seconds: float = MERGE_GAP,
) -> list[dict]:
    """Deduplicate boundaries within *gap_seconds* with the same merged_group_id."""
    if not boundaries:
        return []

    sorted_b = sorted(boundaries, key=lambda b: b["timestamp"])
    merged: list[dict] = [sorted_b[0]]

    for b in sorted_b[1:]:
        prev = merged[-1]
        same_group = (
            b.get("merged_group_id") is not None
            and b.get("merged_group_id") == prev.get("merged_group_id")
        )
        if b["timestamp"] - prev["timestamp"] <= gap_seconds and same_group:
            # same group & close → keep higher score
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
    min_duration: float = 10.0,
) -> list[dict]:
    """Convert fused candidates into segments, grouped by LLM text boundary.

    Candidates sharing the same merged_group_id (same LLM product region)
    are collapsed into ONE segment. Pure-visual candidates become individual segments.

    Args:
        fused: Output of fuse_candidates(), sorted by timestamp.
        video_duration: Total video length in seconds.
        min_duration: Discard segments shorter than this.

    Returns:
        List of segments in the same format as VLM confirmed_segments.
    """
    if not fused:
        return []

    sorted_fused = sorted(fused, key=lambda f: f["timestamp"])

    # Phase 1: group candidates by merged_group_id
    text_groups: dict[int, list[dict]] = {}
    visual_singles: list[dict] = []

    for fc in sorted_fused:
        gid = fc.get("merged_group_id")
        if gid is not None:
            text_groups.setdefault(gid, []).append(fc)
        else:
            visual_singles.append(fc)

    # Phase 2: build segments from text groups
    segments: list[dict] = []
    for gid, group in text_groups.items():
        # Use LLM region's start_time to capture full product discussion
        # (visual candidate may fire mid-way through the discussion)
        region_start = group[0].get("region_start_time")
        start_time = region_start if region_start is not None else group[0]["timestamp"]
        end_time = group[-1].get("end_time", group[-1]["timestamp"])
        # use the region's end_time if it extends beyond last candidate
        region_end = max(fc.get("end_time", fc["timestamp"]) for fc in group)
        end_time = max(end_time, region_end)

        best = max(group, key=lambda fc: fc.get("confidence", 0.0))
        confidence = best.get("confidence", 0.0)
        product_description = best.get("product_description", "")

        segments.append({
            "start_time": start_time,
            "end_time": end_time,
            "confidence": confidence,
            "product_info": {},
            "low_confidence": confidence < 0.5,
            "product_name": product_description if product_description else "未命名商品",
            "name_source": "llm_fusion",
        })

    # Phase 3: add pure-visual candidates as individual segments
    for fc in visual_singles:
        segments.append({
            "start_time": fc["timestamp"],
            "end_time": fc.get("end_time", fc["timestamp"]),
            "confidence": fc.get("confidence", 0.0),
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "vlm",
        })

    # Phase 4: sort by start_time, resolve overlaps, filter short
    segments.sort(key=lambda s: s["start_time"])
    segments = _resolve_overlaps(segments, video_duration)
    segments = [s for s in segments if s["end_time"] - s["start_time"] >= min_duration]

    logger.info(
        "Converted %d fused candidates → %d segments (text_groups=%d, visual=%d, after_filter=%d)",
        len(fused),
        len(segments),
        len(text_groups),
        len(visual_singles),
        len(segments),
    )
    return segments


def _resolve_overlaps(
    segments: list[dict],
    video_duration: float,
) -> list[dict]:
    """Resolve overlapping segments: text-grouped segments take priority."""
    if not segments:
        return []

    # text-grouped (llm_fusion) take priority over visual-only
    resolved: list[dict] = [segments[0]]

    for seg in segments[1:]:
        prev = resolved[-1]
        if seg["start_time"] < prev["end_time"]:
            # overlap: prefer higher confidence
            if seg.get("name_source") == "llm_fusion" and prev.get("name_source") != "llm_fusion":
                # trim previous to make room
                prev["end_time"] = seg["start_time"]
            elif prev.get("name_source") == "llm_fusion" and seg.get("name_source") != "llm_fusion":
                # trim current
                seg["start_time"] = prev["end_time"]
            else:
                # both same type: keep higher confidence, trim the other
                if seg["confidence"] > prev["confidence"]:
                    prev["end_time"] = seg["start_time"]
                else:
                    seg["start_time"] = prev["end_time"]

            # if trimmed segment became invalid, skip it
            if seg["start_time"] >= seg["end_time"]:
                continue
            if prev["start_time"] >= prev["end_time"]:
                resolved[-1] = seg
                continue

        resolved.append(seg)

    # clamp to video duration
    for seg in resolved:
        seg["end_time"] = min(seg["end_time"], video_duration)

    return resolved
