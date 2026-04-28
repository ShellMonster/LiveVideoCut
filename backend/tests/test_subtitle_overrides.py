from app.tasks.stages.process_clips import _collect_clip_subtitle_segments


def test_collect_clip_subtitle_segments_sanitizes_legacy_overrides():
    segment = {
        "start_time": 10,
        "end_time": 20,
        "subtitle_overrides": [
            {
                "start_time": 10,
                "end_time": 12,
                "text": "{\\pos(0,0)} 这件衣服很好看",
            }
        ],
    }

    result = _collect_clip_subtitle_segments(segment, [])

    assert result == [
        {"start_time": 0.0, "end_time": 2.0, "text": "这件衣服很好看"}
    ]
