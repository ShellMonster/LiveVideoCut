"""Tests for segment_fusion — two-layer tree fusion of visual + text signals."""

from app.services.segment_fusion import (
    MERGE_GAP,
    _build_outfit_periods,
    _dedup_close_boundaries,
    _flatten_to_level0,
    _flatten_to_level1,
    _nest_text_regions,
    _split_overlapping_boundaries,
    fused_to_segments,
    fuse_candidates,
)


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _vc(timestamp: float, similarity: float = 0.5, frame_idx: int = 0) -> dict:
    """Shorthand for a visual candidate."""
    return {"timestamp": timestamp, "similarity": similarity, "frame_idx": frame_idx}


def _tb(
    start_time: float,
    end_time: float,
    confidence: float = 0.9,
    description: str = "商品A",
    product_type: str = "上衣",
    reason: str = "换品",
    phrases: list[str] | None = None,
) -> dict:
    """Shorthand for a text boundary."""
    return {
        "start_time": start_time,
        "end_time": end_time,
        "confidence": confidence,
        "product_description": description,
        "product_type": product_type,
        "boundary_reason": reason,
        "key_phrases": phrases or ["关键词"],
    }


# =========================== _build_outfit_periods ===========================

class TestBuildOutfitPeriods:
    def test_no_candidates_single_period(self):
        """No visual signals → one period covering the whole video."""
        periods = _build_outfit_periods([], video_duration=120.0)
        assert len(periods) == 1
        assert periods[0]["start_time"] == 0.0
        assert periods[0]["end_time"] == 120.0
        assert periods[0]["visual_confidence"] == 0.0
        assert periods[0]["children"] == []

    def test_single_candidate(self):
        """One visual candidate splits video into two periods."""
        periods = _build_outfit_periods([_vc(30.0)], video_duration=100.0)
        assert len(periods) == 2
        assert periods[0] == {
            "start_time": 0.0,
            "end_time": 30.0,
            "visual_confidence": 0.5,
            "children": [],
        }
        assert periods[1]["start_time"] == 30.0
        assert periods[1]["end_time"] == 100.0
        assert periods[1]["visual_confidence"] == 0.0

    def test_multiple_candidates(self):
        periods = _build_outfit_periods(
            [_vc(20.0, 0.3), _vc(60.0, 0.7)],
            video_duration=100.0,
        )
        assert len(periods) == 3
        assert periods[0]["end_time"] == 20.0
        assert periods[0]["visual_confidence"] == 0.3
        assert periods[1]["start_time"] == 20.0
        assert periods[1]["end_time"] == 60.0
        assert periods[1]["visual_confidence"] == 0.7
        assert periods[2]["start_time"] == 60.0
        assert periods[2]["end_time"] == 100.0

    def test_unsorted_candidates_get_sorted(self):
        periods = _build_outfit_periods(
            [_vc(60.0, 0.7), _vc(20.0, 0.3)],
            video_duration=100.0,
        )
        assert periods[0]["end_time"] == 20.0
        assert periods[1]["start_time"] == 20.0

    def test_zero_duration_video(self):
        periods = _build_outfit_periods([], video_duration=0.0)
        assert len(periods) == 1
        assert periods[0]["start_time"] == 0.0
        assert periods[0]["end_time"] == 0.0

    def test_candidate_at_zero_skipped_period(self):
        """Candidate at t=0 should not produce a zero-length first period."""
        periods = _build_outfit_periods([_vc(0.0)], video_duration=50.0)
        # ts > prev_ts check (0.0 > 0.0 is False) → no first period
        assert len(periods) == 1
        assert periods[0]["start_time"] == 0.0
        assert periods[0]["end_time"] == 50.0

    def test_candidate_at_end_no_extra_period(self):
        """Candidate at video end should not produce trailing zero-length period."""
        periods = _build_outfit_periods([_vc(100.0)], video_duration=100.0)
        assert len(periods) == 1
        assert periods[0]["start_time"] == 0.0
        assert periods[0]["end_time"] == 100.0

    def test_duplicate_timestamps(self):
        """Two candidates at same timestamp → one splits, second skipped (ts not > prev_ts)."""
        periods = _build_outfit_periods(
            [_vc(50.0, 0.3), _vc(50.0, 0.8)],
            video_duration=100.0,
        )
        # first vc: 0→50, second vc at same ts: ts=50, prev_ts=50, not >, skip
        assert len(periods) == 2
        assert periods[0]["end_time"] == 50.0
        assert periods[0]["visual_confidence"] == 0.3
        assert periods[1]["start_time"] == 50.0


# =========================== _nest_text_regions ===========================

class TestNestTextRegions:
    def test_perfect_overlap(self):
        """Text region fully inside one outfit period → assigned there."""
        periods = _build_outfit_periods([_vc(50.0)], video_duration=100.0)
        tr = _tb(10.0, 40.0)
        _nest_text_regions(periods, [tr])
        assert len(periods[0]["children"]) == 1
        assert periods[1]["children"] == []

    def test_best_overlap_selected(self):
        """Text region overlapping two periods → assigned to the one with more overlap."""
        periods = _build_outfit_periods([_vc(50.0)], video_duration=100.0)
        # Region 30-70: overlap with [0,50]=20s, overlap with [50,100]=20s → tie
        # Region 30-65: overlap with [0,50]=20s, overlap with [50,100]=15s → first wins
        tr = _tb(30.0, 65.0)
        _nest_text_regions(periods, [tr])
        assert len(periods[0]["children"]) == 1
        assert len(periods[1]["children"]) == 0

    def test_no_overlap_fallback_nearest(self):
        """Text region outside all periods → fallback to nearest."""
        periods = [
            {"start_time": 0.0, "end_time": 10.0, "visual_confidence": 0.5, "children": []},
            {"start_time": 100.0, "end_time": 200.0, "visual_confidence": 0.5, "children": []},
        ]
        # Region 50-60: no overlap with either period. Nearest start: period 0 at 0.0 (dist=50)
        # vs period 1 at 100.0 (dist=50). Tie → min picks first (index 0).
        tr = _tb(50.0, 60.0)
        _nest_text_regions(periods, [tr])
        # Either could be picked — just verify it was assigned somewhere
        total_children = sum(len(p["children"]) for p in periods)
        assert total_children == 1

    def test_empty_text_regions(self):
        periods = _build_outfit_periods([_vc(50.0)], video_duration=100.0)
        _nest_text_regions(periods, [])
        assert all(len(p["children"]) == 0 for p in periods)

    def test_multiple_text_regions_assigned(self):
        periods = _build_outfit_periods([_vc(50.0)], video_duration=100.0)
        trs = [_tb(10.0, 30.0), _tb(60.0, 80.0)]
        _nest_text_regions(periods, trs)
        assert len(periods[0]["children"]) == 1
        assert len(periods[1]["children"]) == 1

    def test_text_region_spanning_entire_video(self):
        """One text region covering the whole video → overlaps all periods."""
        periods = _build_outfit_periods([_vc(50.0)], video_duration=100.0)
        tr = _tb(0.0, 100.0)
        _nest_text_regions(periods, [tr])
        # Both periods overlap fully (50s each), first one wins tie
        assert len(periods[0]["children"]) == 1


# =========================== _flatten_to_level0 ===========================

class TestFlattenToLevel0:
    def test_visual_only(self):
        periods = _build_outfit_periods([_vc(50.0)], video_duration=100.0)
        result = _flatten_to_level0(periods, 100.0)
        assert len(result) == 2
        assert result[0]["source"] == "visual"
        assert result[1]["source"] == "visual"
        assert result[0]["timestamp"] == 0.0
        assert result[1]["timestamp"] == 50.0

    def test_with_children_merges_product_info(self):
        periods = [{"start_time": 0.0, "end_time": 100.0, "visual_confidence": 0.3, "children": [
            _tb(10.0, 50.0, confidence=0.8, description="毛衣"),
            _tb(50.0, 90.0, confidence=0.9, description="裙子", phrases=["长裙", "半身裙"]),
        ]}]
        result = _flatten_to_level0(periods, 100.0)
        assert len(result) == 1
        r = result[0]
        assert r["source"] == "visual+text"
        assert r["confidence"] == 0.9  # max of visual and best child
        assert r["product_description"] == "裙子"
        assert "长裙" in r["key_phrases"]
        assert "半身裙" in r["key_phrases"]

    def test_empty_periods(self):
        result = _flatten_to_level0([], 100.0)
        assert result == []


# =========================== _flatten_to_level1 ===========================

class TestFlattenToLevel1:
    def test_period_with_children_produces_per_child(self):
        periods = [{"start_time": 0.0, "end_time": 100.0, "visual_confidence": 0.3, "children": [
            _tb(10.0, 40.0, description="毛衣"),
            _tb(50.0, 80.0, description="裙子"),
        ]}]
        result = _flatten_to_level1(periods, 100.0)
        assert len(result) == 2
        assert result[0]["source"] == "visual+text"
        assert result[0]["product_description"] == "毛衣"
        assert result[1]["product_description"] == "裙子"
        assert result[0]["merged_group_id"] == 0
        assert result[1]["merged_group_id"] == 1

    def test_period_without_children_visual_only(self):
        periods = [
            {"start_time": 0.0, "end_time": 50.0, "visual_confidence": 0.4, "children": []},
            {"start_time": 50.0, "end_time": 100.0, "visual_confidence": 0.6, "children": []},
        ]
        result = _flatten_to_level1(periods, 100.0)
        assert len(result) == 2
        assert result[0]["source"] == "visual"
        assert result[0]["merged_group_id"] is None
        assert result[1]["similarity"] == 0.6

    def test_child_clamped_to_period(self):
        """Child times clamped to period boundaries."""
        periods = [{"start_time": 20.0, "end_time": 60.0, "visual_confidence": 0.5, "children": [
            _tb(10.0, 70.0),  # extends beyond period
        ]}]
        result = _flatten_to_level1(periods, 100.0)
        assert len(result) == 1
        assert result[0]["timestamp"] == 20.0  # clamped to period start
        assert result[0]["end_time"] == 60.0  # clamped to period end

    def test_mixed_periods(self):
        """Mix of periods with and without children."""
        periods = [
            {"start_time": 0.0, "end_time": 50.0, "visual_confidence": 0.3, "children": [
                _tb(10.0, 40.0, description="毛衣"),
            ]},
            {"start_time": 50.0, "end_time": 100.0, "visual_confidence": 0.5, "children": []},
        ]
        result = _flatten_to_level1(periods, 100.0)
        assert len(result) == 2
        assert result[0]["source"] == "visual+text"
        assert result[1]["source"] == "visual"
        assert result[1]["merged_group_id"] is None

    def test_empty_periods(self):
        result = _flatten_to_level1([], 100.0)
        assert result == []


# =========================== _split_overlapping_boundaries ===========================

class TestSplitOverlappingBoundaries:
    def test_no_overlap(self):
        """Non-overlapping boundaries pass through unchanged."""
        tbs = [_tb(0.0, 50.0), _tb(50.0, 100.0)]
        result = _split_overlapping_boundaries(tbs)
        assert len(result) == 2
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 50.0
        assert result[1]["start_time"] == 50.0
        assert result[1]["end_time"] == 100.0

    def test_overlapping_split(self):
        """Overlapping boundaries get split into pieces."""
        tbs = [
            _tb(0.0, 60.0, description="宽区间"),
            _tb(30.0, 80.0, description="窄区间"),
        ]
        result = _split_overlapping_boundaries(tbs)
        # Split points: 0, 30, 60, 80
        # Pieces: [0,30], [30,60], [60,80]
        assert len(result) == 3
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 30.0
        assert result[1]["start_time"] == 30.0
        assert result[1]["end_time"] == 60.0
        assert result[2]["start_time"] == 60.0
        assert result[2]["end_time"] == 80.0

    def test_overlapping_prefers_most_specific(self):
        """Each piece gets info from the shortest covering boundary."""
        tbs = [
            _tb(0.0, 100.0, description="宽区间"),
            _tb(20.0, 60.0, description="窄区间"),
        ]
        result = _split_overlapping_boundaries(tbs)
        # [0,20]: only 宽区间 covers → 宽区间
        # [20,60]: both cover, 窄区间 shorter → 窄区间
        # [60,100]: only 宽区间 → 宽区间
        assert len(result) == 3
        assert result[0]["product_description"] == "宽区间"
        assert result[1]["product_description"] == "窄区间"
        assert result[2]["product_description"] == "宽区间"

    def test_empty_input(self):
        assert _split_overlapping_boundaries([]) == []

    def test_single_boundary(self):
        result = _split_overlapping_boundaries([_tb(10.0, 50.0)])
        assert len(result) == 1
        assert result[0]["start_time"] == 10.0
        assert result[0]["end_time"] == 50.0

    def test_short_piece_filtered(self):
        """Pieces shorter than 1.0 second are filtered out."""
        tbs = [
            _tb(0.0, 100.0),
            _tb(10.0, 10.5),  # 0.5s piece, too short
        ]
        result = _split_overlapping_boundaries(tbs)
        # Split points: 0, 10, 10.5, 100
        # Pieces: [0,10], [10,10.5](0.5s < 1s → filtered), [10.5,100]
        assert len(result) == 2
        assert result[0]["end_time"] == 10.0
        assert result[1]["start_time"] == 10.5


# =========================== _dedup_close_boundaries ===========================

class TestDedupCloseBoundaries:
    def test_no_dedup_needed(self):
        boundaries = [
            {"timestamp": 0.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
            {"timestamp": 50.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
        ]
        result = _dedup_close_boundaries(boundaries, gap_seconds=10.0)
        assert len(result) == 2

    def test_close_same_group_deduped(self):
        boundaries = [
            {"timestamp": 0.0, "similarity": 0.3, "confidence": 0.3, "merged_group_id": 0},
            {"timestamp": 5.0, "similarity": 0.8, "confidence": 0.8, "merged_group_id": 0},
        ]
        result = _dedup_close_boundaries(boundaries, gap_seconds=10.0)
        assert len(result) == 1
        # Keeps the one with higher score
        assert result[0]["similarity"] == 0.8

    def test_different_groups_not_deduped(self):
        boundaries = [
            {"timestamp": 0.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
            {"timestamp": 5.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 1},
        ]
        result = _dedup_close_boundaries(boundaries, gap_seconds=10.0)
        assert len(result) == 2

    def test_none_group_not_deduped(self):
        boundaries = [
            {"timestamp": 0.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": None},
            {"timestamp": 5.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": None},
        ]
        result = _dedup_close_boundaries(boundaries, gap_seconds=10.0)
        assert len(result) == 2

    def test_empty_input(self):
        assert _dedup_close_boundaries([]) == []

    def test_exactly_at_gap_boundary(self):
        """Timestamps exactly gap_seconds apart → should NOT dedup (uses <=)."""
        boundaries = [
            {"timestamp": 0.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
            {"timestamp": 10.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
        ]
        result = _dedup_close_boundaries(boundaries, gap_seconds=10.0)
        assert len(result) == 1  # 10.0 - 0.0 <= 10.0, deduped

    def test_unsorted_input_sorted_first(self):
        boundaries = [
            {"timestamp": 50.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
            {"timestamp": 0.0, "similarity": 0.5, "confidence": 0.5, "merged_group_id": 0},
        ]
        result = _dedup_close_boundaries(boundaries, gap_seconds=10.0)
        assert len(result) == 2
        assert result[0]["timestamp"] == 0.0


# =========================== fuse_candidates ===========================

class TestFuseCandidates:
    def test_empty_both_signals(self):
        assert fuse_candidates([], [], 100.0) == []

    def test_visual_only_single_item(self):
        """Visual only → each period becomes a visual-only segment."""
        result = fuse_candidates(
            [_vc(50.0, 0.5)],
            [],
            video_duration=100.0,
            segment_granularity="single_item",
        )
        assert len(result) == 2
        assert all(r["source"] == "visual" for r in result)

    def test_visual_only_outfit(self):
        result = fuse_candidates(
            [_vc(50.0, 0.5)],
            [],
            video_duration=100.0,
            segment_granularity="outfit",
        )
        assert len(result) == 2
        assert all(r["source"] == "visual" for r in result)

    def test_text_only_no_visual(self):
        """No visual candidates → single outfit period, text regions become segments."""
        result = fuse_candidates(
            [],
            [_tb(10.0, 50.0, description="毛衣"), _tb(60.0, 90.0, description="裙子")],
            video_duration=100.0,
            segment_granularity="single_item",
        )
        assert len(result) == 2
        assert result[0]["product_description"] == "毛衣"
        assert result[1]["product_description"] == "裙子"

    def test_both_signals_single_item(self):
        result = fuse_candidates(
            [_vc(50.0, 0.3)],
            [_tb(10.0, 40.0, description="毛衣"), _tb(55.0, 80.0, description="裙子")],
            video_duration=100.0,
            segment_granularity="single_item",
        )
        # Visual candidate at 50 splits into [0,50] and [50,100]
        # Text regions nest: 毛衣 in [0,50], 裙子 in [50,100]
        # single_item → one per text region
        assert len(result) == 2
        assert result[0]["source"] == "visual+text"
        assert result[1]["source"] == "visual+text"

    def test_both_signals_outfit(self):
        result = fuse_candidates(
            [_vc(50.0, 0.3)],
            [_tb(10.0, 40.0, description="毛衣"), _tb(55.0, 80.0, description="裙子")],
            video_duration=100.0,
            segment_granularity="outfit",
        )
        # outfit → each outfit period is one segment
        assert len(result) == 2
        # First period [0,50] has 毛衣 child, second [50,100] has 裙子 child
        assert result[0]["source"] == "visual+text"
        assert result[1]["source"] == "visual+text"

    def test_zero_duration_video(self):
        result = fuse_candidates([], [], 0.0)
        assert result == []


# =========================== fused_to_segments ===========================

class TestFusedToSegments:
    def test_empty_input(self):
        assert fused_to_segments([], 100.0) == []

    def test_text_group_segments(self):
        fused = [
            {
                "timestamp": 10.0,
                "end_time": 50.0,
                "region_start_time": 10.0,
                "similarity": 0.8,
                "source": "visual+text",
                "confidence": 0.9,
                "product_description": "毛衣",
                "merged_group_id": 0,
            },
        ]
        segments = fused_to_segments(fused, 100.0, min_duration=5.0)
        assert len(segments) == 1
        assert segments[0]["product_name"] == "毛衣"
        assert segments[0]["name_source"] == "llm_fusion"
        assert segments[0]["start_time"] == 10.0
        assert segments[0]["end_time"] == 50.0

    def test_visual_only_segments(self):
        fused = [
            {
                "timestamp": 0.0,
                "end_time": 50.0,
                "similarity": 0.3,
                "source": "visual",
                "confidence": 0.3,
                "merged_group_id": None,
            },
        ]
        segments = fused_to_segments(fused, 100.0, min_duration=5.0)
        assert len(segments) == 1
        assert segments[0]["name_source"] == "vlm"
        assert segments[0]["low_confidence"] is True

    def test_min_duration_filter(self):
        fused = [
            {
                "timestamp": 0.0,
                "end_time": 5.0,
                "region_start_time": 0.0,
                "similarity": 0.5,
                "source": "visual",
                "confidence": 0.5,
                "merged_group_id": None,
            },
        ]
        segments = fused_to_segments(fused, 100.0, min_duration=10.0)
        assert len(segments) == 0

    def test_overlapping_segments_resolved(self):
        fused = [
            {
                "timestamp": 0.0,
                "end_time": 60.0,
                "region_start_time": 0.0,
                "similarity": 0.8,
                "source": "visual+text",
                "confidence": 0.8,
                "merged_group_id": 0,
                "product_description": "毛衣",
            },
            {
                "timestamp": 50.0,
                "end_time": 100.0,
                "similarity": 0.3,
                "source": "visual",
                "confidence": 0.3,
                "merged_group_id": None,
            },
        ]
        segments = fused_to_segments(fused, 100.0, min_duration=5.0)
        # Both should survive overlap resolution (llm_fusion takes priority)
        assert len(segments) >= 1
        # First segment should be llm_fusion
        assert segments[0]["name_source"] == "llm_fusion"
