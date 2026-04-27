import json
import subprocess
import time
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_visual_prescreen(task_id: str, video_path: str, task_dir: str) -> dict[str, Any]:
    from app.tasks.pipeline import (
        TaskStateMachine,
        PipelineErrorHandler,
        TempFileCleaner,
        ClothingChangeDetector,
        _load_task_settings,
        _log_elapsed,
        _get_video_duration,
    )

    task_path = Path(task_dir)
    settings = _load_task_settings(task_path)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    stage_started_at = time.perf_counter()
    sm.transition("UPLOADED", "EXTRACTING_FRAMES", step="extracting_frames")

    frames_dir = task_path / "frames" / "scene000"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_pattern = str(frames_dir / "frame_%05d.jpg")
    sample_fps = settings.frame_sample_fps

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            f"fps={sample_fps}",
            "-q:v",
            "2",
            frame_pattern,
        ],
        capture_output=True,
        timeout=600,
        check=True,
    )

    frames = []
    for jpg in sorted(frames_dir.glob("frame_*.jpg")):
        frame_num = int(jpg.stem.split("_")[1])
        frames.append(
            {
                "path": str(jpg),
                "timestamp": round((frame_num - 1) / sample_fps, 3),
                "scene_idx": 0,
            }
        )
    (task_path / "frames" / "frames.json").write_text(
        json.dumps(frames, ensure_ascii=False, indent=2)
    )
    logger.info("Extracted %d frames at %.2f fps", len(frames), sample_fps)
    _log_elapsed("visual_prescreen.extract_frames", stage_started_at)

    stage_started_at = time.perf_counter()
    sm.transition("EXTRACTING_FRAMES", "SCENE_DETECTING", step="scene_detecting")

    clothing_detector = ClothingChangeDetector(
        hist_threshold=0.85,
        min_scene_gap=float(settings.recall_cooldown_seconds),
        merge_window=25.0,
    )
    candidates = clothing_detector.detect_from_frames(
        frames,
        output_dir=str(task_path / "scenes"),
    )
    _log_elapsed("visual_prescreen.detect_changes", stage_started_at)
    sm.transition("SCENE_DETECTING", "VISUAL_SCREENING", step="visual_screening")

    # 同时生成 scenes.json（供 all_scenes 模式使用）
    video_duration = _get_video_duration(video_path)
    scenes = ClothingChangeDetector.detect_scenes_from_candidates(
        candidates,
        video_duration,
    )
    scenes_dir = task_path / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "scenes.json").write_text(
        json.dumps(scenes, ensure_ascii=False, indent=2),
    )

    candidates_file = task_path / "candidates.json"
    candidates_file.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))

    return {
        "candidates_count": len(candidates),
        "scenes_count": len(scenes),
        "frames_count": len(frames),
    }
