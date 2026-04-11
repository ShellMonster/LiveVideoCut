"""Tests for VLMResponseParser — pure logic, no external deps."""

import pytest

from app.services.vlm_parser import VLMResponseParser


@pytest.fixture
def parser():
    return VLMResponseParser()


STANDARD_RESPONSE = """{
  "is_different": true,
  "confidence": 0.85,
  "dimensions": {
    "type": {"same": false, "value_1": "上衣", "value_2": "裙子"},
    "color": {"same": false, "value_1": "红色", "value_2": "蓝色"},
    "pattern": {"same": true, "value_1": "纯色", "value_2": "纯色"},
    "cut": {"same": false, "value_1": "修身", "value_2": "A字"},
    "wear": {"same": true, "value_1": "单穿", "value_2": "单穿"}
  },
  "product_1": {"type": "上衣", "color": "红色", "style": "修身纯色上衣"},
  "product_2": {"type": "裙子", "color": "蓝色", "style": "A字纯色裙子"}
}"""


class TestStandardJSON:
    def test_parses_standard_json_correctly(self, parser):
        result = parser.parse(STANDARD_RESPONSE)
        assert result["is_different"] is True
        assert result["confidence"] == 0.85
        assert result["low_confidence"] is False
        assert "dimensions" in result
        assert result["dimensions"]["type"]["same"] is False
        assert result["product_1"]["type"] == "上衣"
        assert result["product_2"]["type"] == "裙子"


class TestTextBeforeJSON:
    def test_extracts_json_from_text_prefix(self, parser):
        text = f"好的，我来分析：{STANDARD_RESPONSE}"
        result = parser.parse(text)
        assert result["is_different"] is True
        assert result["confidence"] == 0.85

    def test_extracts_json_with_chinese_prefix(self, parser):
        text = f"根据对比分析，结果如下：\n{STANDARD_RESPONSE}\n以上是我的分析。"
        result = parser.parse(text)
        assert result["is_different"] is True


class TestMalformedJSON:
    def test_missing_bracket_returns_defaults(self, parser):
        text = '{"is_different": true, "confidence": 0.8'
        result = parser.parse(text)
        assert result["is_different"] is False
        assert result["confidence"] == 0.0
        assert result["low_confidence"] is True

    def test_garbled_text_returns_defaults(self, parser):
        result = parser.parse("这不是JSON格式的内容")
        assert result["is_different"] is False
        assert result["confidence"] == 0.0


class TestEmptyResponse:
    def test_empty_string_returns_defaults(self, parser):
        result = parser.parse("")
        assert result["is_different"] is False
        assert result["confidence"] == 0.0
        assert result["low_confidence"] is True

    def test_whitespace_only_returns_defaults(self, parser):
        result = parser.parse("   \n\t  ")
        assert result["is_different"] is False
        assert result["low_confidence"] is True


class TestConfidenceThreshold:
    def test_low_confidence_flagged(self, parser):
        text = '{"is_different": true, "confidence": 0.4}'
        result = parser.parse(text)
        assert result["low_confidence"] is True

    def test_high_confidence_not_flagged(self, parser):
        text = '{"is_different": true, "confidence": 0.8}'
        result = parser.parse(text)
        assert result["low_confidence"] is False

    def test_exact_threshold_not_flagged(self, parser):
        text = '{"is_different": true, "confidence": 0.6}'
        result = parser.parse(text)
        assert result["low_confidence"] is False

    def test_just_below_threshold_flagged(self, parser):
        text = '{"is_different": true, "confidence": 0.59}'
        result = parser.parse(text)
        assert result["low_confidence"] is True


class TestMissingFields:
    def test_missing_dimensions_fills_defaults(self, parser):
        text = '{"is_different": true, "confidence": 0.9}'
        result = parser.parse(text)
        assert result["dimensions"] == {}
        assert result["product_1"] == {}
        assert result["product_2"] == {}

    def test_missing_is_different_defaults_false(self, parser):
        text = '{"confidence": 0.9}'
        result = parser.parse(text)
        assert result["is_different"] is False

    def test_missing_confidence_defaults_zero(self, parser):
        text = '{"is_different": true}'
        result = parser.parse(text)
        assert result["confidence"] == 0.0
        assert result["low_confidence"] is True


class TestAllFieldsPresent:
    def test_exact_match(self, parser):
        result = parser.parse(STANDARD_RESPONSE)
        assert result["is_different"] is True
        assert result["confidence"] == 0.85
        assert result["low_confidence"] is False
        assert len(result["dimensions"]) == 5
        assert result["product_1"]["type"] == "上衣"
        assert result["product_1"]["color"] == "红色"
        assert result["product_1"]["style"] == "修身纯色上衣"
        assert result["product_2"]["type"] == "裙子"
        assert result["product_2"]["color"] == "蓝色"
        assert result["product_2"]["style"] == "A字纯色裙子"


class TestNonDictResponse:
    def test_array_response_returns_defaults(self, parser):
        result = parser.parse("[1, 2, 3]")
        assert result["is_different"] is False

    def test_string_response_returns_defaults(self, parser):
        result = parser.parse('"hello"')
        assert result["is_different"] is False

    def test_number_response_returns_defaults(self, parser):
        result = parser.parse("42")
        assert result["is_different"] is False
