# pyright: reportImplicitRelativeImport=false
"""Provider-aware VLM client for OpenAI-compatible multimodal APIs."""

import base64
import logging
import time
from typing import Any, cast

from openai import OpenAI

from app.api.settings import DEFAULT_API_BASES, DEFAULT_MODELS, VLMProvider

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = VLMProvider.qwen.value
DEFAULT_BASE_URL = DEFAULT_API_BASES[DEFAULT_PROVIDER]
DEFAULT_MODEL = DEFAULT_MODELS[DEFAULT_PROVIDER]
MAX_RETRIES = 3
TIMEOUT_SECONDS = 120


def _resolve_provider(provider: str | None) -> str:
    resolved_provider = (provider or DEFAULT_PROVIDER).strip().lower()
    allowed_providers = {member.value for member in VLMProvider}
    if resolved_provider not in allowed_providers:
        raise ValueError(
            f"Unsupported VLM provider '{resolved_provider}'. "
            f"Supported providers: {', '.join(sorted(allowed_providers))}"
        )
    return resolved_provider


class VLMClient:
    """OpenAI-compatible multimodal client with provider-aware defaults."""

    def __init__(
        self,
        api_key: str,
        provider: str = DEFAULT_PROVIDER,
        base_url: str | None = None,
        model: str | None = None,
    ):
        resolved_provider = _resolve_provider(provider)
        resolved_base_url = base_url or DEFAULT_API_BASES[resolved_provider]
        resolved_model = model or DEFAULT_MODELS[resolved_provider]

        self.api_key: str = api_key
        self.provider: str = resolved_provider
        self.base_url: str = resolved_base_url
        self.model: str = resolved_model
        self.client: OpenAI = OpenAI(api_key=api_key, base_url=resolved_base_url)

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
                        "VLM API call failed for provider=%s model=%s "
                        "(attempt %d/%d), retrying in %ds: %s",
                        self.provider,
                        self.model,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                        str(e),
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "VLM API call failed for provider=%s model=%s after %d attempts: %s",
                        self.provider,
                        self.model,
                        MAX_RETRIES,
                        str(e),
                    )

        raise RuntimeError(
            f"VLM API call failed after {MAX_RETRIES} attempts: {last_error}"
        )
