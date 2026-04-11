"""VLM (Vision Language Model) client for Qwen-VL-Plus via OpenAI SDK."""

import base64
import logging
import time
from typing import Any, cast

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-vl-plus"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 120


class VLMClient:
    """Qwen-VL-Plus API client using OpenAI SDK compatible interface."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ):
        self.api_key: str = api_key
        self.base_url: str = base_url
        self.model: str = model
        self.client: OpenAI = OpenAI(api_key=api_key, base_url=base_url)

    def encode_image_base64(self, image_path: str) -> str:
        """Read image file and return base64-encoded string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def compare_frames(self, image1_path: str, image2_path: str, prompt: str) -> str:
        """Send two frames to VLM for comparison.

        Both images are base64-encoded as image_url content.
        Returns raw text response from VLM.

        Retry: 3x with exponential backoff (1s, 2s, 4s).
        Timeout: 120s per request.
        """
        return self.compare_frames_multi([image1_path, image2_path], prompt)

    def compare_frames_multi(self, image_paths: list[str], prompt: str) -> str:
        """Send multiple frames to VLM for comparison without breaking two-frame callers."""
        content: list[dict[str, object]] = []
        for image_path in image_paths:
            b64 = self.encode_image_base64(image_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )
        content.append({"type": "text", "text": prompt})

        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    timeout=TIMEOUT_SECONDS,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = 2**attempt  # 1s, 2s, 4s
                    logger.warning(
                        "VLM API call failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                        str(e),
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "VLM API call failed after %d attempts: %s",
                        MAX_RETRIES,
                        str(e),
                    )

        raise RuntimeError(
            f"VLM API call failed after {MAX_RETRIES} attempts: {last_error}"
        )
