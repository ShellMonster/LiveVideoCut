"""Tests for VLMClient — mocked OpenAI SDK, no real API calls."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from app.services.vlm_client import VLMClient


@pytest.fixture
def mock_openai():
    with patch("app.services.vlm_client.OpenAI") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def client(mock_openai):
    return VLMClient(api_key="test-key")


@pytest.fixture
def sample_image(tmp_path):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")
    return str(img)


class TestEncodeImageBase64:
    def test_returns_valid_base64(self, client, sample_image):
        result = client.encode_image_base64(sample_image)
        decoded = base64.b64decode(result)
        assert decoded == b"\xff\xd8\xff\xe0fake_jpeg_data"

    def test_result_is_string(self, client, sample_image):
        result = client.encode_image_base64(sample_image)
        assert isinstance(result, str)


class TestCompareFrames:
    def test_returns_response_text(self, client, mock_openai, sample_image):
        mock_message = MagicMock()
        mock_message.content = '{"is_different": true}'
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = client.compare_frames(sample_image, sample_image, "test prompt")
        assert result == '{"is_different": true}'

    def test_sends_both_images_as_base64(self, client, mock_openai, sample_image):
        mock_message = MagicMock()
        mock_message.content = "ok"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        client.compare_frames(sample_image, sample_image, "prompt")

        call_args = mock_openai.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        content = messages[0]["content"]

        image_items = [c for c in content if c["type"] == "image_url"]
        assert len(image_items) == 2
        assert image_items[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert image_items[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    def test_uses_correct_model(self, client, mock_openai, sample_image):
        mock_message = MagicMock()
        mock_message.content = "ok"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        client.compare_frames(sample_image, sample_image, "prompt")

        call_args = mock_openai.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "qwen-vl-plus"


class TestRetryOnFailure:
    def test_retries_on_failure_then_succeeds(self, client, mock_openai, sample_image):
        mock_message = MagicMock()
        mock_message.content = "success"
        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_openai.chat.completions.create.side_effect = [
            Exception("network error"),
            Exception("timeout"),
            MagicMock(choices=[mock_choice]),
        ]

        with patch("app.services.vlm_client.time.sleep"):
            result = client.compare_frames(sample_image, sample_image, "prompt")

        assert result == "success"
        assert mock_openai.chat.completions.create.call_count == 3

    def test_raises_after_max_retries(self, client, mock_openai, sample_image):
        mock_openai.chat.completions.create.side_effect = Exception("persistent error")

        with patch("app.services.vlm_client.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after 3 attempts"):
                client.compare_frames(sample_image, sample_image, "prompt")

        assert mock_openai.chat.completions.create.call_count == 3


class TestTimeout:
    def test_passes_timeout_to_api_call(self, client, mock_openai, sample_image):
        mock_message = MagicMock()
        mock_message.content = "ok"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        client.compare_frames(sample_image, sample_image, "prompt")

        call_args = mock_openai.chat.completions.create.call_args
        assert call_args.kwargs["timeout"] == 120
