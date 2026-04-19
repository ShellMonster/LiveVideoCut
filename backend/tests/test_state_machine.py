"""Tests for TaskStateMachine — TDD first."""

import json
from pathlib import Path

import pytest

from app.services.state_machine import TaskStateMachine, InvalidTransitionError


class TestValidTransitions:
    """Happy path: each state transitions to its valid next state."""

    def test_uploaded_to_extracting(self):
        sm = TaskStateMachine()
        assert sm.transition("UPLOADED", "EXTRACTING_FRAMES") == "EXTRACTING_FRAMES"

    def test_extracting_to_scene_detecting(self):
        sm = TaskStateMachine()
        assert (
            sm.transition("EXTRACTING_FRAMES", "SCENE_DETECTING") == "SCENE_DETECTING"
        )

    def test_scene_detecting_to_visual_screening(self):
        sm = TaskStateMachine()
        assert (
            sm.transition("SCENE_DETECTING", "VISUAL_SCREENING") == "VISUAL_SCREENING"
        )

    def test_visual_screening_to_vlm_confirming(self):
        sm = TaskStateMachine()
        assert sm.transition("VISUAL_SCREENING", "VLM_CONFIRMING") == "VLM_CONFIRMING"

    def test_vlm_confirming_to_transcribing(self):
        sm = TaskStateMachine()
        assert sm.transition("VLM_CONFIRMING", "TRANSCRIBING") == "TRANSCRIBING"

    def test_transcribing_to_processing(self):
        sm = TaskStateMachine()
        assert sm.transition("TRANSCRIBING", "PROCESSING") == "PROCESSING"

    def test_processing_to_completed(self):
        sm = TaskStateMachine()
        assert sm.transition("PROCESSING", "COMPLETED") == "COMPLETED"


class TestErrorTransition:
    """Any state can transition to ERROR."""

    @pytest.mark.parametrize(
        "state",
        [
            "UPLOADED",
            "EXTRACTING_FRAMES",
            "SCENE_DETECTING",
            "VISUAL_SCREENING",
            "VLM_CONFIRMING",
            "TRANSCRIBING",
            "PROCESSING",
        ],
    )
    def test_any_state_to_error(self, state):
        sm = TaskStateMachine()
        assert sm.transition(state, "ERROR") == "ERROR"


class TestInvalidTransitions:
    """Invalid transitions raise InvalidTransitionError."""

    def test_uploaded_to_completed(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("UPLOADED", "COMPLETED")

    def test_completed_to_uploaded(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("COMPLETED", "UPLOADED")

    def test_error_to_uploaded(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("ERROR", "UPLOADED")

    def test_skip_step(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("UPLOADED", "SCENE_DETECTING")

    def test_backward_transition(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("SCENE_DETECTING", "EXTRACTING_FRAMES")

    def test_same_state(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("UPLOADED", "UPLOADED")

    def test_unknown_state(self):
        sm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("UNKNOWN", "COMPLETED")


class TestStatePersistence:
    """State transitions persist to state.json."""

    def test_persist_creates_state_file(self, tmp_path):
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        sm = TaskStateMachine(task_dir)
        sm.transition("UPLOADED", "EXTRACTING_FRAMES")

        state_file = task_dir / "state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["state"] == "EXTRACTING_FRAMES"

    def test_persist_with_message(self, tmp_path):
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        sm = TaskStateMachine(task_dir)
        sm.transition("UPLOADED", "EXTRACTING_FRAMES", message="开始抽帧...")

        data = json.loads((task_dir / "state.json").read_text())
        assert data["message"] == "开始抽帧..."

    def test_persist_with_step(self, tmp_path):
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        sm = TaskStateMachine(task_dir)
        sm.transition("UPLOADED", "EXTRACTING_FRAMES", step="1/7")

        data = json.loads((task_dir / "state.json").read_text())
        assert data["step"] == "1/7"

    def test_read_state(self, tmp_path):
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        sm = TaskStateMachine(task_dir)
        sm.transition("UPLOADED", "EXTRACTING_FRAMES", message="抽帧中", step="1/7")

        state = sm.read_state()
        assert state["state"] == "EXTRACTING_FRAMES"
        assert state["message"] == "抽帧中"
        assert state["step"] == "1/7"

    def test_read_state_no_file(self, tmp_path):
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        sm = TaskStateMachine(task_dir)
        state = sm.read_state()
        assert state["state"] == "UPLOADED"

    def test_error_persists(self, tmp_path):
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        sm = TaskStateMachine(task_dir)
        sm.transition("UPLOADED", "ERROR", message="抽帧失败")

        data = json.loads((task_dir / "state.json").read_text())
        assert data["state"] == "ERROR"
        assert data["message"] == "抽帧失败"


class TestGetAllStates:
    """Utility: list all valid states."""

    def test_states_list(self):
        sm = TaskStateMachine()
        states = sm.get_states()
        assert "UPLOADED" in states
        assert "COMPLETED" in states
        assert "ERROR" not in states
        assert "LLM_ANALYZING" in states
        assert states[-1] == "COMPLETED"
