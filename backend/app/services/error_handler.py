import json
import logging
from pathlib import Path

from app.services.state_machine import TaskStateMachine

logger = logging.getLogger(__name__)


class PipelineErrorHandler:
    """Centralized error handling for the pipeline."""

    ERROR_TYPES = {
        "UPLOAD_FAILED": "上传失败",
        "VISUAL_FAILED": "视觉分析失败",
        "VLM_FAILED": "VLM确认失败",
        "ASR_FAILED": "语音转写失败",
        "EXPORT_FAILED": "视频导出失败",
    }

    def __init__(self, task_dir: str | Path):
        self.task_dir = Path(task_dir)
        self.sm = TaskStateMachine(task_dir=self.task_dir)

    def handle_error(
        self, error_type: str, error_message: str, current_state: str = ""
    ) -> None:
        """Transition state to ERROR and save error details to state.json."""
        label = self.ERROR_TYPES.get(error_type, error_type)
        logger.error(
            "Pipeline error [%s]: %s (task_dir=%s)",
            error_type,
            error_message,
            self.task_dir,
        )

        state = self.sm.read_state().get("state", current_state)
        self.sm.transition(
            state,
            "ERROR",
            message=f"{label}: {error_message}",
            step=error_type.lower(),
        )

        # 保存详细错误信息
        error_file = self.task_dir / "error.json"
        error_data = {
            "error_type": error_type,
            "error_label": label,
            "error_message": error_message,
            "previous_state": state,
        }
        error_file.write_text(json.dumps(error_data, ensure_ascii=False, indent=2))

    def should_retry(self, error_type: str, attempt: int, max_retries: int = 3) -> bool:
        """Determine if task should be retried based on error type and attempt count."""
        # UPLOAD_FAILED 不重试（文件问题）
        if error_type == "UPLOAD_FAILED":
            return False
        return attempt < max_retries

    def read_error(self) -> dict | None:
        """Read error details from error.json if it exists."""
        error_file = self.task_dir / "error.json"
        if not error_file.exists():
            return None
        return json.loads(error_file.read_text())
