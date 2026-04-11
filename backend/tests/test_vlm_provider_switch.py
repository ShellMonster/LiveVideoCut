# pyright: reportImplicitRelativeImport=false, reportFunctionMemberAccess=false
import logging
from unittest.mock import MagicMock, patch

from app.tasks.pipeline import vlm_confirm
from app.services.vlm_client import VLMClient


def test_vlm_client_uses_qwen_defaults_when_provider_absent():
    with patch("app.services.vlm_client.OpenAI") as mock_openai:
        client = VLMClient(api_key="test-key")

    assert client.provider == "qwen"
    assert client.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert client.model == "qwen-vl-plus"
    mock_openai.assert_called_once_with(
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


def test_vlm_client_uses_glm_defaults_for_glm_provider():
    with patch("app.services.vlm_client.OpenAI") as mock_openai:
        client = VLMClient(api_key="test-key", provider="glm")

    assert client.provider == "glm"
    assert client.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert client.model == "glm-5v-turbo"
    mock_openai.assert_called_once_with(
        api_key="test-key",
        base_url="https://open.bigmodel.cn/api/paas/v4",
    )


def test_vlm_client_prefers_explicit_base_and_model_over_provider_defaults():
    with patch("app.services.vlm_client.OpenAI") as mock_openai:
        client = VLMClient(
            api_key="test-key",
            provider="glm",
            base_url="https://custom.example.com/v1",
            model="glm-custom",
        )

    assert client.provider == "glm"
    assert client.base_url == "https://custom.example.com/v1"
    assert client.model == "glm-custom"
    mock_openai.assert_called_once_with(
        api_key="test-key",
        base_url="https://custom.example.com/v1",
    )


def test_vlm_confirm_routes_provider_to_vlm_client_and_logs_selection(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="app.tasks.pipeline")
    candidates_file = tmp_path / "candidates.json"
    candidates_file.write_text("[]")
    (tmp_path / "frames").mkdir()

    fake_confirmor = MagicMock()
    fake_confirmor.confirm_candidates.return_value = []

    with (
        patch("app.tasks.pipeline.VLMClient") as mock_client_cls,
        patch("app.tasks.pipeline.VLMConfirmor", return_value=fake_confirmor),
    ):
        mock_client_cls.return_value = MagicMock()

        result = vlm_confirm.run(
            "task-123",
            str(tmp_path),
            "test-key",
            provider="glm",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-5v-turbo",
            review_mode="segment_multiframe",
        )

    assert result == {"confirmed_count": 0, "total_candidates": 0}
    mock_client_cls.assert_called_once_with(
        api_key="test-key",
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-5v-turbo",
    )
    assert "provider=glm" in caplog.text
    assert "model=glm-5v-turbo" in caplog.text
