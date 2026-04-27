"""Tests for boundary_snapper — snapping segment boundaries to ASR sentence edges."""

import copy

from app.services.boundary_snapper import snap_to_sentence_boundaries


def _sentence(text: str, start: float, end: float) -> dict:
    return {"text": text, "start_time": start, "end_time": end}


def _segment(start: float, end: float, **extra: float | str) -> dict:
    seg: dict = {"start_time": start, "end_time": end}
    seg.update(extra)
    return seg


# =========================== snap_to_sentence_boundaries ===========================

class TestSnapToSentenceBoundaries:
    def test_snap_start_forward(self):
        """Start snaps to first sentence with start_time >= segment start."""
        segs = [_segment(5.0, 60.0)]
        transcript = [
            _sentence("你好", 0.0, 3.0),
            _sentence("这个毛衣", 7.0, 10.0),
            _sentence("很好看", 12.0, 50.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert result[0]["start_time"] == 7.0
        assert result[0]["end_time"] == 50.0

    def test_snap_end_backward(self):
        """End snaps to last sentence with end_time <= segment end."""
        segs = [_segment(0.0, 12.0)]
        transcript = [
            _sentence("你好", 0.0, 3.0),
            _sentence("这个毛衣", 5.0, 8.0),
            _sentence("很好看", 10.0, 13.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 8.0

    def test_perfect_alignment(self):
        """Segment already aligned → no change."""
        segs = [_segment(5.0, 15.0)]
        transcript = [
            _sentence("你好", 5.0, 8.0),
            _sentence("毛衣", 8.0, 12.0),
            _sentence("好看", 12.0, 15.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript)
        assert result[0]["start_time"] == 5.0
        assert result[0]["end_time"] == 15.0

    def test_segment_within_one_sentence(self):
        """Segment within one long sentence snaps start to that sentence start."""
        segs = [_segment(3.0, 7.0)]
        transcript = [
            _sentence("这是一段很长的话", 0.0, 10.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        # No sentence has start >= 3.0, so start stays 3.0
        # End: sentence end 10.0 > 7.0, no sentence end <= 7.0, end stays 7.0
        # Duration 4.0 < min_duration 5.0 → revert
        assert result[0]["start_time"] == 3.0
        assert result[0]["end_time"] == 7.0

    def test_orphan_trim_leading(self):
        """Single-char sentence at start gets trimmed if enough duration remains."""
        segs = [_segment(0.0, 20.0)]
        transcript = [
            _sentence("的", 0.0, 0.5),
            _sentence("这个毛衣好看", 2.0, 10.0),
            _sentence("真的不错", 10.0, 15.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert result[0]["start_time"] == 2.0

    def test_orphan_trim_trailing(self):
        """Single-char sentence at end gets trimmed if enough duration remains."""
        segs = [_segment(0.0, 20.0)]
        transcript = [
            _sentence("这个毛衣", 0.0, 5.0),
            _sentence("很好看", 5.0, 10.0),
            _sentence("了", 18.0, 19.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert result[0]["end_time"] == 10.0

    def test_orphan_not_trimmed_if_only_sentence(self):
        """Single orphan that is the only sentence → not trimmed (len(inner)==1 check)."""
        segs = [_segment(0.0, 10.0)]
        transcript = [
            _sentence("的", 0.0, 10.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript)
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 10.0

    def test_min_duration_revert(self):
        """Snapped duration < min_duration → revert to original."""
        segs = [_segment(5.0, 15.0)]
        transcript = [
            _sentence("你好", 13.0, 14.0),
        ]
        # Snap start → 13.0, snap end → 14.0, duration=1.0 < 10.0 → revert
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=10.0)
        assert result[0]["start_time"] == 5.0
        assert result[0]["end_time"] == 15.0

    def test_empty_segments(self):
        assert snap_to_sentence_boundaries([], [_sentence("你好", 0.0, 3.0)]) == []

    def test_empty_transcript(self):
        segs = [_segment(0.0, 10.0)]
        result = snap_to_sentence_boundaries(segs, [])
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 10.0

    def test_both_empty(self):
        assert snap_to_sentence_boundaries([], []) == []

    def test_multiple_segments(self):
        segs = [_segment(0.0, 10.0), _segment(10.0, 30.0)]
        transcript = [
            _sentence("第一段", 0.0, 5.0),
            _sentence("第二段", 5.0, 10.0),
            _sentence("第三段", 12.0, 25.0),
        ]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 10.0
        assert result[1]["start_time"] == 12.0
        assert result[1]["end_time"] == 25.0

    def test_mutates_in_place(self):
        segs = [_segment(5.0, 60.0)]
        original_id = id(segs[0])
        transcript = [_sentence("你好", 7.0, 50.0)]
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert id(result[0]) == original_id
        assert segs[0]["start_time"] == 7.0

    def test_extra_segment_fields_preserved(self):
        segs = [_segment(5.0, 30.0, product_name="毛衣", confidence=0.9)]
        transcript = [_sentence("你好", 5.0, 30.0)]
        result = snap_to_sentence_boundaries(segs, transcript)
        assert result[0]["product_name"] == "毛衣"
        assert result[0]["confidence"] == 0.9

    def test_orphan_trim_respects_min_duration(self):
        """Orphan trim skipped if it would make duration < min_duration."""
        segs = [_segment(0.0, 10.0)]
        transcript = [
            _sentence("的", 0.0, 1.0),
            _sentence("毛衣", 2.0, 9.9),
        ]
        # After leading trim: start=2.0, end=9.9 → duration=7.9 >= 5.0 OK
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        assert result[0]["start_time"] == 2.0
        assert result[0]["end_time"] == 9.9

    def test_orphan_trim_reverts_if_too_short(self):
        """Orphan trim would make duration < min_duration → trim skipped."""
        segs = [_segment(0.0, 10.0)]
        transcript = [
            _sentence("的", 0.0, 6.0),
            _sentence("毛衣", 6.5, 10.0),
        ]
        # After leading trim: start=6.5, end=10.0 → duration=3.5
        # min_duration=5.0 → trim would violate, so orphan NOT trimmed
        result = snap_to_sentence_boundaries(segs, transcript, min_duration=5.0)
        # The orphan trim check: (new_end - candidate_start) >= min_duration
        # candidate_start = 6.5, new_end = 10.0 → 3.5 < 5.0 → skip trim
        assert result[0]["start_time"] == 0.0
