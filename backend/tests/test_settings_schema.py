# pyright: reportImplicitRelativeImport=false, reportArgumentType=false

import pytest
from pydantic import ValidationError

from app.api.settings import SettingsRequest, VLMProvider


def test_settings_request_uses_backend_defaults_for_qwen():
    settings = SettingsRequest(api_key="test-key")

    assert settings.vlm_provider == "qwen"
    assert settings.api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.model == "qwen-vl-plus"
    assert settings.scene_threshold == 27.0
    assert settings.frame_sample_fps == 2
    assert settings.recall_cooldown_seconds == 15
    assert settings.candidate_looseness == "standard"
    assert settings.min_segment_duration_seconds == 25
    assert settings.dedupe_window_seconds == 90
    assert settings.allow_returned_product is True
    assert settings.review_strictness == "standard"
    assert settings.review_mode == "segment_multiframe"
    assert settings.max_candidate_count == 20
    assert settings.subtitle_mode == "off"
    assert settings.subtitle_position == "bottom"
    assert settings.subtitle_template == "clean"
    assert settings.custom_position_y is None


def test_settings_request_resolves_glm_defaults():
    settings = SettingsRequest(api_key="test-key", vlm_provider=VLMProvider.glm)

    assert settings.api_base == "https://open.bigmodel.cn/api/paas/v4"
    assert settings.model == "glm-5v-turbo"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("scene_threshold", 9.9),
        ("scene_threshold", 60.1),
        ("frame_sample_fps", 0),
        ("frame_sample_fps", 6),
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
