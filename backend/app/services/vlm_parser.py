"""VLM response parser with multi-layer JSON extraction and tolerance for malformed output."""

import json
import logging
import re

logger = logging.getLogger(__name__)

CONFIDENCE_LOW_THRESHOLD = 0.6

DEFAULT_RESPONSE = {
    "is_different": False,
    "confidence": 0.0,
    "dimensions": {},
    "product_1": {},
    "product_2": {},
}


class VLMResponseParser:
    """Parses VLM responses with JSON extraction and tolerance for malformed output.

    Qwen-VL-Plus does NOT support native JSON mode, so responses may contain
    extra text around the JSON. Multi-layer parsing strategy:
    1. Try direct json.loads
    2. Regex extract JSON object from text
    3. Fill missing fields with safe defaults
    """

    def parse(self, response_text: str) -> dict:
        """Extract and parse JSON from VLM response.

        Returns dict with keys: is_different, confidence, dimensions,
        product_1, product_2, low_confidence.
        """
        if not response_text or not response_text.strip():
            return {**DEFAULT_RESPONSE, "low_confidence": True}

        parsed = self._extract_json(response_text)
        if parsed is None:
            logger.warning("Failed to extract JSON from VLM response, using defaults")
            return {**DEFAULT_RESPONSE, "low_confidence": True}

        result = self._fill_defaults(parsed)
        result["low_confidence"] = (
            float(result.get("confidence", 0.0)) < CONFIDENCE_LOW_THRESHOLD
        )
        return result

    def _extract_json(self, text: str) -> dict | None:
        """Try multiple strategies to extract JSON from text."""
        text = text.strip()

        # Strategy 1: direct parse
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: regex extract first JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _fill_defaults(self, parsed: dict) -> dict:
        """Fill missing fields with safe defaults."""
        result = {
            "is_different": bool(parsed.get("is_different", False)),
            "confidence": float(parsed.get("confidence", 0.0)),
            "dimensions": parsed.get("dimensions", {}),
            "product_1": parsed.get("product_1", {}),
            "product_2": parsed.get("product_2", {}),
        }

        if not isinstance(result["dimensions"], dict):
            result["dimensions"] = {}

        for key in ("product_1", "product_2"):
            if not isinstance(result[key], dict):
                result[key] = {}

        return result
