"""Tests for ProductNameMatcher — pure logic, no external dependencies."""

from app.services.product_matcher import ProductNameMatcher


class TestVLMNameGeneration:
    def test_vlm_name_used_when_asr_has_no_match(self):
        matcher = ProductNameMatcher()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_info": {
                    "type": "连衣裙",
                    "color": "白色",
                    "style": "A字裙",
                },
            }
        ]
        transcript = [
            {"text": "大家好欢迎来到直播间", "start_time": 0.0, "end_time": 10.0},
        ]

        result = matcher.match(segments, transcript)
        assert len(result) == 1
        assert result[0]["product_name"] == "白色 A字裙 连衣裙"
        assert result[0]["name_source"] == "vlm"

    def test_empty_product_info_returns_default(self):
        matcher = ProductNameMatcher()

        segments = [{"start_time": 0.0, "end_time": 120.0, "product_info": {}}]
        transcript = []

        result = matcher.match(segments, transcript)
        assert result[0]["product_name"] == "未命名商品"

    def test_empty_transcript_uses_vlm_name(self):
        matcher = ProductNameMatcher()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_info": {
                    "type": "T恤",
                    "color": "黑色",
                    "style": "Oversize",
                },
            }
        ]
        transcript = []

        result = matcher.match(segments, transcript)
        assert result[0]["product_name"] == "黑色 Oversize T恤"
        assert result[0]["name_source"] == "vlm"


class TestASROverride:
    def test_asr_more_specific_overrides_vlm(self):
        matcher = ProductNameMatcher()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_info": {
                    "type": "T恤",
                    "color": "黑色",
                    "style": "圆领",
                },
            }
        ]
        transcript = [
            {
                "text": "这款黑色冰丝透气圆领T恤特别舒服",
                "start_time": 10.0,
                "end_time": 20.0,
            },
        ]

        result = matcher.match(segments, transcript)
        assert result[0]["product_name"] == "黑色冰丝透气圆领T恤"
        assert result[0]["name_source"] == "asr"

    def test_asr_vague_uses_vlm_fallback(self):
        matcher = ProductNameMatcher()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_info": {
                    "type": "T恤",
                    "color": "黑色",
                    "style": "Oversize",
                },
            }
        ]
        transcript = [
            {"text": "看这一件", "start_time": 10.0, "end_time": 15.0},
        ]

        result = matcher.match(segments, transcript)
        # "看这一件" 是模糊短语，VLM 名称应该被使用
        assert result[0]["product_name"] == "黑色 Oversize T恤"
        assert result[0]["name_source"] == "vlm"


class TestEdgeCases:
    def test_empty_segments_returns_empty(self):
        matcher = ProductNameMatcher()
        result = matcher.match(
            [], [{"text": "test", "start_time": 0.0, "end_time": 1.0}]
        )
        assert result == []

    def test_product_info_with_description_fallback(self):
        matcher = ProductNameMatcher()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_info": {
                    "type": "",
                    "color": "",
                    "style": "",
                    "description": "碎花雪纺长裙",
                },
            }
        ]
        transcript = []

        result = matcher.match(segments, transcript)
        assert result[0]["product_name"] == "碎花雪纺长裙"

    def test_multiple_segments_matched(self):
        matcher = ProductNameMatcher()

        segments = [
            {
                "start_time": 0.0,
                "end_time": 120.0,
                "product_info": {"type": "连衣裙", "color": "红色", "style": "A字裙"},
            },
            {
                "start_time": 200.0,
                "end_time": 400.0,
                "product_info": {"type": "外套", "color": "黑色", "style": "风衣"},
            },
        ]
        transcript = [
            {"text": "这款红色A字连衣裙特别好看", "start_time": 10.0, "end_time": 20.0},
            {"text": "接下来看这件", "start_time": 250.0, "end_time": 260.0},
        ]

        result = matcher.match(segments, transcript)
        assert len(result) == 2
        # ASR 提取 "红色A字连衣裙特别好" (8 chars) > VLM "红色 A字裙 连衣裙" (8 chars)
        # 长度相等时使用 VLM
        assert result[0]["name_source"] == "vlm"
        assert result[1]["name_source"] == "vlm"
