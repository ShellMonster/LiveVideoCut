"""Transcript merger — offset correction and overlap deduplication for chunked ASR results."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TranscriptMerger:
    """Merges transcript chunks with offset correction and overlap deduplication.

    When audio is split into chunks with overlap, the overlap region will have
    duplicate transcripts. This merger keeps the later chunk's result for overlap
    regions (typically more accurate due to more context).
    """

    def merge(
        self,
        chunks: list[list[dict[str, Any]]],
        offsets: list[float],
        overlap: float = 3.0,
    ) -> list[dict[str, Any]]:
        """Merge multiple transcript chunks.

        Args:
            chunks: List of transcript segment lists, one per chunk.
            offsets: Time offsets for each chunk (e.g., [0, 1800, 3600]).
            overlap: Overlap duration in seconds between chunks.

        Returns:
            Merged and sorted transcript segments: [{text, start_time, end_time}]
        """
        if not chunks:
            return []

        if len(chunks) == 1:
            return sorted(chunks[0], key=lambda s: s.get("start_time", 0.0))

        # 为每个片段标记来源 chunk 索引
        tagged = []
        for chunk_idx, (chunk_segments, offset) in enumerate(zip(chunks, offsets)):
            for seg in chunk_segments:
                tagged.append(
                    {
                        "text": seg.get("text", ""),
                        "start_time": seg.get("start_time", 0.0),
                        "end_time": seg.get("end_time", 0.0),
                        "words": seg.get("words", []),
                        "_chunk_idx": chunk_idx,
                    }
                )

        # 按开始时间排序
        tagged.sort(key=lambda s: (s["start_time"], s["_chunk_idx"]))

        # 计算每个 chunk 的重叠区域边界
        # chunk[i] 的重叠区域: [offsets[i] + chunk_duration - overlap, offsets[i] + chunk_duration]
        # 简化: 对于相邻 chunk i 和 i+1, 重叠区域是 [offsets[i+1] - overlap, offsets[i+1]]
        overlap_boundaries = []
        for i in range(len(offsets) - 1):
            boundary_start = offsets[i + 1] - overlap
            boundary_end = offsets[i + 1]
            overlap_boundaries.append((boundary_start, boundary_end, i, i + 1))

        # 去重: 在重叠区域内，保留后一个 chunk 的结果
        result = []
        for seg in tagged:
            in_overlap = False
            should_skip = False

            for (
                boundary_start,
                boundary_end,
                earlier_idx,
                later_idx,
            ) in overlap_boundaries:
                if boundary_start <= seg["start_time"] < boundary_end:
                    in_overlap = True
                    # 在重叠区域内，只保留后一个 chunk 的结果
                    if seg["_chunk_idx"] == earlier_idx:
                        should_skip = True
                    break

            if not should_skip:
                clean_seg = {
                    "text": seg["text"],
                    "start_time": seg["start_time"],
                    "end_time": seg["end_time"],
                }
                if seg.get("words"):
                    clean_seg["words"] = seg["words"]
                result.append(clean_seg)

        result.sort(key=lambda s: s["start_time"])
        return result
