"""Tests for TranscriptMerger — pure logic, no external dependencies."""

from app.services.transcript_merger import TranscriptMerger


class TestMergeThreeChunks:
    def test_correct_merge_with_offsets(self):
        merger = TranscriptMerger()

        chunk1 = [
            {"text": "开场白", "start_time": 0.0, "end_time": 5.0},
            {"text": "介绍商品", "start_time": 5.0, "end_time": 120.0},
            {"text": "重叠前", "start_time": 1795.0, "end_time": 1798.0},
        ]
        chunk2 = [
            {"text": "重叠后", "start_time": 0.0, "end_time": 3.0},
            {"text": "继续介绍", "start_time": 10.0, "end_time": 200.0},
            {"text": "第二段重叠前", "start_time": 1795.0, "end_time": 1798.0},
        ]
        chunk3 = [
            {"text": "第三段开始", "start_time": 0.0, "end_time": 5.0},
            {"text": "结尾", "start_time": 100.0, "end_time": 300.0},
        ]

        offsets = [0, 1800, 3600]
        result = merger.merge([chunk1, chunk2, chunk3], offsets, overlap=3.0)

        assert len(result) > 0
        # 结果应该按 start_time 排序
        for i in range(len(result) - 1):
            assert result[i]["start_time"] <= result[i + 1]["start_time"]

    def test_overlap_deduplication_keeps_later_chunk(self):
        merger = TranscriptMerger()

        # chunk1 在重叠区域 [1797, 1800) 有一个片段
        chunk1 = [
            {"text": "正常片段", "start_time": 100.0, "end_time": 200.0},
            {"text": "重叠区域_旧", "start_time": 1798.0, "end_time": 1799.0},
        ]
        # chunk2 在重叠区域也有片段
        chunk2 = [
            {"text": "重叠区域_新", "start_time": 0.0, "end_time": 2.0},
            {"text": "后续内容", "start_time": 100.0, "end_time": 200.0},
        ]

        offsets = [0, 1800]
        result = merger.merge([chunk1, chunk2], offsets, overlap=3.0)

        # 重叠区域 [1797, 1800): chunk1 的 1798.0 在此范围内，应被跳过
        # chunk2 的 0.0 + offset 1800 = 1800.0，不在 [1797, 1800) 范围内，保留
        texts = [r["text"] for r in result]
        assert "重叠区域_旧" not in texts
        assert "重叠区域_新" in texts


class TestMergeEdgeCases:
    def test_empty_chunks_returns_empty(self):
        merger = TranscriptMerger()
        result = merger.merge([], [], overlap=3.0)
        assert result == []

    def test_single_chunk_no_modification(self):
        merger = TranscriptMerger()

        chunk = [
            {"text": "片段A", "start_time": 0.0, "end_time": 10.0},
            {"text": "片段B", "start_time": 10.0, "end_time": 20.0},
        ]

        result = merger.merge([chunk], [0], overlap=3.0)

        assert len(result) == 2
        assert result[0]["text"] == "片段A"
        assert result[1]["text"] == "片段B"

    def test_empty_chunk_segments_skipped(self):
        merger = TranscriptMerger()

        chunk1 = [{"text": "内容", "start_time": 0.0, "end_time": 10.0}]
        chunk2 = []  # 空块
        chunk3 = [{"text": "更多内容", "start_time": 0.0, "end_time": 10.0}]

        result = merger.merge([chunk1, chunk2, chunk3], [0, 1800, 3600], overlap=3.0)
        assert len(result) == 2
