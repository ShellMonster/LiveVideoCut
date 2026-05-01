from enum import Enum
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import (
    DEFAULT_API_BASES,
    DEFAULT_MODELS,
    PROVIDER_HOST_HINTS,
    PROVIDER_MODEL_PREFIXES,
    VLMProvider,
    UPLOAD_DIR,
)
from app.services import app_settings

router = APIRouter()


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
    top = "top"
    bottom = "bottom"
    middle = "middle"
    custom = "custom"


class SubtitleTemplate(str, Enum):
    clean = "clean"
    ecommerce = "ecommerce"
    bold = "bold"
    karaoke = "karaoke"


class AsrProvider(str, Enum):
    dashscope = "dashscope"
    volcengine = "volcengine"
    volcengine_vc = "volcengine_vc"


class CandidateLooseness(str, Enum):
    strict = "strict"
    standard = "standard"
    loose = "loose"


class ExportMode(str, Enum):
    smart = "smart"
    no_vlm = "no_vlm"
    all_candidates = "all_candidates"
    all_scenes = "all_scenes"


class LLMType(str, Enum):
    openai = "openai"
    gemini = "gemini"


class ExportResolution(str, Enum):
    original = "original"
    r1080p = "1080p"
    r4k = "4k"


class SegmentGranularity(str, Enum):
    single_item = "single_item"
    outfit = "outfit"


class SensitiveFilterMode(str, Enum):
    video_segment = "video_segment"
    drop_clip = "drop_clip"


class SensitiveMatchMode(str, Enum):
    contains = "contains"
    exact = "exact"


class ChangeDetectionFusionMode(str, Enum):
    any_signal = "any_signal"
    weighted_vote = "weighted_vote"


class ChangeDetectionSensitivity(str, Enum):
    conservative = "conservative"
    balanced = "balanced"
    sensitive = "sensitive"


class FFmpegPreset(str, Enum):
    veryfast = "veryfast"
    fast = "fast"
    medium = "medium"


class CommerceImageSize(str, Enum):
    r2k = "2K"
    square = "1024x1024"
    portrait = "1024x1536"
    landscape = "1536x1024"
    large_square = "2048x2048"
    detail_long = "2160x3840"


class CommerceImageQuality(str, Enum):
    auto = "auto"
    low = "low"
    medium = "medium"
    high = "high"


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

    api_key: str = ""
    enable_vlm: bool = True
    export_mode: ExportMode = ExportMode.smart
    vlm_provider: VLMProvider = VLMProvider.qwen
    api_base: str | None = None
    model: str | None = None

    scene_threshold: float = Field(default=27.0, ge=10.0, le=60.0)
    frame_sample_fps: float = Field(default=0.5, ge=0.25, le=5.0)
    recall_cooldown_seconds: int = Field(default=15, ge=0, le=60)
    candidate_looseness: CandidateLooseness = CandidateLooseness.standard
    min_segment_duration_seconds: int = Field(default=25, ge=5, le=120)
    dedupe_window_seconds: int = Field(default=90, ge=0, le=600)
    merge_count: int = Field(default=1, ge=1, le=10)
    allow_returned_product: bool = True

    review_strictness: ReviewStrictness = ReviewStrictness.standard
    review_mode: ReviewMode = ReviewMode.segment_multiframe
    max_candidate_count: int = Field(default=20, ge=1, le=100)

    subtitle_mode: SubtitleMode = SubtitleMode.karaoke
    subtitle_position: SubtitlePosition = SubtitlePosition.bottom
    subtitle_template: SubtitleTemplate = SubtitleTemplate.clean
    custom_position_y: int | None = Field(default=None, ge=0, le=100)
    subtitle_font_size: int = Field(default=45, ge=24, le=120)
    subtitle_highlight_font_size: int = Field(default=55, ge=24, le=144)

    filter_filler_mode: str = "off"
    sensitive_filter_enabled: bool = False
    sensitive_words: list[str] = Field(default_factory=list, max_length=200)
    sensitive_filter_mode: SensitiveFilterMode = SensitiveFilterMode.video_segment
    sensitive_match_mode: SensitiveMatchMode = SensitiveMatchMode.contains
    cover_strategy: str = "content_first"
    video_speed: float = Field(default=1.25, ge=0.5, le=3.0)
    export_resolution: ExportResolution = ExportResolution.r1080p

    asr_provider: AsrProvider = AsrProvider.volcengine_vc
    asr_api_key: str = ""

    tos_ak: str = ""
    tos_sk: str = ""
    tos_bucket: str = "mp3-srt"
    tos_region: str = "cn-beijing"
    tos_endpoint: str = "tos-cn-beijing.volces.com"

    # --- LLM 文本分析设置（独立于 VLM） ---
    enable_llm_analysis: bool = False
    llm_type: LLMType = LLMType.openai
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_model: str = ""
    segment_granularity: SegmentGranularity = SegmentGranularity.single_item
    boundary_snap: bool = True  # Snap clip boundaries to sentence edges
    enable_boundary_refinement: bool = False  # LLM reviews and adjusts clip boundaries for narrative completeness
    change_detection_fusion_mode: ChangeDetectionFusionMode = ChangeDetectionFusionMode.any_signal
    change_detection_sensitivity: ChangeDetectionSensitivity = ChangeDetectionSensitivity.balanced
    clothing_yolo_confidence: float = Field(default=0.25, ge=0.05, le=0.8)

    # --- FFmpeg 导出编码设置 ---
    ffmpeg_preset: FFmpegPreset = FFmpegPreset.fast
    ffmpeg_crf: int = Field(default=23, ge=18, le=32)

    # --- BGM 设置 ---
    bgm_enabled: bool = True
    bgm_volume: float = Field(default=0.25, ge=0.0, le=1.0)
    original_volume: float = Field(default=1.0, ge=0.0, le=2.0)

    # --- AI 商品素材设置（独立于剪辑流水线 VLM/LLM） ---
    commerce_gemini_api_key: str = ""
    commerce_gemini_api_base: str = "https://generativelanguage.googleapis.com"
    commerce_gemini_model: str = "gemini-3-flash-preview"
    commerce_gemini_timeout_seconds: int = Field(default=150, ge=30, le=600)
    commerce_image_api_key: str = ""
    commerce_image_api_base: str = "https://api.openai.com/v1"
    commerce_image_model: str = "gpt-image-2"
    commerce_image_size: CommerceImageSize = CommerceImageSize.r2k
    commerce_image_quality: CommerceImageQuality = CommerceImageQuality.auto
    commerce_image_timeout_seconds: int = Field(default=500, ge=60, le=1200)

    @model_validator(mode="after")
    def apply_provider_defaults_and_validate(self):
        normalized_sensitive_words: list[str] = []
        seen_sensitive_words: set[str] = set()
        for word in self.sensitive_words:
            value = str(word).strip()
            if not value or len(value) > 50 or value in seen_sensitive_words:
                continue
            normalized_sensitive_words.append(value)
            seen_sensitive_words.add(value)
        self.sensitive_words = normalized_sensitive_words

        if not self.enable_vlm and self.export_mode == ExportMode.smart:
            self.export_mode = ExportMode.no_vlm

        if self.export_mode == ExportMode.smart and not self.api_key:
            raise ValueError("api_key is required when enable_vlm is true")

        provider = self.vlm_provider.value
        resolved_api_base = self.api_base or DEFAULT_API_BASES[provider]
        resolved_model = self.model or DEFAULT_MODELS[provider]

        self.api_base = _validate_api_base(provider, resolved_api_base)
        self.model = _validate_model(provider, resolved_model)
        return self


SENSITIVE_FIELDS = frozenset(
    {
        "api_key",
        "asr_api_key",
        "tos_ak",
        "tos_sk",
        "llm_api_key",
        "commerce_gemini_api_key",
        "commerce_image_api_key",
    }
)


@router.post("/api/settings/validate")
async def validate_settings(settings: SettingsRequest):
    try:
        if settings.export_mode != ExportMode.smart:
            return {"valid": True}

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


@router.get("/api/settings/current")
async def get_current_settings():
    return app_settings.get_current_settings(UPLOAD_DIR)


@router.put("/api/settings/current")
async def save_current_settings(payload: dict[str, object]):
    return app_settings.save_current_settings(payload, UPLOAD_DIR)


@router.post("/api/settings/reset")
async def reset_current_settings():
    return app_settings.reset_current_settings(UPLOAD_DIR)
