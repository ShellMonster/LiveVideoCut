import json
from pathlib import Path

import pytest

from app.services.error_handler import PipelineErrorHandler


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"state": "VISUAL_SCREENING"}))
    return tmp_path


class TestHandleError:
    def test_transitions_to_error_state(self, task_dir: Path):
        handler = PipelineErrorHandler(task_dir)
        handler.handle_error("VISUAL_FAILED", "frame extraction crashed")

        state = json.loads((task_dir / "state.json").read_text())
        assert state["state"] == "ERROR"
        assert "视觉分析失败" in state["message"]

    def test_saves_error_json(self, task_dir: Path):
        handler = PipelineErrorHandler(task_dir)
        handler.handle_error("ASR_FAILED", "connection refused")

        error = json.loads((task_dir / "error.json").read_text())
        assert error["error_type"] == "ASR_FAILED"
        assert error["error_label"] == "语音转写失败"
        assert error["error_message"] == "connection refused"
        assert error["previous_state"] == "VISUAL_SCREENING"

    def test_uses_current_state_when_no_state_file(self, tmp_path: Path):
        handler = PipelineErrorHandler(tmp_path)
        handler.handle_error(
            "EXPORT_FAILED", "ffmpeg error", current_state="PROCESSING"
        )

        state = json.loads((tmp_path / "state.json").read_text())
        assert state["state"] == "ERROR"


class TestShouldRetry:
    def test_upload_failed_never_retries(self):
        handler = PipelineErrorHandler("/tmp")
        assert handler.should_retry("UPLOAD_FAILED", 0) is False
        assert handler.should_retry("UPLOAD_FAILED", 1) is False

    def test_retries_up_to_max(self):
        handler = PipelineErrorHandler("/tmp")
        assert handler.should_retry("VISUAL_FAILED", 0) is True
        assert handler.should_retry("VISUAL_FAILED", 1) is True
        assert handler.should_retry("VISUAL_FAILED", 2) is True
        assert handler.should_retry("VISUAL_FAILED", 3) is False

    def test_custom_max_retries(self):
        handler = PipelineErrorHandler("/tmp")
        assert handler.should_retry("ASR_FAILED", 2, max_retries=2) is False
        assert handler.should_retry("ASR_FAILED", 1, max_retries=2) is True


class TestReadError:
    def test_returns_none_when_no_error_file(self, tmp_path: Path):
        handler = PipelineErrorHandler(tmp_path)
        assert handler.read_error() is None

    def test_returns_error_details(self, task_dir: Path):
        handler = PipelineErrorHandler(task_dir)
        handler.handle_error("VLM_FAILED", "timeout")

        error = handler.read_error()
        assert error is not None
        assert error["error_type"] == "VLM_FAILED"
        assert error["error_message"] == "timeout"
