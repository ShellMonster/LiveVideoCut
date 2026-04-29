from app.services.sensitive_filter import (
    compute_sensitive_cut_ranges,
    find_sensitive_hits,
    merge_cut_ranges,
    remove_sensitive_subtitle_segments,
)


def test_find_sensitive_hits_contains_match():
    segments = [
        {"text": "这里有联系方式", "start_time": 1.0, "end_time": 3.0},
        {"text": "正常讲解", "start_time": 3.0, "end_time": 5.0},
    ]

    hits = find_sensitive_hits(segments, ["联系方式"])

    assert len(hits) == 1
    assert hits[0]["matched_words"] == ["联系方式"]


def test_compute_sensitive_cut_ranges_uses_whole_subtitle_segment():
    segments = [
        {"text": "这里有联系方式", "start_time": 1.0, "end_time": 3.0},
    ]

    ranges = compute_sensitive_cut_ranges(segments, ["联系方式"], padding=0.1)

    assert ranges == [{"start_time": 0.9, "end_time": 3.1, "text": "联系方式"}]


def test_remove_sensitive_subtitle_segments():
    segments = [
        {"text": "这里有联系方式", "start_time": 1.0, "end_time": 3.0},
        {"text": "正常讲解", "start_time": 3.0, "end_time": 5.0},
    ]

    result = remove_sensitive_subtitle_segments(segments, ["联系方式"])

    assert result == [segments[1]]


def test_merge_cut_ranges_combines_overlaps():
    result = merge_cut_ranges(
        [{"start_time": 1.0, "end_time": 2.0, "text": "嗯"}],
        [{"start_time": 1.9, "end_time": 3.0, "text": "联系方式"}],
    )

    assert result == [{"start_time": 1.0, "end_time": 3.0, "text": "嗯、联系方式"}]
