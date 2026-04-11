from enum import Enum
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

router = APIRouter()

QWEN_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
GLM_API_BASE = "https://open.bigmodel.cn/api/paas/v4"

DEFAULT_API_BASES = {
    "qwen": QWEN_API_BASE,
    "glm": GLM_API_BASE,
}

DEFAULT_MODELS = {
    "qwen": "qwen-vl-plus",
    "glm": "glm-5v-turbo",
}

PROVIDER_HOST_HINTS = {
    "qwen": ("dashscope.aliyuncs.com",),
    "glm": ("open.bigmodel.cn",),
}

PROVIDER_MODEL_PREFIXES = {
    "qwen": ("qwen-",),
    "glm": ("glm-",),
}


class VLMProvider(str, Enum):
    qwen = "qwen"
    glm = "glm"


class ReviewStrictness(str, Enum):
    strict = "strict"
    standard = "standard"
    loose = "loose"


class ReviewMode(str, Enum):
    adjacent_frames = "adjacent_frames"
    segment_multiframe = "segment_multiframe"


class SubtitleMode(str, Enum):
    off = "off"
    basic = "basic"
    styled = "styled"
    karaoke = "karaoke"


class SubtitlePosition(str, Enum):
    bottom = "bottom"
    middle = "middle"
    custom = "custom"


class SubtitleTemplate(str, Enum):
    clean = "clean"
    ecommerce = "ecommerce"
    bold = "bold"
    karaoke = "karaoke"


class CandidateLooseness(str, Enum):
    strict = "strict"
    standard = "standard"
    loose = "loose"


def _validate_api_base(provider: str, api_base: str) -> str:
    parsed = urlparse(api_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("api_base must be a valid http(s) URL")

    hostname = (parsed.hostname or "").lower()
    if not any(hint in hostname for hint in PROVIDER_HOST_HINTS[provider]):
        raise ValueError(f"api_base is not compatible with provider '{provider}'")

    return api_base.rstrip("/")


def _validate_model(provider: str, model: str) -> str:
    lowered_model = model.lower()
    if not any(
        lowered_model.startswith(prefix) for prefix in PROVIDER_MODEL_PREFIXES[provider]
    ):
        raise ValueError(f"model is not compatible with provider '{provider}'")
    return model


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    api_key: str = Field(min_length=1)
    vlm_provider: VLMProvider = VLMProvider.qwen
    api_base: str | None = None
    model: str | None = None

    scene_threshold: float = Field(default=27.0, ge=10.0, le=60.0)
    frame_sample_fps: int = Field(default=2, ge=1, le=5)
    recall_cooldown_seconds: int = Field(default=15, ge=0, le=60)
    candidate_looseness: CandidateLooseness = CandidateLooseness.standard
    min_segment_duration_seconds: int = Field(default=25, ge=5, le=120)
    dedupe_window_seconds: int = Field(default=90, ge=0, le=600)
    allow_returned_product: bool = True

    review_strictness: ReviewStrictness = ReviewStrictness.standard
    review_mode: ReviewMode = ReviewMode.segment_multiframe
    max_candidate_count: int = Field(default=20, ge=1, le=100)

    subtitle_mode: SubtitleMode = SubtitleMode.off
    subtitle_position: SubtitlePosition = SubtitlePosition.bottom
    subtitle_template: SubtitleTemplate = SubtitleTemplate.clean
    custom_position_y: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def apply_provider_defaults_and_validate(self):
        provider = self.vlm_provider.value
        resolved_api_base = self.api_base or DEFAULT_API_BASES[provider]
        resolved_model = self.model or DEFAULT_MODELS[provider]

        self.api_base = _validate_api_base(provider, resolved_api_base)
        self.model = _validate_model(provider, resolved_model)
        return self


@router.post("/api/settings/validate")
async def validate_settings(settings: SettingsRequest):
    try:
        from openai import OpenAI

        api_base = settings.api_base or DEFAULT_API_BASES[settings.vlm_provider.value]
        model = settings.model or DEFAULT_MODELS[settings.vlm_provider.value]

        client = OpenAI(api_key=settings.api_key, base_url=api_base)
        _ = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "error": str(e)}
