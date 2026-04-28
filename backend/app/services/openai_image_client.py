"""OpenAI Images client for commerce asset generation."""

import base64
from pathlib import Path
from typing import Any

import requests


class OpenAIImageClient:
    def __init__(self, api_key: str, api_base: str, model: str, timeout: int = 500):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate_with_reference(
        self,
        prompt: str,
        image_path: Path,
        *,
        size: str,
        quality: str = "auto",
    ) -> bytes:
        url = f"{self.api_base}/images/edits"
        fields = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "n": "1",
        }
        if quality and quality != "auto":
            fields["quality"] = quality

        with image_path.open("rb") as image_file:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=fields,
                files={"image": ("cover.jpg", image_file, "image/jpeg")},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return self._extract_first_image(response.json())

    @staticmethod
    def _extract_first_image(payload: dict[str, Any]) -> bytes:
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("OpenAI Images response has no data")
        first = data[0]
        if not isinstance(first, dict):
            raise ValueError("OpenAI Images response data item is invalid")
        b64_json = first.get("b64_json")
        if isinstance(b64_json, str) and b64_json:
            return base64.b64decode(b64_json)
        url = first.get("url")
        if isinstance(url, str) and url:
            image_response = requests.get(url, timeout=60)
            image_response.raise_for_status()
            return image_response.content
        raise ValueError("OpenAI Images response has no image payload")
