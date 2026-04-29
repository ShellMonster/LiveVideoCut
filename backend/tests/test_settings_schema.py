# pyright: reportImplicitRelativeImport=false, reportArgumentType=false

import pytest
from pydantic import ValidationError

from app.api.settings import SettingsRequest, VLMProvider


def test_settings_request_uses_backend_defaults_for_qwen():
    settings = SettingsRequest(api_key="test-key")

    assert settings.enable_vlm is True
    assert settings.export_mode == "smart"
    assert settings.vlm_provider == "qwen"
    assert settings.api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.model == "qwen-vl-plus"
    assert settings.scene_threshold == 27.0
    assert settings.frame_sample_fps == 0.5
    assert settings.recall_cooldown_seconds == 15
    assert settings.candidate_looseness == "standard"
    assert settings.min_segment_duration_seconds == 25
    assert settings.dedupe_window_seconds == 90
    assert settings.allow_returned_product is True
    assert settings.review_strictness == "standard"
    assert settings.review_mode == "segment_multiframe"
    assert settings.max_candidate_count == 20
    assert settings.subtitle_mode == "karaoke"
    assert settings.subtitle_position == "bottom"
    assert settings.subtitle_template == "clean"
    assert settings.custom_position_y is None
    assert settings.subtitle_font_size == 60
    assert settings.subtitle_highlight_font_size == 72
    assert settings.sensitive_filter_enabled is False
    assert settings.sensitive_words == []
    assert settings.sensitive_filter_mode == "video_segment"
    assert settings.sensitive_match_mode == "contains"
    assert settings.change_detection_fusion_mode == "any_signal"
    assert settings.change_detection_sensitivity == "balanced"
    assert settings.clothing_yolo_confidence == 0.25
    assert settings.ffmpeg_preset == "fast"
    assert settings.ffmpeg_crf == 23


def test_settings_request_resolves_glm_defaults():
    settings = SettingsRequest(api_key="test-key", vlm_provider=VLMProvider.glm)

    assert settings.api_base == "https://open.bigmodel.cn/api/paas/v4"
    assert settings.model == "glm-5v-turbo"


def test_settings_request_allows_blank_api_key_when_vlm_disabled():
    settings = SettingsRequest(enable_vlm=False, api_key="")

    assert settings.enable_vlm is False
    assert settings.export_mode == "no_vlm"
    assert settings.api_key == ""


def test_settings_request_rejects_blank_api_key_when_vlm_enabled():
    with pytest.raises(ValidationError):
        _ = SettingsRequest(enable_vlm=True, api_key="")


def test_settings_request_allows_blank_api_key_for_all_scenes_mode():
    settings = SettingsRequest(export_mode="all_scenes", api_key="")

    assert settings.export_mode == "all_scenes"
    assert settings.api_key == ""


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("scene_threshold", 9.9),
        ("scene_threshold", 60.1),
        ("frame_sample_fps", 0.24),
        ("frame_sample_fps", 5.1),
        ("recall_cooldown_seconds", -1),
        ("recall_cooldown_seconds", 61),
        ("min_segment_duration_seconds", 4),
        ("min_segment_duration_seconds", 121),
        ("dedupe_window_seconds", -1),
        ("dedupe_window_seconds", 601),
        ("max_candidate_count", 0),
        ("max_candidate_count", 101),
        ("custom_position_y", -1),
        ("custom_position_y", 101),
        ("subtitle_font_size", 23),
        ("subtitle_font_size", 121),
        ("subtitle_highlight_font_size", 23),
        ("subtitle_highlight_font_size", 145),
        ("sensitive_words", ["词"] * 201),
        ("clothing_yolo_confidence", 0.04),
        ("clothing_yolo_confidence", 0.81),
        ("ffmpeg_crf", 17),
        ("ffmpeg_crf", 33),
    ],
)
def test_settings_request_rejects_out_of_range_values(
    field_name: str, value: int | float
):
    with pytest.raises(ValidationError):
        _ = SettingsRequest(api_key="test-key", **{field_name: value})


def test_settings_request_rejects_provider_model_mismatch():
    with pytest.raises(ValidationError):
        _ = SettingsRequest(
            api_key="test-key", vlm_provider=VLMProvider.qwen, model="glm-5v-turbo"
        )

    with pytest.raises(ValidationError):
        _ = SettingsRequest(
            api_key="test-key", vlm_provider=VLMProvider.glm, model="qwen-vl-plus"
        )


def test_settings_request_rejects_provider_base_mismatch():
    with pytest.raises(ValidationError):
        _ = SettingsRequest(
            api_key="test-key",
            vlm_provider=VLMProvider.qwen,
            api_base="https://open.bigmodel.cn/api/paas/v4",
        )


def test_settings_request_normalizes_sensitive_words():
    settings = SettingsRequest(
        api_key="test-key",
        sensitive_filter_enabled=True,
        sensitive_words=[" 联系方式 ", "", "联系方式", "价格承诺"],
    )

    assert settings.sensitive_words == ["联系方式", "价格承诺"]

    with pytest.raises(ValidationError):
        _ = SettingsRequest(
            api_key="test-key",
            vlm_provider=VLMProvider.glm,
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )


@pytest.mark.anyio
async def test_validate_settings_accepts_qwen_payload(client, monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    response = await client.post(
        "/api/settings/validate",
        json={
            "api_key": "test-key",
            "vlm_provider": "qwen",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-vl-plus",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}
    assert calls[0]["model"] == "qwen-vl-plus"


@pytest.mark.anyio
async def test_validate_settings_accepts_glm_payload(client, monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    response = await client.post(
        "/api/settings/validate",
        json={
            "api_key": "test-key",
            "vlm_provider": "glm",
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-5v-turbo",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}
    assert calls[0]["model"] == "glm-5v-turbo"


@pytest.mark.anyio
async def test_validate_settings_short_circuits_when_vlm_disabled(client, monkeypatch):
    class FakeOpenAI:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError(
                "OpenAI client should not be created when VLM is disabled"
            )

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    response = await client.post(
        "/api/settings/validate",
        json={
            "enable_vlm": False,
            "api_key": "",
            "vlm_provider": "qwen",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}


@pytest.mark.anyio
async def test_validate_settings_short_circuits_for_all_candidates_mode(
    client, monkeypatch
):
    class FakeOpenAI:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError(
                "OpenAI client should not be created outside smart mode"
            )

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    response = await client.post(
        "/api/settings/validate",
        json={
            "export_mode": "all_candidates",
            "api_key": "",
            "vlm_provider": "qwen",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}
