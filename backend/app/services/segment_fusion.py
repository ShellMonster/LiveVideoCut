"""Segment fusion — two-layer tree: visual outfit periods + LLM product discussions.

Architecture:
  Level 0: Outfit Period — driven by visual clothing-change signals
  Level 1: Product Discussion — driven by LLM text boundaries within each outfit period

Export granularity selects the level:
  single_item → Level 1 (each product discussion is a clip)
  outfit      → Level 0 (each outfit period is a clip)
"""

import logging

logger = logging.getLogger(__name__)

MERGE_GAP = 10.0  # dedup fused candidates within this gap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fuse_candidates(
    visual_candidates: list[dict],
    text_boundaries: list[dict],
    video_duration: float,
    segment_granularity: str = "single_item",
) -> list[dict]:
    """Two-layer fusion: visual outfit periods + LLM product discussions.

    Builds a tree:
      Level 0 (outfit periods): defined by visual candidate timestamps
      Level 1 (product discussions): LLM text boundaries nested inside Level 0

    Then flattens to the appropriate level based on *segment_granularity*.

    Args:
        visual_candidates: [{timestamp, similarity, frame_idx}]
        text_boundaries: [{start_time, end_time, confidence, product_description,
                           product_type, boundary_reason, key_phrases}]
        video_duration: Total video length in seconds.
        segment_granularity: "single_item" (Level 1) or "outfit" (Level 0).

    Returns:
        Sorted list of fused boundary points by timestamp ascending.
    """
    logger.info(
        "Two-layer fusion: %d visual + %d text (duration=%.1fs, granularity=%s)",
        len(visual_candidates),
        len(text_boundaries),
        video_duration,
        segment_granularity,
    )

    if not visual_candidates and not text_boundaries:
        return []

    # --- Build Level 0: outfit periods from visual candidates ---
    outfit_periods = _build_outfit_periods(visual_candidates, video_duration)
    logger.info("Level 0: %d outfit periods from visual signals", len(outfit_periods))

    # --- Build Level 1: nest LLM text boundaries into outfit periods ---
    text_regions = _split_overlapping_boundaries(text_boundaries)
    _nest_text_regions(outfit_periods, text_regions)

    # --- Flatten to the selected granularity ---
    if segment_granularity == "outfit":
        result = _flatten_to_level0(outfit_periods, video_duration)
    else:
        result = _flatten_to_level1(outfit_periods, video_duration)

    result = _dedup_close_boundaries(result)

    logger.info(
        "Fusion result: %d segments at %s level (%s)",
        len(result),
        "L0 outfit" if segment_granularity == "outfit" else "L1 product",
        _source_summary(result),
    )
    return result


# ---------------------------------------------------------------------------
# Level 0: outfit periods
# ---------------------------------------------------------------------------

def _build_outfit_periods(
    visual_candidates: list[dict],
    video_duration: float,
) -> list[dict]:
    """Build outfit periods (Level 0) from visual change detection points.

    Each visual candidate marks a boundary between two outfit periods.
    Returns list of {start_time, end_time, visual_confidence, children: []}.
    """
    if not visual_candidates:
        # No visual signals → single outfit period spanning the whole video
        return [{
            "start_time": 0.0,
            "end_time": video_duration,
            "visual_confidence": 0.0,
            "children": [],
        }]

    sorted_vc = sorted(visual_candidates, key=lambda vc: vc["timestamp"])

    periods: list[dict] = []
    prev_ts = 0.0

    for vc in sorted_vc:
        ts = vc["timestamp"]
        sim = vc.get("similarity", 0.0)
        if ts > prev_ts:
            periods.append({
                "start_time": prev_ts,
                "end_time": ts,
                "visual_confidence": sim,
                "children": [],
            })
        prev_ts = ts

    # Final period from last visual point to end of video
    if prev_ts < video_duration:
        periods.append({
            "start_time": prev_ts,
            "end_time": video_duration,
            "visual_confidence": 0.0,
            "children": [],
        })

    return periods


# ---------------------------------------------------------------------------
# Level 1: text regions nested into outfit periods
# ---------------------------------------------------------------------------

def _nest_text_regions(
    outfit_periods: list[dict],
    text_regions: list[dict],
) -> None:
    """Assign each text region to the outfit period that best contains it.

    A text region is assigned to the period that overlaps the most with it.
    Text regions not contained in any period are assigned to the nearest one.
    """
    for tr in text_regions:
        tr_start = tr["start_time"]
        tr_end = tr["end_time"]
        best_idx = -1
        best_overlap = -1.0

        for i, period in enumerate(outfit_periods):
            overlap_start = max(tr_start, period["start_time"])
            overlap_end = min(tr_end, period["end_time"])
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i

        if best_idx >= 0:
            outfit_periods[best_idx]["children"].append(tr)
        elif outfit_periods:
            # Fallback: assign to the nearest period
            nearest = min(
                range(len(outfit_periods)),
                key=lambda i: abs(tr_start - outfit_periods[i]["start_time"]),
            )
            outfit_periods[nearest]["children"].append(tr)


# ---------------------------------------------------------------------------
# Flatten helpers
# ---------------------------------------------------------------------------

def _flatten_to_level0(
    outfit_periods: list[dict],
    video_duration: float,
) -> list[dict]:
    """Flatten to outfit periods (Level 0). Each period becomes one segment.

    Merges product info from nested Level 1 children into the parent period.
    """
    result: list[dict] = []

    for period in outfit_periods:
        children = period.get("children", [])
        # Use the best child's product info if available
        best_child = max(children, key=lambda c: c.get("confidence", 0.0)) if children else None

        product_description = ""
        product_type = ""
        confidence = period.get("visual_confidence", 0.0)
        key_phrases: list[str] = []
        boundary_reason = ""

        if best_child:
            product_description = best_child.get("product_description", "")
            product_type = best_child.get("product_type", "")
            confidence = max(confidence, best_child.get("confidence", 0.0))
            key_phrases = best_child.get("key_phrases", [])
            boundary_reason = best_child.get("boundary_reason", "")

        # Collect all phrases from all children
        if children:
            all_phrases = set()
            for c in children:
                all_phrases.update(c.get("key_phrases", []))
            key_phrases = list(all_phrases)

        source = "visual+text" if children else "visual"

        result.append({
            "timestamp": period["start_time"],
            "end_time": period["end_time"],
            "region_start_time": period["start_time"],
            "similarity": confidence,
            "source": source,
            "confidence": confidence,
            "product_description": product_description,
            "product_type": product_type,
            "boundary_reason": boundary_reason,
            "key_phrases": key_phrases,
            "merged_group_id": 0,
        })

    return result


def _flatten_to_level1(
    outfit_periods: list[dict],
    video_duration: float,
) -> list[dict]:
    """Flatten to product discussions (Level 1).

    - Periods WITH children → one segment per child (product discussion)
    - Periods WITHOUT children → one segment per period (visual-only)
    """
    result: list[dict] = []
    group_id = 0

    for period in outfit_periods:
        children = period.get("children", [])

        if children:
            for child in children:
                # Clamp child times to period boundaries
                start = max(child["start_time"], period["start_time"])
                end = min(child["end_time"], period["end_time"])

                result.append({
                    "timestamp": start,
                    "end_time": end,
                    "region_start_time": start,
                    "similarity": child.get("confidence", 0.0),
                    "source": "visual+text",
                    "confidence": child.get("confidence", 0.0),
                    "product_description": child.get("product_description", ""),
                    "product_type": child.get("product_type", ""),
                    "boundary_reason": child.get("boundary_reason", ""),
                    "key_phrases": child.get("key_phrases", []),
                    "merged_group_id": group_id,
                })
                group_id += 1
        else:
            # Visual-only period — becomes its own segment
            result.append({
                "timestamp": period["start_time"],
                "end_time": period["end_time"],
                "similarity": period.get("visual_confidence", 0.0),
                "source": "visual",
                "confidence": period.get("visual_confidence", 0.0),
                "product_description": "",
                "product_type": "",
                "boundary_reason": "",
                "key_phrases": [],
                "merged_group_id": None,
            })

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
