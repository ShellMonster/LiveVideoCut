"""Product name matcher — conflict resolution: VLM > ASR > VLM-description fallback."""

import logging
import re

logger = logging.getLogger(__name__)

# 直播场景中常见的商品相关关键词模式
PRODUCT_PATTERNS = [
    r"这款(.{2,20}?)(?:很|特别|真的|非常|超)",
    r"看一下这(?:件|个|条)(.{2,20})",
    r"这(?:件|个|条)(.{2,20})(?:是|的|很)",
    r"(.{2,15})(?:面料|材质|版型|颜色)",
    r"(.{2,15})(?:只要|仅需|秒杀|福利)",
]

VAGUE_PHRASES = {"看这一件", "看一下", "这个", "这一件", "来", "看一下这个", "看看"}


class ProductNameMatcher:
    """Matches product names using conflict resolution: VLM > ASR > VLM-description fallback.

    Priority chain:
    1. VLM 5-dimension description (type+color+style) as primary name
    2. ASR text in corresponding time range for more specific name
    3. VLM description concatenation as fallback
    """

    def match(self, segments: list[dict], transcript: list[dict]) -> list[dict]:
        """For each segment, determine the best product name.

        Args:
            segments: Confirmed segments with product_info from VLM.
            transcript: Full ASR transcript with timestamps.

        Returns:
            Segments with enriched product_name field.
        """
        if not segments:
            return []

        enriched = []
        for seg in segments:
            product_info = seg.get("product_info", {})
            start_time = seg.get("start_time", 0.0)
            end_time = seg.get("end_time", 0.0)

            vlm_name = self._generate_vlm_name(product_info)
            asr_name = self._search_asr_text(start_time, end_time, transcript)

            # 冲突解决: VLM识别 > ASR提取 > VLM描述兜底
            if (
                asr_name
                and asr_name not in VAGUE_PHRASES
                and len(asr_name) > len(vlm_name)
            ):
                # ASR 提供了更具体的名称
                final_name = asr_name
                name_source = "asr"
            else:
                final_name = vlm_name
                name_source = "vlm"

            enriched_seg = dict(seg)
            enriched_seg["product_name"] = final_name
            enriched_seg["name_source"] = name_source
            enriched.append(enriched_seg)

        return enriched

    def _search_asr_text(
        self, start_time: float, end_time: float, transcript: list[dict]
    ) -> str:
        """Search ASR text in time range for product-related keywords.

        Returns the most specific product name found, or empty string.
        """
        relevant_texts = []
        for seg in transcript:
            seg_start = seg.get("start_time", 0.0)
            seg_end = seg.get("end_time", 0.0)
            # 时间范围有交集
            if seg_start <= end_time and seg_end >= start_time:
                text = seg.get("text", "").strip()
                if text:
                    relevant_texts.append(text)

        combined_text = " ".join(relevant_texts)

        if not combined_text:
            return ""

        # 尝试匹配商品相关模式
        for pattern in PRODUCT_PATTERNS:
            match = re.search(pattern, combined_text)
            if match:
                candidate = match.group(1).strip()
                # 过滤太短或太长的结果
                if 2 <= len(candidate) <= 20:
                    return candidate

        return ""

    def _generate_vlm_name(self, product_info: dict) -> str:
        """Generate name from VLM description: '{color} {style} {type}'.

        Returns '未命名商品' if product_info is empty.
        """
        if not product_info:
            return "未命名商品"

        color = product_info.get("color", "").strip()
        style = product_info.get("style", "").strip()
        ptype = product_info.get("type", "").strip()

        parts = [p for p in [color, style, ptype] if p]

        if not parts:
            description = product_info.get("description", "").strip()
            if description:
                return description
            return "未命名商品"

        return " ".join(parts)
