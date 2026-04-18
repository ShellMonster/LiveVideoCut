# pyright: reportImplicitRelativeImport=false
import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

from app.services.vlm_confirmor import VLMConfirmor


def _reload_pipeline_module():
    sys.modules.pop("app.tasks.pipeline", None)
    return importlib.import_module("app.tasks.pipeline")


def _make_vlm_response(is_different: bool = True, confidence: float = 0.85) -> str:
    return json.dumps(
        {
            "is_different": is_different,
            "confidence": confidence,
            "dimensions": {},
            "product_1": {"type": "上衣", "color": "红色", "style": "修身上衣"},
            "product_2": {"type": "裙子", "color": "蓝色", "style": "连衣裙"},
        }
    )


def _write_frames_json(frames_dir: Path, timestamps: list[float]) -> None:
    frames_json = []
    scene_dir = frames_dir / "scene000"
    scene_dir.mkdir(parents=True, exist_ok=True)
    for idx, timestamp in enumerate(timestamps, start=1):
        path = scene_dir / f"frame_{idx:05d}.jpg"
        path.write_bytes(b"\xff\xd8fake")
        frames_json.append(
            {
                "path": str(path),
                "timestamp": timestamp,
                "scene_idx": 0,
            }
        )
    (frames_dir / "frames.json").write_text(
        json.dumps(frames_json, ensure_ascii=False, indent=2)
    )


def test_adjacent_frames_mode_keeps_existing_two_image_path(tmp_path):
    frames_dir = tmp_path / "frames"
    _write_frames_json(frames_dir, [0.0, 1.0, 2.0])

    client = MagicMock()
    client.compare_frames.return_value = _make_vlm_response()
    confirmor = VLMConfirmor(vlm_client=client)

    result = confirmor.confirm_candidates(
        [{"timestamp": 1.0, "frame_idx": 1, "end_time": 2.0}],
        str(frames_dir),
        review_mode="adjacent_frames",
    )

    assert len(result) == 1
    client.compare_frames.assert_called_once()
    client.compare_frames_multi.assert_not_called()


def test_segment_multiframe_samples_start_middle_end_frames(tmp_path):
    frames_dir = tmp_path / "frames"
    _write_frames_json(frames_dir, [0.0, 1.0, 2.0, 3.0, 4.0])

    client = MagicMock()
    client.compare_frames_multi.return_value = _make_vlm_response()
    confirmor = VLMConfirmor(vlm_client=client)

    result = confirmor.confirm_candidates(
        [{"timestamp": 1.0, "frame_idx": 2, "start_time": 0.0, "end_time": 4.0}],
        str(frames_dir),
        review_mode="segment_multiframe",
    )

    assert len(result) == 1
    image_paths, prompt = client.compare_frames_multi.call_args.args
    assert [Path(path).name for path in image_paths] == [
        "frame_00001.jpg",
        "frame_00003.jpg",
        "frame_00005.jpg",
    ]
    assert isinstance(prompt, str)
    client.compare_frames.assert_not_called()


def test_segment_multiframe_falls_back_to_adjacent_when_boundaries_missing(tmp_path):
    frames_dir = tmp_path / "frames"
    _write_frames_json(frames_dir, [0.0, 1.0, 2.0])

    client = MagicMock()
    client.compare_frames.return_value = _make_vlm_response()
    confirmor = VLMConfirmor(vlm_client=client)

    result = confirmor.confirm_candidates(
        [{"timestamp": 1.0, "frame_idx": 1}],
        str(frames_dir),
        review_mode="segment_multiframe",
    )

    assert len(result) == 1
    client.compare_frames.assert_called_once()
    client.compare_frames_multi.assert_not_called()


def test_start_pipeline_threads_review_mode_from_settings_snapshot(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("VLM_API_KEY", "env-key")
    monkeypatch.setenv(
        "VLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    monkeypatch.setenv("VLM_MODEL", "qwen-vl-plus")

    pipeline = _reload_pipeline_module()

    task_id = "task-review-mode"
    task_dir_path = tmp_path / task_id
    task_dir_path.mkdir(parents=True, exist_ok=True)
    (task_dir_path / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "review_mode": "adjacent_frames",
            }
        )
    )
    file_path = str(task_dir_path / "original.mp4")

    stage_calls: list[tuple[str, tuple[object, ...]]] = []

    class _StageStub:
        def __init__(self, name: str):
            self.name = name

        def si(self, *args: object) -> str:
            stage_calls.append((self.name, args))
            return f"{self.name}-sig"

    monkeypatch.setattr(pipeline, "visual_prescreen", _StageStub("visual_prescreen"))
    monkeypatch.setattr(pipeline, "vlm_confirm", _StageStub("vlm_confirm"))
    monkeypatch.setattr(pipeline, "enrich_segments", _StageStub("enrich_segments"))
    monkeypatch.setattr(pipeline, "process_clips", _StageStub("process_clips"))

    class _FakeChain:
        def __init__(self, signatures: tuple[object, ...]):
            self.signatures = signatures

        def apply_async(self) -> None:
            return None

    monkeypatch.setattr(
        pipeline, "chain", lambda *signatures: _FakeChain(signatures), raising=False
    )

    pipeline.start_pipeline.run(task_id, file_path)

    assert stage_calls[1] == (
        "vlm_confirm",
        (
            task_id,
            str(task_dir_path),
            "snapshot-key",
            "qwen",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-vl-plus",
            "adjacent_frames",
        ),
    )
