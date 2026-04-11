import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def _reload_pipeline_module():
    sys.modules.pop("app.tasks.pipeline", None)
    return importlib.import_module("app.tasks.pipeline")


class _StageStub:
    def __init__(self, name: str, calls: list[tuple[str, tuple[object, ...]]]):
        self.name = name
        self.calls = calls

    def si(self, *args: object) -> str:
        self.calls.append((self.name, args))
        return f"{self.name}-sig"


def test_start_pipeline_dispatches_full_task_chain(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("VLM_API_KEY", "env-key")
    monkeypatch.setenv(
        "VLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    monkeypatch.setenv("VLM_MODEL", "qwen-vl-plus")

    pipeline = _reload_pipeline_module()

    task_id = "task-123"
    task_dir_path = Path("/tmp/uploads") / task_id
    task_dir_path.mkdir(parents=True, exist_ok=True)
    (task_dir_path / "settings.json").write_text(
        '{"api_key": "snapshot-key", "vlm_provider": "glm", "api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-5v-turbo"}'
    )
    task_dir = str(task_dir_path)
    file_path = str(task_dir_path / "original.mp4")

    stage_calls: list[tuple[str, tuple[object, ...]]] = []
    chain_calls: list[tuple[object, ...]] = []
    apply_async_called: list[bool] = []

    monkeypatch.setattr(
        pipeline, "visual_prescreen", _StageStub("visual_prescreen", stage_calls)
    )
    monkeypatch.setattr(pipeline, "vlm_confirm", _StageStub("vlm_confirm", stage_calls))
    monkeypatch.setattr(
        pipeline, "enrich_segments", _StageStub("enrich_segments", stage_calls)
    )
    monkeypatch.setattr(
        pipeline, "process_clips", _StageStub("process_clips", stage_calls)
    )

    class _FakeChain:
        def __init__(self, signatures: tuple[object, ...]):
            self.signatures = signatures

        def apply_async(self) -> None:
            apply_async_called.append(True)

    def fake_chain(*signatures: object) -> _FakeChain:
        chain_calls.append(signatures)
        return _FakeChain(signatures)

    monkeypatch.setattr(pipeline, "chain", fake_chain, raising=False)

    result = pipeline.start_pipeline.run(task_id, file_path)

    assert result == task_id
    assert stage_calls == [
        ("visual_prescreen", (task_id, file_path, task_dir)),
        (
            "vlm_confirm",
            (
                task_id,
                task_dir,
                "snapshot-key",
                "https://open.bigmodel.cn/api/paas/v4",
                "glm-5v-turbo",
            ),
        ),
        ("enrich_segments", (task_id, task_dir)),
        ("process_clips", (task_id, task_dir)),
    ]
    assert chain_calls == [
        (
            "visual_prescreen-sig",
            "vlm_confirm-sig",
            "enrich_segments-sig",
            "process_clips-sig",
        )
    ]
    assert apply_async_called == [True]


def test_start_pipeline_falls_back_to_environment_without_settings_snapshot(
    monkeypatch,
):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("VLM_API_KEY", "env-key")
    monkeypatch.setenv(
        "VLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    monkeypatch.setenv("VLM_MODEL", "qwen-vl-plus")

    pipeline = _reload_pipeline_module()

    task_id = "task-456"
    task_dir = str(Path("/tmp/uploads") / task_id)
    file_path = str(Path(task_dir) / "original.mp4")

    stage_calls: list[tuple[str, tuple[object, ...]]] = []

    monkeypatch.setattr(
        pipeline, "visual_prescreen", _StageStub("visual_prescreen", stage_calls)
    )
    monkeypatch.setattr(pipeline, "vlm_confirm", _StageStub("vlm_confirm", stage_calls))
    monkeypatch.setattr(
        pipeline, "enrich_segments", _StageStub("enrich_segments", stage_calls)
    )
    monkeypatch.setattr(
        pipeline, "process_clips", _StageStub("process_clips", stage_calls)
    )

    class _FakeChain:
        def __init__(self, signatures: tuple[object, ...]):
            self.signatures = signatures

        def apply_async(self) -> None:
            return None

    monkeypatch.setattr(
        pipeline, "chain", lambda *signatures: _FakeChain(signatures), raising=False
    )

    result = pipeline.start_pipeline.run(task_id, file_path)

    assert result == task_id
    assert stage_calls[1] == (
        "vlm_confirm",
        (
            task_id,
            task_dir,
            "env-key",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-vl-plus",
        ),
    )


def test_visual_prescreen_uses_task_snapshot_segmentation_controls(
    monkeypatch, tmp_path
):
    pipeline = _reload_pipeline_module()

    task_id = "task-visual"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    video_path = task_dir / "original.mp4"
    video_path.write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "scene_threshold": 33.5,
                "frame_sample_fps": 4,
                "recall_cooldown_seconds": 7,
                "candidate_looseness": "loose",
            }
        )
    )

    captured: dict[str, object] = {}

    class _FakeStateMachine:
        def __init__(self, task_dir: Path):
            self.task_dir = task_dir

        def transition(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {}

    class _FakeErrorHandler:
        def __init__(self, task_dir: Path):
            self.task_dir = task_dir

        def handle_error(self, *_args: object, **_kwargs: object) -> None:
            return None

    class _FakeCleaner:
        def cleanup_frames(self, _task_dir: str) -> None:
            return None

    class _FakeDetector:
        def detect(
            self,
            video_path: str,
            output_dir: str | None = None,
            threshold: float | None = None,
        ) -> list[dict[str, float]]:
            captured["scene_threshold"] = threshold
            captured["scene_output_dir"] = output_dir
            return [{"start_time": 0.0, "end_time": 5.0}]

    class _FakeExtractor:
        def extract(
            self,
            video_path: str,
            scenes: list[dict[str, float]],
            output_dir: str,
            sample_fps: int,
        ) -> list[dict[str, object]]:
            captured["frame_sample_fps"] = sample_fps
            captured["frames_output_dir"] = output_dir
            return [
                {
                    "path": str(task_dir / "frames" / "frame_00001.jpg"),
                    "timestamp": 1.0,
                    "scene_idx": 0,
                },
                {
                    "path": str(task_dir / "frames" / "frame_00002.jpg"),
                    "timestamp": 9.0,
                    "scene_idx": 0,
                },
            ]

    class _FakeEncoder:
        def encode_batch(self, frame_paths: list[str]) -> np.ndarray:
            return np.ones((len(frame_paths), 4), dtype=np.float32)

    class _FakeAnalyzer:
        def analyze(
            self,
            embeddings: np.ndarray,
            frame_timestamps: list[float],
            window_size: int | None = None,
            cooldown_seconds: float | None = None,
            candidate_looseness: str = "standard",
        ) -> list[dict[str, object]]:
            captured["recall_cooldown_seconds"] = cooldown_seconds
            captured["candidate_looseness"] = candidate_looseness
            return [
                {
                    "timestamp": frame_timestamps[0],
                    "similarity": 0.75,
                    "frame_idx": 0,
                }
            ]

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "SceneDetector", _FakeDetector)
    monkeypatch.setattr(pipeline, "FrameExtractor", _FakeExtractor)
    monkeypatch.setattr(pipeline, "FashionSigLIPEncoder", _FakeEncoder)
    monkeypatch.setattr(pipeline, "AdaptiveSimilarityAnalyzer", _FakeAnalyzer)

    result = pipeline.visual_prescreen.run(task_id, str(video_path), str(task_dir))

    assert result["candidates_count"] == 1
    assert captured == {
        "scene_threshold": 33.5,
        "scene_output_dir": str(task_dir / "scenes"),
        "frame_sample_fps": 4,
        "frames_output_dir": str(task_dir / "frames"),
        "recall_cooldown_seconds": 7,
        "candidate_looseness": "loose",
    }
