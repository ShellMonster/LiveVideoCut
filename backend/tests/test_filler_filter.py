"""Tests for filler_filter — filler word detection, subtitle filtering, cut range computation."""

from app.services.filler_filter import (
    FILLER_ALL,
    FILLER_SAFE,
    FILLER_SENTENCE_EDGE,
    compute_filler_cut_ranges,
    filter_subtitle_words,
    is_filler,
)


def _word(text: str, begin: float = 0.0, end: float = 0.0) -> dict:
    return {"text": text, "start_time": begin, "end_time": end}


def _seg(text: str, start: float = 0.0, end: float = 0.0, words: list[dict] | None = None) -> dict:
    return {"text": text, "start_time": start, "end_time": end, "words": words or []}


# =========================== is_filler ===========================

class TestIsFiller:
    def test_safe_filler(self):
        assert is_filler("嗯") is True
        assert is_filler("嗯嗯") is True
        assert is_filler("啊啊") is True

    def test_sentence_edge_filler(self):
        assert is_filler("就是说") is True
        assert is_filler("你知道吗") is True

    def test_non_filler(self):
        assert is_filler("毛衣") is False
        assert is_filler("这个") is False
        assert is_filler("") is False

    def test_stripped_matching(self):
        assert is_filler("  嗯  ") is True
        assert is_filler(" 嗯嗯 ") is True

    def test_custom_set(self):
        custom = {"嗯", "啊"}
        assert is_filler("嗯", custom) is True
        assert is_filler("就是说", custom) is False

    def test_none_set_uses_all(self):
        assert is_filler("嗯") is True
        assert is_filler("就是说") is True

    def test_filler_safe_subset_of_all(self):
        assert FILLER_SAFE <= FILLER_ALL

    def test_filler_sentence_edge_subset_of_all(self):
        assert FILLER_SENTENCE_EDGE <= FILLER_ALL

    def test_safe_and_edge_disjoint(self):
        assert FILLER_SAFE & FILLER_SENTENCE_EDGE == set()


# =========================== filter_subtitle_words ===========================

class TestFilterSubtitleWords:
    def test_removes_filler_words(self):
        segs = [
            _seg("嗯这个毛衣", 0.0, 5.0, [
                _word("嗯", 0.0, 0.5),
                _word("这", 0.5, 0.8),
                _word("个", 0.8, 1.0),
                _word("毛", 1.0, 1.3),
                _word("衣", 1.3, 1.5),
            ]),
        ]
        result = filter_subtitle_words(segs)
        assert len(result) == 1
        assert "嗯" not in result[0]["text"]
        assert "这个毛衣" == result[0]["text"]
        assert len(result[0]["words"]) == 4

    def test_removes_empty_segments(self):
        segs = [
            _seg("嗯嗯", 0.0, 1.0, [_word("嗯嗯", 0.0, 1.0)]),
            _seg("毛衣好看", 1.0, 3.0, [_word("毛衣", 1.0, 2.0), _word("好看", 2.0, 3.0)]),
        ]
        result = filter_subtitle_words(segs)
        assert len(result) == 1
        assert result[0]["text"] == "毛衣好看"

    def test_no_words_segment_text_match(self):
        """Segment without words falls back to full-text match."""
        segs = [
            {"text": "嗯嗯", "start_time": 0.0, "end_time": 1.0},
            {"text": "毛衣好看", "start_time": 1.0, "end_time": 3.0},
        ]
        result = filter_subtitle_words(segs)
        assert len(result) == 1
        assert result[0]["text"] == "毛衣好看"

    def test_no_words_segment_non_filler_kept(self):
        segs = [
            {"text": "毛衣好看", "start_time": 0.0, "end_time": 3.0},
        ]
        result = filter_subtitle_words(segs)
        assert len(result) == 1

    def test_all_filler_removed(self):
        segs = [
            _seg("嗯啊", 0.0, 2.0, [_word("嗯", 0.0, 1.0), _word("啊", 1.0, 2.0)]),
            _seg("呃", 2.0, 3.0, [_word("呃", 2.0, 3.0)]),
        ]
        result = filter_subtitle_words(segs)
        assert len(result) == 0

    def test_preserves_non_filler_timestamps(self):
        segs = [
            _seg("嗯毛衣", 0.0, 2.0, [
                _word("嗯", 0.0, 0.5),
                _word("毛衣", 0.5, 2.0),
            ]),
        ]
        result = filter_subtitle_words(segs)
        assert result[0]["words"][0]["start_time"] == 0.5
        assert result[0]["words"][0]["end_time"] == 2.0

    def test_custom_filler_set(self):
        custom = {"嗯"}
        segs = [
            _seg("嗯就是说", 0.0, 3.0, [
                _word("嗯", 0.0, 1.0),
                _word("就是说", 1.0, 3.0),
            ]),
        ]
        result = filter_subtitle_words(segs, filler_set=custom)
        assert len(result) == 1
        assert "就是说" in result[0]["text"]

    def test_empty_input(self):
        assert filter_subtitle_words([]) == []

    def test_segment_without_words_key(self):
        """Segment with no 'words' key at all."""
        segs = [{"text": "嗯嗯", "start_time": 0.0, "end_time": 1.0}]
        result = filter_subtitle_words(segs)
        assert len(result) == 0

    def test_sentence_edge_filler_removed(self):
        segs = [
            _seg("就是说这个毛衣", 0.0, 3.0, [
                _word("就是说", 0.0, 1.0),
                _word("这", 1.0, 1.5),
                _word("个", 1.5, 1.8),
                _word("毛", 1.8, 2.0),
                _word("衣", 2.0, 2.5),
            ]),
        ]
        result = filter_subtitle_words(segs)
        assert len(result) == 1
        assert "就是说" not in result[0]["text"]
        assert "这个毛衣" == result[0]["text"]


# =========================== compute_filler_cut_ranges ===========================

class TestComputeFillerCutRanges:
    def test_single_filler(self):
        segs = [
            _seg("嗯毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.5),
                _word("毛衣", 0.5, 3.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs)
        assert len(result) == 1
        assert result[0]["text"] == "嗯"
        assert result[0]["start_time"] <= 0.5
        assert result[0]["end_time"] >= 0.5

    def test_adjacent_fillers_merged(self):
        segs = [
            _seg("嗯啊毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.3),
                _word("啊", 0.3, 0.6),
                _word("毛衣", 0.6, 3.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs, merge_gap=0.5)
        assert len(result) == 1
        assert "嗯" in result[0]["text"]
        assert "啊" in result[0]["text"]

    def test_non_adjacent_fillers_separate(self):
        segs = [
            _seg("嗯毛衣啊好看", 0.0, 5.0, [
                _word("嗯", 0.0, 0.3),
                _word("毛衣", 0.3, 2.0),
                _word("啊", 2.0, 2.3),
                _word("好看", 2.3, 5.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs, merge_gap=0.2)
        assert len(result) == 2

    def test_padding_limited_by_non_filler(self):
        segs = [
            _seg("嗯毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.3),
                _word("毛衣", 0.3, 3.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs, padding=0.5)
        # Start padded back but non-filler "毛衣" at 0.3 limits start
        assert result[0]["start_time"] < 0.3
        # Padding forward from 0.3 → 0.8, but "毛衣" starts at 0.3, so end limited to 0.3
        assert result[0]["end_time"] <= 0.3 + 0.5 + 0.01  # small tolerance

    def test_min_cut_duration_filter(self):
        segs = [
            _seg("嗯毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.1),
                _word("毛衣", 0.1, 3.0),
            ]),
        ]
        # Filler is only 0.1s, with default min_cut_duration=0.1 it might pass
        # Set higher to force filter
        result = compute_filler_cut_ranges(segs, min_cut_duration=1.0, padding=0.0)
        assert len(result) == 0

    def test_empty_input(self):
        assert compute_filler_cut_ranges([]) == []

    def test_no_filler_words(self):
        segs = [
            _seg("毛衣好看", 0.0, 3.0, [
                _word("毛衣", 0.0, 1.5),
                _word("好看", 1.5, 3.0),
            ]),
        ]
        assert compute_filler_cut_ranges(segs) == []

    def test_no_words_segments_skipped(self):
        segs = [
            {"text": "嗯嗯", "start_time": 0.0, "end_time": 1.0},
        ]
        assert compute_filler_cut_ranges(segs) == []

    def test_padding_not_negative_start(self):
        segs = [
            _seg("嗯毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.2),
                _word("毛衣", 0.2, 3.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs, padding=1.0)
        assert result[0]["start_time"] >= 0.0

    def test_cut_range_has_expected_keys(self):
        segs = [
            _seg("嗯毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.3),
                _word("毛衣", 0.3, 3.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs)
        assert len(result) == 1
        for key in ("start_time", "end_time", "text"):
            assert key in result[0]

    def test_values_are_rounded(self):
        segs = [
            _seg("嗯毛衣", 0.0, 3.0, [
                _word("嗯", 0.0, 0.333),
                _word("毛衣", 0.333, 3.0),
            ]),
        ]
        result = compute_filler_cut_ranges(segs)
        # Check rounded to 4 decimal places
        for r in result:
            assert r["start_time"] == round(r["start_time"], 4)
            assert r["end_time"] == round(r["end_time"], 4)
