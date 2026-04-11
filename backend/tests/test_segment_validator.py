"""Tests for SegmentValidator — pure logic, no external dependencies."""

from app.services.segment_validator import SegmentValidator


class TestDurationValidation:
    def test_valid_120s_segment_kept(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_name": "白色连衣裙",
            }
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 1
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 120.0

    def test_30s_segment_too_short_removed(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 30.0,
                "product_name": "短片段",
            }
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 0

    def test_700s_segment_truncated_to_600s(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 700.0,
                "product_name": "超长片段",
            }
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 1
        assert result[0]["end_time"] == 600.0

    def test_segment_beyond_video_duration_clipped(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 3500.0,
                "end_time": 3700.0,
                "product_name": "超出范围",
            }
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 1
        assert result[0]["end_time"] == 3600.0
        # 截断后 3600 - 3500 = 100s > 60s，保留
        assert result[0]["start_time"] == 3500.0

    def test_segment_beyond_video_too_short_after_clip(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 3550.0,
                "end_time": 3700.0,
                "product_name": "超出范围且短",
            }
        ]

        result = validator.validate(segments, video_duration=3600.0)
        # 截断后 3600 - 3550 = 50s < 60s，移除
        assert len(result) == 0


class TestDeduplication:
    def test_same_name_within_5min_deduplicated(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_name": "白色连衣裙",
            },
            {
                "start_time": 180.0,
                "end_time": 300.0,
                "product_name": "白色连衣裙",
            },
        ]

        result = validator.validate(segments, video_duration=3600.0)
        # 两个同名片段在 300s 窗口内，只保留第一个
        assert len(result) == 1
        assert result[0]["start_time"] == 0.0

    def test_same_name_beyond_5min_both_kept(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_name": "白色连衣裙",
            },
            {
                "start_time": 400.0,
                "end_time": 520.0,
                "product_name": "白色连衣裙",
            },
        ]

        result = validator.validate(segments, video_duration=3600.0)
        # 400s > 300s 窗口，两个都保留
        assert len(result) == 2

    def test_different_names_all_kept(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_name": "白色连衣裙",
            },
            {
                "start_time": 60.0,
                "end_time": 180.0,
                "product_name": "黑色T恤",
            },
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 2


class TestEdgeCases:
    def test_empty_segments_returns_empty(self):
        validator = SegmentValidator()
        result = validator.validate([], video_duration=3600.0)
        assert result == []

    def test_negative_start_time_clamped(self):
        validator = SegmentValidator()

        segments = [
            {
                "start_time": -10.0,
                "end_time": 120.0,
                "product_name": "负时间",
            }
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 1
        assert result[0]["start_time"] == 0.0

    def test_mixed_valid_and_invalid(self):
        validator = SegmentValidator()

        segments = [
            {"start_time": 0.0, "end_time": 30.0, "product_name": "太短"},
            {"start_time": 100.0, "end_time": 250.0, "product_name": "正常"},
            {"start_time": 300.0, "end_time": 1000.0, "product_name": "太长"},
        ]

        result = validator.validate(segments, video_duration=3600.0)
        assert len(result) == 2
        assert result[0]["product_name"] == "正常"
        assert result[1]["end_time"] == 900.0  # 300 + 600


class TestPointExpansion:
    def test_expands_change_points_into_exportable_segments(self):
        validator = SegmentValidator()

        confirmed_points = [
            {"start_time": 65.233, "end_time": 65.233, "product_name": "蓝色连衣裙"},
            {"start_time": 246.799, "end_time": 246.799, "product_name": "裤子"},
        ]

        result = validator.validate(confirmed_points, video_duration=283.96)

        assert len(result) == 2
        assert result[0]["start_time"] == 65.233
        assert result[0]["end_time"] == 246.799
        # 最后一个点位会回补成至少 60 秒的可导出片段，并贴合视频末尾
        assert result[1]["end_time"] == 283.96
        assert round(result[1]["start_time"], 2) == round(283.96 - 60.0, 2)
