import datetime
from pathlib import Path
from typing import Any

from starlette.responses import JSONResponse

from app.api.settings import SENSITIVE_FIELDS
from app.api.validation import is_safe_task_dir, is_task_id
from app.config import UPLOAD_DIR
from app.services.memory_cache import path_fingerprint
from app.utils.json_io import read_json_silent as _read_json, write_json


def task_dir_or_404(task_id: str) -> Path | JSONResponse:
    if not is_task_id(task_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id format"})
    task_dir = UPLOAD_DIR / task_id
    if not task_dir.exists():
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return task_dir


def deletable_task_dir_or_404(task_id: str) -> Path | JSONResponse:
    if not is_safe_task_dir(task_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id format"})
    task_dir = (UPLOAD_DIR / task_id).resolve()
    upload_root = UPLOAD_DIR.resolve()
    try:
        task_dir.relative_to(upload_root)
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id format"})
    if not task_dir.exists() or not task_dir.is_dir():
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return task_dir


def count_clip_videos(task_dir: Path) -> int:
    clips_dir = task_dir / "clips"
    if not clips_dir.is_dir():
        return 0
    return sum(1 for f in clips_dir.iterdir() if f.name.endswith(".mp4"))


def collect_artifact_status(task_dir: Path) -> dict[str, bool]:
    return {
        "meta": (task_dir / "meta.json").exists(),
        "settings": (task_dir / "settings.json").exists(),
        "candidates": (task_dir / "candidates.json").exists(),
        "scenes": (task_dir / "scenes" / "scenes.json").exists(),
        "person_presence": (task_dir / "scenes" / "person_presence.json").exists(),
        "confirmed_segments": (task_dir / "vlm" / "confirmed_segments.json").exists(),
        "transcript": (task_dir / "transcript.json").exists(),
        "text_boundaries": (task_dir / "text_boundaries.json").exists(),
        "fused_candidates": (task_dir / "fused_candidates.json").exists(),
        "enriched_segments": (task_dir / "enriched_segments.json").exists(),
        "clips": (task_dir / "clips").is_dir(),
    }


def load_review_state(task_dir: Path) -> dict[str, Any]:
    review = _read_json(task_dir / "review.json", {})
    return review if isinstance(review, dict) else {}


def write_review_state(task_dir: Path, review: dict[str, Any]) -> None:
    review["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(task_dir / "review.json", review)


def write_clip_job_api(task_dir: Path, segment_id: str, payload: dict[str, Any]) -> None:
    jobs_path = task_dir / "clip_jobs.json"
    jobs = _read_json(jobs_path, {})
    if not isinstance(jobs, dict):
        jobs = {}
    current = jobs.get(segment_id, {})
    if not isinstance(current, dict):
        current = {}
    current.update(payload)
    current["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    jobs[segment_id] = current
    write_json(jobs_path, jobs)


def segment_id(index: int) -> str:
    return f"clip_{index:03d}"


def summary_from_task_dir(task_dir: Path) -> dict[str, Any]:
    candidates = _read_json(task_dir / "candidates.json", [])
    confirmed = _read_json(task_dir / "vlm" / "confirmed_segments.json", [])
    transcript = _read_json(task_dir / "transcript.json", [])
    text_boundaries = _read_json(task_dir / "text_boundaries.json", [])
    fused = _read_json(task_dir / "fused_candidates.json", [])
    enriched = _read_json(task_dir / "enriched_segments.json", [])
    person_presence = _read_json(task_dir / "scenes" / "person_presence.json", [])
    clips_count = count_clip_videos(task_dir)

    enriched_count = len(enriched) if isinstance(enriched, list) else 0
    empty_screen_dropped = max(enriched_count - clips_count, 0)

    return {
        "task_id": task_dir.name,
        "candidates_count": len(candidates) if isinstance(candidates, list) else 0,
        "confirmed_count": len(confirmed) if isinstance(confirmed, list) else 0,
        "transcript_segments_count": len(transcript) if isinstance(transcript, list) else 0,
        "text_boundaries_count": len(text_boundaries) if isinstance(text_boundaries, list) else 0,
        "fused_candidates_count": len(fused) if isinstance(fused, list) else 0,
        "enriched_segments_count": enriched_count,
        "clips_count": clips_count,
        "empty_screen_dropped_estimate": empty_screen_dropped,
        "person_presence_frames": len(person_presence) if isinstance(person_presence, list) else 0,
        "artifact_status": collect_artifact_status(task_dir),
    }


def summary_fingerprint(task_dir: Path) -> tuple[Any, ...]:
    return path_fingerprint([
        task_dir / "candidates.json",
        task_dir / "vlm" / "confirmed_segments.json",
        task_dir / "transcript.json",
        task_dir / "text_boundaries.json",
        task_dir / "fused_candidates.json",
        task_dir / "enriched_segments.json",
        task_dir / "scenes" / "person_presence.json",
        task_dir / "clips",
        task_dir / "settings.json",
        task_dir / "review.json",
        task_dir / "state.json",
    ])


def diagnostics_fingerprint(task_dir: Path) -> tuple[Any, ...]:
    return path_fingerprint([
        task_dir / "state.json",
        task_dir / "meta.json",
        task_dir / "settings.json",
        task_dir / "frames" / "frames.json",
        task_dir / "candidates.json",
        task_dir / "scenes",
        task_dir / "vlm",
        task_dir / "transcript.json",
        task_dir / "text_boundaries.json",
        task_dir / "fused_candidates.json",
        task_dir / "enriched_segments.json",
        task_dir / "review.json",
        task_dir / "clips",
    ])


def review_fingerprint(task_dir: Path) -> tuple[Any, ...]:
    return path_fingerprint([
        task_dir / "enriched_segments.json",
        task_dir / "transcript.json",
        task_dir / "settings.json",
        task_dir / "review.json",
        task_dir / "clips",
    ])


def diagnostic_event_log(task_dir: Path) -> list[dict[str, str]]:
    event_log = []
    for label, path in [
        ("任务状态", task_dir / "state.json"),
        ("任务元数据", task_dir / "meta.json"),
        ("任务设置", task_dir / "settings.json"),
        ("候选边界", task_dir / "candidates.json"),
        ("场景分段", task_dir / "scenes" / "scenes.json"),
        ("人物出现", task_dir / "scenes" / "person_presence.json"),
        ("VLM确认", task_dir / "vlm" / "confirmed_segments.json"),
        ("转写文本", task_dir / "transcript.json"),
        ("文本边界", task_dir / "text_boundaries.json"),
        ("融合候选", task_dir / "fused_candidates.json"),
        ("有效分段", task_dir / "enriched_segments.json"),
        ("复核状态", task_dir / "review.json"),
    ]:
        if path.exists():
            stat = path.stat()
            event_log.append(
                {
                    "time": datetime.datetime.fromtimestamp(
                        stat.st_mtime, tz=datetime.timezone.utc
                    ).isoformat(),
                    "stage": label,
                    "level": "INFO",
                    "message": f"{label} 文件已生成",
                    "file": path.relative_to(task_dir).as_posix(),
                }
            )
    event_log.sort(key=lambda item: item["time"])
    return event_log


def artifact_mtime(task_dir: Path, relative_path: str) -> float | None:
    path = task_dir / relative_path
    if path.is_dir():
        mtimes = [item.stat().st_mtime for item in path.iterdir()]
        return max(mtimes) if mtimes else path.stat().st_mtime
    if path.exists():
        return path.stat().st_mtime
    return None


def pipeline_timing(task_dir: Path, pipeline: list[dict[str, Any]]) -> dict[str, Any]:
    meta_mtime = artifact_mtime(task_dir, "meta.json")
    previous_mtime = meta_mtime
    total_end = meta_mtime

    for item in pipeline:
        artifact = str(item["artifact"]).rstrip("/")
        mtime = artifact_mtime(task_dir, artifact)
        if mtime is not None:
            total_end = max(total_end or mtime, mtime)

        if mtime is not None and previous_mtime is not None and mtime >= previous_mtime:
            item["duration_s"] = round(mtime - previous_mtime, 3)
        else:
            item["duration_s"] = None

        if mtime is not None:
            previous_mtime = mtime

    total_elapsed = None
    if meta_mtime is not None and total_end is not None and total_end >= meta_mtime:
        total_elapsed = round(total_end - meta_mtime, 3)

    return {"pipeline": pipeline, "total_elapsed_s": total_elapsed}


def diagnostics_payload(task_dir: Path) -> dict[str, Any]:
    summary = summary_from_task_dir(task_dir)
    state = _read_json(task_dir / "state.json", {"state": "UPLOADED"})
    artifacts = summary["artifact_status"]

    pipeline = [
        {"stage": "上传", "status": "done" if artifacts["meta"] else "pending", "artifact": "meta.json"},
        {"stage": "抽帧", "status": "done" if (task_dir / "frames" / "frames.json").exists() else "pending", "artifact": "frames/frames.json"},
        {"stage": "换衣检测", "status": "done" if artifacts["candidates"] else "pending", "artifact": "candidates.json"},
        {"stage": "VLM确认", "status": "done" if artifacts["confirmed_segments"] else "skipped", "artifact": "vlm/confirmed_segments.json"},
        {"stage": "ASR转写", "status": "done" if artifacts["transcript"] else "skipped", "artifact": "transcript.json"},
        {"stage": "LLM融合", "status": "done" if artifacts["fused_candidates"] else "skipped", "artifact": "fused_candidates.json"},
        {"stage": "导出", "status": "done" if summary["clips_count"] > 0 else "pending", "artifact": "clips/"},
    ]
    timing = pipeline_timing(task_dir, pipeline)

    funnel = [
        {"label": "原始候选", "count": summary["candidates_count"]},
        {"label": "VLM确认", "count": summary["confirmed_count"]},
        {"label": "文本边界", "count": summary["text_boundaries_count"]},
        {"label": "融合候选", "count": summary["fused_candidates_count"]},
        {"label": "有效分段", "count": summary["enriched_segments_count"]},
        {"label": "导出成功", "count": summary["clips_count"]},
    ]

    warnings: list[dict[str, str]] = []
    raw_settings = _read_json(task_dir / "settings.json", {})
    settings = raw_settings if isinstance(raw_settings, dict) else {}
    if settings.get("subtitle_mode") == "karaoke" and settings.get("asr_provider") == "dashscope":
        warnings.append({
            "level": "warning",
            "message": "DashScope 字幕时间戳可能不适合 karaoke，推荐使用火山 VC。",
        })
    if summary["empty_screen_dropped_estimate"] > 0:
        warnings.append({
            "level": "info",
            "message": f"预计有 {summary['empty_screen_dropped_estimate']} 个分段未生成 clip，可能被空镜/时长/导出过滤。",
        })
    if state.get("state") == "ERROR":
        warnings.append({
            "level": "error",
            "message": state.get("message", "任务执行失败"),
        })

    return {
        "task_id": task_dir.name,
        "state": state,
        "summary": summary,
        "pipeline": timing["pipeline"],
        "total_elapsed_s": timing["total_elapsed_s"],
        "funnel": funnel,
        "warnings": warnings,
        "event_log": diagnostic_event_log(task_dir),
    }


def review_payload(task_dir: Path) -> dict[str, Any]:
    enriched = _read_json(task_dir / "enriched_segments.json", [])
    transcript = _read_json(task_dir / "transcript.json", [])
    raw_settings = _read_json(task_dir / "settings.json", {})
    settings = {k: v for k, v in raw_settings.items() if k not in SENSITIVE_FIELDS} if isinstance(raw_settings, dict) else {}
    review = load_review_state(task_dir)
    segment_reviews = review.get("segments", {})
    if not isinstance(segment_reviews, dict):
        segment_reviews = {}

    segments: list[dict[str, Any]] = []
    if isinstance(enriched, list):
        for idx, segment in enumerate(enriched):
            if not isinstance(segment, dict):
                continue
            current_segment_id = segment_id(idx)
            override = segment_reviews.get(current_segment_id, {})
            if not isinstance(override, dict):
                override = {}
            merged = {**segment, **override}
            merged["segment_id"] = current_segment_id
            merged["review_status"] = override.get("status", "pending")
            segments.append(merged)

    clips: list[dict[str, Any]] = []
    clips_dir = task_dir / "clips"
    if clips_dir.is_dir():
        for meta_file in sorted(clips_dir.glob("clip_*_meta.json")):
            meta = _read_json(meta_file, {})
            if not isinstance(meta, dict):
                continue
            stem = meta_file.stem.replace("_meta", "")
            meta["segment_id"] = stem
            meta["clip_id"] = f"{task_dir.name}/{stem}"
            meta["video_url"] = f"/api/clips/{task_dir.name}/{stem}/download"
            meta["thumbnail_url"] = f"/api/clips/{task_dir.name}/{stem}/thumbnail"
            meta["review_status"] = segment_reviews.get(stem, {}).get("status", "pending") if isinstance(segment_reviews.get(stem), dict) else "pending"
            clips.append(meta)

    return {
        "task_id": task_dir.name,
        "segments": segments,
        "clips": clips,
        "transcript": transcript if isinstance(transcript, list) else [],
        "settings": settings if isinstance(settings, dict) else {},
        "review_status": review,
    }
