import importlib
import json
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
        '{"api_key": "snapshot-key", "enable_vlm": true, "export_mode": "smart", "vlm_provider": "glm", "api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-5v-turbo"}'
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
                "glm",
                "https://open.bigmodel.cn/api/paas/v4",
                "glm-5v-turbo",
                "segment_multiframe",
                True,
                "smart",
                "standard",
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
            "qwen",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-vl-plus",
            "segment_multiframe",
            True,
            "smart",
            "standard",
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
                "change_detection_fusion_mode": "weighted_vote",
                "change_detection_sensitivity": "sensitive",
                "clothing_yolo_confidence": 0.4,
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

    class _FakeClothingDetector:
        def __init__(
            self,
            hist_threshold: float | None = None,
            min_scene_gap: float | None = None,
            merge_window: float | None = None,
            fusion_mode: str | None = None,
            sensitivity: str | None = None,
            yolo_confidence_threshold: float | None = None,
            frame_workers: int | None = None,
        ):
            captured["hist_threshold"] = hist_threshold
            captured["min_scene_gap"] = min_scene_gap
            captured["merge_window"] = merge_window
            captured["fusion_mode"] = fusion_mode
            captured["sensitivity"] = sensitivity
            captured["yolo_confidence_threshold"] = yolo_confidence_threshold
            captured["frame_workers"] = frame_workers

        def detect_from_frames(
            self,
            frame_records: list[dict],
            output_dir: str | None = None,
        ) -> list[dict]:
            captured["frames_count"] = len(frame_records)
            captured["output_dir"] = output_dir
            return [{"timestamp": 5.0, "similarity": 0.75, "frame_idx": 0}]

        @staticmethod
        def detect_scenes_from_candidates(
            candidates: list[dict], video_duration: float
        ) -> list[dict]:
            captured["video_duration"] = video_duration
            return [{"start_time": 0.0, "end_time": video_duration}]

    def _fake_subprocess_run(*args: object, **kwargs: object) -> object:
        frames_dir = task_dir / "frames" / "scene000"
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 4):
            (frames_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake-jpg")

        class _FakeCompletedProcess:
            returncode = 0
            stdout = b""
            stderr = b""

        return _FakeCompletedProcess()

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "ClothingChangeDetector", _FakeClothingDetector)
    monkeypatch.setattr(pipeline.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(pipeline, "_get_video_duration", lambda _p: 120.0)
    monkeypatch.setattr(pipeline, "calculate_parallelism", lambda: {"frame_workers": 2, "clip_workers": 1})

    result = pipeline.visual_prescreen.run(task_id, str(video_path), str(task_dir))

    assert result["candidates_count"] == 1
    assert captured["hist_threshold"] == 0.85
    assert captured["min_scene_gap"] == 7.0
    assert captured["merge_window"] == 25.0
    assert captured["fusion_mode"] == "weighted_vote"
    assert captured["sensitivity"] == "sensitive"
    assert captured["yolo_confidence_threshold"] == 0.4
    assert captured["frame_workers"] == 2
    assert captured["frames_count"] == 3
    assert captured["output_dir"] == str(task_dir / "scenes")
    assert captured["video_duration"] == 120.0


def test_vlm_confirm_bypasses_client_when_vlm_disabled(monkeypatch, tmp_path):
    pipeline = _reload_pipeline_module()

    task_id = "task-no-vlm"
    monkeypatch.chdir(tmp_path)
    task_dir = tmp_path / "uploads" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidates.json").write_text(
        json.dumps(
            [
                {"timestamp": 12.5, "similarity": 0.42, "frame_idx": 7},
                {"timestamp": 33.0, "similarity": 0.67, "frame_idx": 19},
            ]
        )
    )
    (task_dir / "frames").mkdir(parents=True, exist_ok=True)

    transitions: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class _FakeStateMachine:
        def __init__(self, task_dir: Path):
            self.task_dir = task_dir

        def transition(self, *args: object, **kwargs: object) -> dict[str, object]:
            transitions.append((args, kwargs))
            return {}

    class _FakeErrorHandler:
        def __init__(self, task_dir: Path):
            self.task_dir = task_dir

        def handle_error(self, *_args: object, **_kwargs: object) -> None:
            return None

    class _FailingClient:
        def __init__(self, *_args: object, **_kwargs: object):
            raise AssertionError(
                "VLMClient should not be instantiated when enable_vlm is false"
            )

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "VLMClient", _FailingClient)

    result = pipeline.vlm_confirm.run(
        task_id,
        str(task_dir),
        "",
        "qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-vl-plus",
        "segment_multiframe",
        False,
        "no_vlm",
        "standard",
    )

    confirmed_file = task_dir / "vlm" / "confirmed_segments.json"
    confirmed_segments = json.loads(confirmed_file.read_text())

    assert result == {"confirmed_count": 2, "total_candidates": 2}
    assert transitions[0][0] == ("VISUAL_SCREENING", "VLM_CONFIRMING")
    assert confirmed_segments == [
        {
            "start_time": 12.5,
            "end_time": 12.5,
            "confidence": 0.42,
            "product_info": {},
            "low_confidence": True,
        },
        {
            "start_time": 33.0,
            "end_time": 33.0,
            "confidence": 0.67,
            "product_info": {},
            "low_confidence": True,
        },
    ]


def test_vlm_confirm_skips_client_for_all_candidates_mode(monkeypatch, tmp_path):
    pipeline = _reload_pipeline_module()

    task_id = "task-all-candidates"
    monkeypatch.chdir(tmp_path)
    task_dir = tmp_path / "uploads" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidates.json").write_text(
        json.dumps([{"timestamp": 8.0, "similarity": 0.5, "frame_idx": 2}])
    )
    (task_dir / "frames").mkdir(parents=True, exist_ok=True)

    class _FailingClient:
        def __init__(self, *_args: object, **_kwargs: object):
            raise AssertionError(
                "VLMClient should not be instantiated outside smart mode"
            )

    monkeypatch.setattr(pipeline, "VLMClient", _FailingClient)

    result = pipeline.vlm_confirm.run(
        task_id,
        str(task_dir),
        "",
        "qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-vl-plus",
        "segment_multiframe",
        True,
        "all_candidates",
        "standard",
    )

    assert result == {"confirmed_count": 0, "total_candidates": 1}


def test_vlm_confirm_skips_client_for_all_scenes_mode(monkeypatch, tmp_path):
    pipeline = _reload_pipeline_module()

    task_id = "task-all-scenes"
    monkeypatch.chdir(tmp_path)
    task_dir = tmp_path / "uploads" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidates.json").write_text(json.dumps([]))
    (task_dir / "frames").mkdir(parents=True, exist_ok=True)

    class _FailingClient:
        def __init__(self, *_args: object, **_kwargs: object):
            raise AssertionError(
                "VLMClient should not be instantiated outside smart mode"
            )

    monkeypatch.setattr(pipeline, "VLMClient", _FailingClient)

    result = pipeline.vlm_confirm.run(
        task_id,
        str(task_dir),
        "",
        "qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-vl-plus",
        "segment_multiframe",
        True,
        "all_scenes",
        "standard",
    )

    assert result == {"confirmed_count": 0, "total_candidates": 0}


def test_enrich_segments_uses_task_snapshot_post_processing_controls(
    monkeypatch, tmp_path
):
    pipeline = _reload_pipeline_module()

    task_id = "task-enrich"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    video_path = task_dir / "original.mp4"
    video_path.write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "min_segment_duration_seconds": 30,
                "dedupe_window_seconds": 45,
                "allow_returned_product": False,
            }
        )
    )
    (task_dir / "vlm").mkdir(parents=True, exist_ok=True)
    (task_dir / "vlm" / "confirmed_segments.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 0.0,
                    "end_time": 40.0,
                    "product_name": "白色连衣裙",
                }
            ]
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
        def cleanup_chunks(self, _task_dir: str) -> None:
            return None

        def cleanup_frames(self, _task_dir: str) -> None:
            return None

    class _FakeWhisperClient:
        def transcribe(self, _video_path: str) -> dict[str, object]:
            return {"segments": []}

    class _FakeMatcher:
        def match(
            self, segments: list[dict[str, object]], transcript: dict[str, object]
        ) -> list[dict[str, object]]:
            captured["matched_segments"] = segments
            return segments

    class _FakeValidator:
        def __init__(
            self,
            min_duration: float,
            dedupe_window: float,
            allow_returned_product: bool,
        ):
            captured["min_duration"] = min_duration
            captured["dedupe_window"] = dedupe_window
            captured["allow_returned_product"] = allow_returned_product

        def validate(
            self, segments: list[dict[str, object]], video_duration: float
        ) -> list[dict[str, object]]:
            captured["video_duration"] = video_duration
            return segments

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "DashScopeASRClient", _FakeWhisperClient)
    monkeypatch.setattr(pipeline, "ProductNameMatcher", _FakeMatcher)
    monkeypatch.setattr(pipeline, "SegmentValidator", _FakeValidator)
    monkeypatch.setattr(pipeline, "_get_video_duration", lambda _video_path: 512.0)

    result = pipeline.enrich_segments.run(task_id, str(task_dir))

    assert result == {"segments_count": 1, "validated_count": 1}
    assert captured["min_duration"] == 30
    assert captured["dedupe_window"] == 45
    assert captured["allow_returned_product"] is False
    assert captured["video_duration"] == 512.0


def test_process_clips_off_skips_subtitle_generation_and_burn(monkeypatch, tmp_path):
    pipeline = _reload_pipeline_module()

    task_id = "task-off"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "original.mp4").write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "subtitle_mode": "off",
            }
        )
    )
    (task_dir / "enriched_segments.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 1.0,
                    "end_time": 8.0,
                    "product_name": "白色连衣裙",
                    "text": "欢迎来到直播间",
                }
            ]
        )
    )

    captured: dict[str, object] = {"generate_calls": 0}

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
        def cleanup_srt(self, _task_dir: str) -> None:
            return None

        def cleanup_frames(self, _task_dir: str) -> None:
            return None

    class _FakeSRTGenerator:
        def resolve_phase1_export_mode(
            self, requested_mode: str, has_text: bool, has_word_timing: bool = False
        ) -> str:
            return "off" if not has_text else requested_mode

        def generate(
            self,
            _segments: list[dict[str, object]],
            _output_path: str,
            mode: str = "basic",
            **_kwargs: object,
        ) -> str:
            current = captured.get("generate_calls")
            captured["generate_calls"] = (
                current if isinstance(current, int) else 0
            ) + 1
            return _output_path

    class _FakeFFmpegBuilder:
        def process_clip(self, **kwargs: object) -> dict[str, object]:
            captured["srt_path"] = kwargs["srt_path"]
            captured["subtitle_mode"] = kwargs["subtitle_mode"]
            return {
                "output_path": str(task_dir / "clips" / "clip_000.mp4"),
                "thumbnail_path": str(task_dir / "thumbnails" / "clip_000.jpg"),
                "duration": 7.0,
            }

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "SRTGenerator", _FakeSRTGenerator)
    monkeypatch.setattr(pipeline, "FFmpegBuilder", _FakeFFmpegBuilder)

    result = pipeline.process_clips.run(task_id, str(task_dir))

    assert result == {"clips_count": 1, "output_dir": str(task_dir / "clips")}
    assert captured["generate_calls"] == 0
    assert captured["srt_path"] is None
    assert captured["subtitle_mode"] == "off"


def test_process_clips_basic_falls_back_to_no_subtitle_export_when_srt_generation_fails(
    monkeypatch, tmp_path
):
    pipeline = _reload_pipeline_module()

    task_id = "task-basic"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "original.mp4").write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "subtitle_mode": "basic",
            }
        )
    )
    (task_dir / "enriched_segments.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 1.0,
                    "end_time": 8.0,
                    "product_name": "白色连衣裙",
                    "text": "欢迎来到直播间",
                }
            ]
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
        def cleanup_srt(self, _task_dir: str) -> None:
            return None

        def cleanup_frames(self, _task_dir: str) -> None:
            return None

    class _FakeSRTGenerator:
        def resolve_phase1_export_mode(
            self, requested_mode: str, has_text: bool, has_word_timing: bool = False
        ) -> str:
            return "off" if not has_text else requested_mode

        def generate(
            self,
            _segments: list[dict[str, object]],
            _output_path: str,
            mode: str = "basic",
            **_kwargs: object,
        ) -> str:
            raise RuntimeError("SRT boom")

    class _FakeFFmpegBuilder:
        def process_clip(self, **kwargs: object) -> dict[str, object]:
            captured["srt_path"] = kwargs["srt_path"]
            captured["subtitle_mode"] = kwargs["subtitle_mode"]
            return {
                "output_path": str(task_dir / "clips" / "clip_000.mp4"),
                "thumbnail_path": str(task_dir / "thumbnails" / "clip_000.jpg"),
                "duration": 7.0,
            }

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "SRTGenerator", _FakeSRTGenerator)
    monkeypatch.setattr(pipeline, "FFmpegBuilder", _FakeFFmpegBuilder)

    result = pipeline.process_clips.run(task_id, str(task_dir))

    assert result == {"clips_count": 1, "output_dir": str(task_dir / "clips")}
    assert captured["srt_path"] is None
    assert captured["subtitle_mode"] == "off"


def test_process_clips_downgrades_karaoke_to_basic_and_threads_subtitle_settings(
    monkeypatch, tmp_path
):
    pipeline = _reload_pipeline_module()

    task_id = "task-karaoke"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "original.mp4").write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "subtitle_mode": "karaoke",
                "subtitle_position": "custom",
                "subtitle_template": "karaoke",
                "custom_position_y": 72,
                "ffmpeg_preset": "veryfast",
                "ffmpeg_crf": 21,
            }
        )
    )
    (task_dir / "enriched_segments.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 1.0,
                    "end_time": 8.0,
                    "product_name": "白色连衣裙",
                    "text": "欢迎来到直播间",
                }
            ]
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
        def cleanup_srt(self, _task_dir: str) -> None:
            return None

        def cleanup_frames(self, _task_dir: str) -> None:
            return None

    class _FakeSRTGenerator:
        def resolve_phase1_export_mode(
            self, requested_mode: str, has_text: bool, has_word_timing: bool = False
        ) -> str:
            if not has_text:
                return "off"
            return "karaoke" if requested_mode == "karaoke" else requested_mode

        def generate(
            self,
            _segments: list[dict[str, object]],
            output_path: str,
            mode: str = "basic",
            **_kwargs: object,
        ) -> str:
            captured["generated_srt_path"] = output_path
            captured["generated_mode"] = mode
            return output_path

    class _FakeFFmpegBuilder:
        def process_clip(self, **kwargs: object) -> dict[str, object]:
            captured["srt_path"] = kwargs["srt_path"]
            captured["subtitle_mode"] = kwargs["subtitle_mode"]
            captured["subtitle_position"] = kwargs["subtitle_position"]
            captured["subtitle_template"] = kwargs["subtitle_template"]
            captured["custom_position_y"] = kwargs["custom_position_y"]
            captured["ffmpeg_preset"] = kwargs["ffmpeg_preset"]
            captured["ffmpeg_crf"] = kwargs["ffmpeg_crf"]
            return {
                "output_path": str(task_dir / "clips" / "clip_000.mp4"),
                "thumbnail_path": str(task_dir / "thumbnails" / "clip_000.jpg"),
                "duration": 7.0,
            }

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "SRTGenerator", _FakeSRTGenerator)
    monkeypatch.setattr(pipeline, "FFmpegBuilder", _FakeFFmpegBuilder)

    result = pipeline.process_clips.run(task_id, str(task_dir))

    assert result == {"clips_count": 1, "output_dir": str(task_dir / "clips")}
    assert captured["srt_path"] == captured["generated_srt_path"]
    assert str(captured["generated_srt_path"]).endswith(".ass")
    assert captured["generated_mode"] == "karaoke"
    assert captured["subtitle_mode"] == "karaoke"
    assert captured["subtitle_position"] == "custom"
    assert captured["subtitle_template"] == "karaoke"
    assert captured["custom_position_y"] == 72
    assert captured["ffmpeg_preset"] == "veryfast"
    assert captured["ffmpeg_crf"] == 21


def test_process_clips_writes_clip_metadata_for_listing(monkeypatch, tmp_path):
    pipeline = _reload_pipeline_module()

    task_id = "task-meta"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "original.mp4").write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "api_key": "snapshot-key",
                "subtitle_mode": "off",
            }
        )
    )
    (task_dir / "enriched_segments.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 12.0,
                    "end_time": 42.0,
                    "product_name": "白色连衣裙",
                    "confidence": 0.88,
                    "text": "欢迎来到直播间",
                }
            ]
        )
    )

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
        def cleanup_srt(self, _task_dir: str) -> None:
            return None

        def cleanup_frames(self, _task_dir: str) -> None:
            return None

    class _FakeSRTGenerator:
        def resolve_phase1_export_mode(
            self, requested_mode: str, has_text: bool, has_word_timing: bool = False
        ) -> str:
            return "off"

    class _FakeFFmpegBuilder:
        def process_clip(self, **kwargs: object) -> dict[str, object]:
            output_path = Path(str(kwargs["output_path"]))
            thumbnail_path = Path(str(kwargs["thumbnail_path"]))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-mp4-data")
            thumbnail_path.write_bytes(b"fake-jpg-data")
            return {
                "output_path": str(output_path),
                "thumbnail_path": str(thumbnail_path),
                "duration": 30.0,
            }

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "TempFileCleaner", _FakeCleaner)
    monkeypatch.setattr(pipeline, "SRTGenerator", _FakeSRTGenerator)
    monkeypatch.setattr(pipeline, "FFmpegBuilder", _FakeFFmpegBuilder)

    result = pipeline.process_clips.run(task_id, str(task_dir))

    meta_file = task_dir / "clips" / "clip_000_meta.json"
    assert result == {"clips_count": 1, "output_dir": str(task_dir / "clips")}
    assert meta_file.exists()
    assert json.loads(meta_file.read_text()) == {
        "product_name": "白色连衣裙",
        "duration": 30.0,
        "start_time": 12.0,
        "end_time": 42.0,
        "confidence": 0.88,
    }


def test_enrich_segments_uses_candidates_directly_for_all_candidates_mode(
    monkeypatch, tmp_path
):
    pipeline = _reload_pipeline_module()

    task_id = "task-candidate-mode"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "original.mp4").write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps({"api_key": "", "enable_vlm": True, "export_mode": "all_candidates"})
    )
    (task_dir / "candidates.json").write_text(
        json.dumps(
            [
                {"timestamp": 10.0, "similarity": 0.4, "frame_idx": 3},
                {"timestamp": 28.0, "similarity": 0.9, "frame_idx": 9},
            ]
        )
    )

    transitions: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class _FakeStateMachine:
        def __init__(self, task_dir: Path):
            self.task_dir = task_dir

        def transition(self, *args: object, **kwargs: object) -> dict[str, object]:
            transitions.append((args, kwargs))
            return {}

    class _FakeErrorHandler:
        def __init__(self, task_dir: Path):
            self.task_dir = task_dir

        def handle_error(self, *_args: object, **_kwargs: object) -> None:
            return None

    class _FakeASR:
        def transcribe(self, *_args: object, **_kwargs: object):
            return [
                {"text": "第一段字幕", "start_time": 9.5, "end_time": 10.5},
                {"text": "第二段字幕", "start_time": 27.5, "end_time": 28.5},
            ]

    class _UnusedMatcher:
        def match(self, *_args: object, **_kwargs: object):
            raise AssertionError("Matcher should be skipped for all_candidates mode")

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "_create_asr_client", lambda _s: _FakeASR())
    monkeypatch.setattr(pipeline, "ProductNameMatcher", _UnusedMatcher)

    result = pipeline.enrich_segments.run(task_id, str(task_dir))

    enriched = json.loads((task_dir / "enriched_segments.json").read_text())
    assert result == {"segments_count": 2, "validated_count": 2}
    assert transitions[-1][0] == ("TRANSCRIBING", "PROCESSING")
    assert enriched == [
        {
            "start_time": 10.0,
            "end_time": 10.0,
            "confidence": 0.4,
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "export_mode",
            "text": "第一段字幕",
        },
        {
            "start_time": 28.0,
            "end_time": 28.0,
            "confidence": 0.9,
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "export_mode",
            "text": "第二段字幕",
        },
    ]


def test_enrich_segments_uses_scenes_directly_for_all_scenes_mode(
    monkeypatch, tmp_path
):
    pipeline = _reload_pipeline_module()

    task_id = "task-scene-mode"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "original.mp4").write_bytes(b"video")
    (task_dir / "settings.json").write_text(
        json.dumps({"api_key": "", "enable_vlm": True, "export_mode": "all_scenes", "asr_enabled": True, "asr_provider": "dashscope"})
    )
    scenes_dir = task_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "scenes.json").write_text(
        json.dumps(
            [
                {"start_time": 0.0, "end_time": 12.0},
                {"start_time": 15.0, "end_time": 40.0},
            ]
        )
    )

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

    class _FakeASR:
        def transcribe(self, *_args: object, **_kwargs: object):
            return [
                {"text": "开场介绍", "start_time": 0.5, "end_time": 4.0},
                {"text": "第二段介绍", "start_time": 16.0, "end_time": 21.0},
            ]

    monkeypatch.setattr(pipeline, "TaskStateMachine", _FakeStateMachine)
    monkeypatch.setattr(pipeline, "PipelineErrorHandler", _FakeErrorHandler)
    monkeypatch.setattr(pipeline, "_create_asr_client", lambda _s: _FakeASR())

    result = pipeline.enrich_segments.run(task_id, str(task_dir))

    enriched = json.loads((task_dir / "enriched_segments.json").read_text())
    assert result == {"segments_count": 2, "validated_count": 2}
    assert enriched == [
        {
            "start_time": 0.0,
            "end_time": 12.0,
            "confidence": 0.0,
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "export_mode",
            "text": "开场介绍",
        },
        {
            "start_time": 15.0,
            "end_time": 40.0,
            "confidence": 0.0,
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "export_mode",
            "text": "第二段介绍",
        },
    ]
