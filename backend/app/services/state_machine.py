import json
from pathlib import Path

VALID_TRANSITIONS: dict[str, list[str]] = {
    "UPLOADED": ["EXTRACTING_FRAMES"],
    "EXTRACTING_FRAMES": ["SCENE_DETECTING"],
    "SCENE_DETECTING": ["VISUAL_SCREENING"],
    "VISUAL_SCREENING": ["VLM_CONFIRMING"],
    "VLM_CONFIRMING": ["TRANSCRIBING"],
    "TRANSCRIBING": ["PROCESSING", "LLM_ANALYZING"],
    "LLM_ANALYZING": ["TRANSCRIBING"],
    "PROCESSING": ["COMPLETED"],
}

ALL_STATES = list(VALID_TRANSITIONS.keys()) + ["ERROR"]


class InvalidTransitionError(Exception):
    def __init__(self, current: str, new: str):
        self.current = current
        self.new = new
        super().__init__(f"Invalid transition: {current} → {new}")


class TaskStateMachine:
    def __init__(self, task_dir: Path | None = None):
        self.task_dir = task_dir

    def transition(
        self, current: str, new: str, *, message: str = "", step: str = ""
    ) -> str:
        allowed = VALID_TRANSITIONS.get(current, [])
        if new not in allowed and new != "ERROR":
            raise InvalidTransitionError(current, new)

        if self.task_dir:
            self._persist(new, message=message, step=step)

        return new

    def read_state(self) -> dict:
        if not self.task_dir:
            return {"state": "UPLOADED"}

        state_file = self.task_dir / "state.json"
        if not state_file.exists():
            return {"state": "UPLOADED"}

        return json.loads(state_file.read_text())

    def get_states(self) -> list[str]:
        return list(VALID_TRANSITIONS.keys()) + ["COMPLETED"]

    def _persist(self, state: str, *, message: str = "", step: str = "") -> None:
        if not self.task_dir:
            return

        state_file = self.task_dir / "state.json"
        data: dict = {"state": state}
        if message:
            data["message"] = message
        if step:
            data["step"] = step

        state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        try:
            from app.services.list_index import refresh_task_index

            refresh_task_index(self.task_dir.parent, self.task_dir.name)
        except Exception:
            pass
