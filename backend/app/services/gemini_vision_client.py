"""Gemini vision client for commerce asset analysis and copywriting."""

import base64
import json
import re
from pathlib import Path
from typing import Any

import requests


class GeminiVisionClient:
    def __init__(self, api_key: str, api_base: str, model: str, timeout: int = 150):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.timeout = timeout

    def analyze_cover(self, image_path: Path, product_hint: str) -> dict[str, Any]:
        prompt = f"""
你是直播电商服装商品识别助手。请只根据图片可见内容识别商品，不确定就写入 uncertain_fields。
已知片段商品名提示：{product_hint or "未知商品"}

请返回严格 JSON，不要 Markdown，结构如下：
{{
  "confidence": 0.0,
  "product_type": "品类",
  "visible_attributes": {{
    "color": "颜色",
    "fit": "版型",
    "sleeve": "袖型",
    "scene": "适用场景"
  }},
  "selling_points": ["可见卖点1", "可见卖点2"],
  "uncertain_fields": ["无法确认的字段"]
}}
""".strip()
        data = self._generate_json(prompt, image_path=image_path)
        return {
            "confidence": float(data.get("confidence") or 0),
            "product_type": str(data.get("product_type") or product_hint or "待识别商品"),
            "visible_attributes": self._string_map(data.get("visible_attributes")),
            "selling_points": self._string_list(data.get("selling_points")),
            "uncertain_fields": self._string_list(data.get("uncertain_fields")),
        }

    def generate_copywriting(self, analysis: dict[str, Any], product_hint: str) -> dict[str, Any]:
        prompt = f"""
你是直播电商短视频文案助手。根据商品识别结果生成抖音和淘宝可用文案。
必须遵守：
- 抖音标题尽量 30 个中文字符内，描述自然口播感，hashtags 不超过 5 个。
- 淘宝标题尽量 30 个中文字符内，卖点具体但不要写图片无法确认的材质、品牌、功效。
- 避免“最、第一、顶级、绝对”等绝对化宣传。
- AI 生成图或详情页建议必须标注“效果示意”。

商品名提示：{product_hint or "未知商品"}
商品识别 JSON：{json.dumps(analysis, ensure_ascii=False)}

请返回严格 JSON，不要 Markdown，结构如下：
{{
  "douyin": {{
    "title": "标题",
    "description": "描述",
    "hashtags": ["#标签"]
  }},
  "taobao": {{
    "title": "标题",
    "selling_points": ["卖点1", "卖点2", "卖点3"],
    "detail_modules": ["详情模块1", "详情模块2"]
  }}
}}
""".strip()
        data = self._generate_json(prompt)
        douyin = data.get("douyin") if isinstance(data.get("douyin"), dict) else {}
        taobao = data.get("taobao") if isinstance(data.get("taobao"), dict) else {}
        return {
            "douyin": {
                "title": str(douyin.get("title") or ""),
                "description": str(douyin.get("description") or ""),
                "hashtags": self._string_list(douyin.get("hashtags")),
                "compliance": ["标题建议 30 字内", "避免绝对化用语", "未确认材质不写实锤"],
            },
            "taobao": {
                "title": str(taobao.get("title") or ""),
                "selling_points": self._string_list(taobao.get("selling_points")),
                "detail_modules": self._string_list(taobao.get("detail_modules")),
                "compliance": ["商品标题建议 30 汉字内", "材质/尺码需人工确认", "AI 图需标注示意"],
            },
        }

    def _generate_json(self, prompt: str, image_path: Path | None = None) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if image_path is not None:
            image_bytes = image_path.read_bytes()
            parts.insert(
                0,
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode("utf-8"),
                    }
                },
            )

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        url = f"{self.api_base}/v1beta/models/{self.model}:generateContent"
        response = requests.post(
            url,
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        text = self._extract_text(response.json())
        return self._parse_json_text(text)

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Gemini response has no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        text = "\n".join(str(item) for item in texts if item)
        if not text.strip():
            raise ValueError("Gemini response has no text content")
        return text

    @staticmethod
    def _parse_json_text(text: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Gemini response JSON is not an object")
        return data

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    @staticmethod
    def _string_map(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {str(key): str(item) for key, item in value.items()}
