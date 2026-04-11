import importlib
import sys
from pathlib import Path
from typing import Any


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
