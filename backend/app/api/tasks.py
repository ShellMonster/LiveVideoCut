import asyncio
import datetime
import io
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.responses import JSONResponse, StreamingResponse

from app.services.state_machine import TaskStateMachine
from app.tasks.pipeline import reprocess_clip, start_pipeline

UPLOAD_DIR = Path("uploads")

router = APIRouter()


class ReviewSegmentPatch(BaseModel):
    product_name: str | None = None
    title: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    status: str | None = None
    cover_strategy: str | None = None
    note: str | None = None


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _task_dir_or_404(task_id: str) -> Path | JSONResponse:
    task_dir = UPLOAD_DIR / task_id
    if not task_dir.exists():
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return task_dir


def _count_clip_videos(task_dir: Path) -> int:
    clips_dir = task_dir / "clips"
    if not clips_dir.is_dir():
        return 0
    return sum(1 for f in clips_dir.iterdir() if f.name.endswith(".mp4"))


def _collect_artifact_status(task_dir: Path) -> dict[str, bool]:
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


def _load_review_state(task_dir: Path) -> dict[str, Any]:
    review = _read_json(task_dir / "review.json", {})
    return review if isinstance(review, dict) else {}


def _write_review_state(task_dir: Path, review: dict[str, Any]) -> None:
    review["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (task_dir / "review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2)
    )


def _write_clip_job_api(task_dir: Path, segment_id: str, payload: dict[str, Any]) -> None:
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
    jobs_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2))


def _segment_id(index: int) -> str:
    return f"clip_{index:03d}"


def _summary_from_task_dir(task_dir: Path) -> dict[str, Any]:
    candidates = _read_json(task_dir / "candidates.json", [])
    confirmed = _read_json(task_dir / "vlm" / "confirmed_segments.json", [])
    transcript = _read_json(task_dir / "transcript.json", [])
    text_boundaries = _read_json(task_dir / "text_boundaries.json", [])
    fused = _read_json(task_dir / "fused_candidates.json", [])
    enriched = _read_json(task_dir / "enriched_segments.json", [])
    person_presence = _read_json(task_dir / "scenes" / "person_presence.json", [])
    clips_count = _count_clip_videos(task_dir)

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
        "artifact_status": _collect_artifact_status(task_dir),
    }


def _diagnostic_event_log(task_dir: Path) -> list[dict[str, str]]:
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


@router.get("/api/tasks")
async def list_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    if not UPLOAD_DIR.exists():
        return {"items": [], "total": 0, "offset": offset, "limit": limit}

    items: list[dict] = []
    for entry in os.scandir(UPLOAD_DIR):
        if not entry.is_dir():
            continue

        state_path = os.path.join(entry.path, "state.json")
        if not os.path.exists(state_path):
            continue

        try:
            state_data = json.loads(Path(state_path).read_text())
        except (json.JSONDecodeError, OSError):
            continue

        task_state = state_data.get("state", "UPLOADED")
        if status and task_state != status:
            continue

        task_id = entry.name

        meta_path = os.path.join(entry.path, "meta.json")
        meta: dict = {}
        if os.path.exists(meta_path):
            try:
                meta = json.loads(Path(meta_path).read_text())
            except (json.JSONDecodeError, OSError):
                pass

        created_at = meta.get("created_at", "")
        original_filename = meta.get("original_filename", "")
        video_duration_s = meta.get("duration")
        settings = _read_json(Path(entry.path) / "settings.json", {})
        asr_provider = settings.get("asr_provider", "") if isinstance(settings, dict) else ""

        clips_dir = os.path.join(entry.path, "clips")
        clip_count = 0
        if os.path.isdir(clips_dir):
            clip_count = sum(
                1 for f in os.scandir(clips_dir) if f.name.endswith(".mp4")
            )

        covers_dir = os.path.join(entry.path, "covers")
        thumbnail_url: str | None = None
        if os.path.isdir(covers_dir):
            for f in os.scandir(covers_dir):
                if f.name.endswith(".jpg"):
                    clip_name = f.name.rsplit(".", 1)[0]
                    thumbnail_url = f"/api/clips/{task_id}/{clip_name}/thumbnail"
                    break

        # display_name: original_filename > first product_name > clip count label
        display_name = original_filename
        if not display_name and os.path.isdir(clips_dir):
            first_product = ""
            for mf in sorted(Path(clips_dir).glob("*_meta.json")):
                try:
                    pm = json.loads(mf.read_text())
                    first_product = pm.get("product_name", "")
                except (json.JSONDecodeError, OSError):
                    pass
                break
            if first_product and first_product != "未命名商品":
                display_name = first_product
        if not display_name:
            display_name = f"{clip_count}个片段的视频" if clip_count > 0 else "视频"

        items.append({
            "task_id": task_id,
            "status": task_state,
            "stage": state_data.get("step"),
            "message": state_data.get("message"),
            "created_at": created_at,
            "original_filename": original_filename,
            "display_name": display_name,
            "video_duration_s": video_duration_s,
            "asr_provider": asr_provider,
            "clip_count": clip_count,
            "thumbnail_url": thumbnail_url,
        })

    def _sort_key(item: dict) -> str:
        ca = item.get("created_at", "")
        if ca:
            return ca
        task_dir = UPLOAD_DIR / item["task_id"]
        return datetime.datetime.fromtimestamp(
            task_dir.stat().st_mtime, tz=datetime.timezone.utc
        ).isoformat()

    items.sort(key=_sort_key, reverse=True)

    total = len(items)
    page = items[offset : offset + limit]

    return {"items": page, "total": total, "offset": offset, "limit": limit}


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    task_dir = UPLOAD_DIR / task_id
    if not task_dir.exists():
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    shutil.rmtree(task_dir)
    return {"detail": "Task deleted", "task_id": task_id}


@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    task_dir = UPLOAD_DIR / task_id
    if not task_dir.exists():
        return JSONResponse(status_code=404, content={"detail": "Task not found"})

    sm = TaskStateMachine(task_dir)
    state = sm.read_state()

    meta_file = task_dir / "meta.json"
    metadata = {}
    if meta_file.exists():
        metadata = json.loads(meta_file.read_text())

    return {"task_id": task_id, **state, "metadata": metadata}


@router.get("/api/tasks/{task_id}/summary")
async def get_task_summary(task_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    return _summary_from_task_dir(task_dir)


@router.get("/api/tasks/{task_id}/diagnostics")
async def get_task_diagnostics(task_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    summary = _summary_from_task_dir(task_dir)
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

    funnel = [
        {"label": "原始候选", "count": summary["candidates_count"]},
        {"label": "VLM确认", "count": summary["confirmed_count"]},
        {"label": "文本边界", "count": summary["text_boundaries_count"]},
        {"label": "融合候选", "count": summary["fused_candidates_count"]},
        {"label": "有效分段", "count": summary["enriched_segments_count"]},
        {"label": "导出成功", "count": summary["clips_count"]},
    ]

    warnings: list[dict[str, str]] = []
    settings = _read_json(task_dir / "settings.json", {})
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
        "task_id": task_id,
        "state": state,
        "summary": summary,
        "pipeline": pipeline,
        "funnel": funnel,
        "warnings": warnings,
        "event_log": _diagnostic_event_log(task_dir),
    }


@router.get("/api/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    return {"task_id": task_id, "events": _diagnostic_event_log(task_dir)}


@router.get("/api/tasks/{task_id}/diagnostics/export")
async def export_task_diagnostics(task_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    diagnostics = await get_task_diagnostics(task_id)
    if isinstance(diagnostics, JSONResponse):
        return diagnostics

    content = json.dumps(diagnostics, ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{task_id}-diagnostics.json"'
        },
    )


@router.get("/api/tasks/{task_id}/artifacts.zip")
async def download_task_artifacts(task_id: str, include_media: bool = Query(False)):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    allowed_names = {
        "meta.json",
        "settings.json",
        "state.json",
        "candidates.json",
        "transcript.json",
        "text_boundaries.json",
        "fused_candidates.json",
        "enriched_segments.json",
        "review.json",
    }
    allowed_suffixes = {"_meta.json", ".ass", ".srt"}
    media_suffixes = {".mp4", ".jpg", ".jpeg", ".png"}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in task_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(task_dir).as_posix()
            if path.name in allowed_names or any(path.name.endswith(s) for s in allowed_suffixes):
                zf.write(path, arcname=relative)
            elif include_media and path.suffix.lower() in media_suffixes:
                zf.write(path, arcname=relative)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{task_id}-artifacts.zip"'},
    )


@router.get("/api/tasks/{task_id}/review")
async def get_task_review(task_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    enriched = _read_json(task_dir / "enriched_segments.json", [])
    transcript = _read_json(task_dir / "transcript.json", [])
    settings = _read_json(task_dir / "settings.json", {})
    review = _load_review_state(task_dir)
    segment_reviews = review.get("segments", {})
    if not isinstance(segment_reviews, dict):
        segment_reviews = {}

    segments: list[dict[str, Any]] = []
    if isinstance(enriched, list):
        for idx, segment in enumerate(enriched):
            if not isinstance(segment, dict):
                continue
            segment_id = _segment_id(idx)
            override = segment_reviews.get(segment_id, {})
            if not isinstance(override, dict):
                override = {}
            merged = {**segment, **override}
            merged["segment_id"] = segment_id
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
            meta["clip_id"] = f"{task_id}/{stem}"
            meta["video_url"] = f"/api/clips/{task_id}/{stem}/download"
            meta["thumbnail_url"] = f"/api/clips/{task_id}/{stem}/thumbnail"
            meta["review_status"] = segment_reviews.get(stem, {}).get("status", "pending") if isinstance(segment_reviews.get(stem), dict) else "pending"
            clips.append(meta)

    return {
        "task_id": task_id,
        "segments": segments,
        "clips": clips,
        "transcript": transcript if isinstance(transcript, list) else [],
        "settings": settings if isinstance(settings, dict) else {},
        "review_status": review,
    }


@router.patch("/api/tasks/{task_id}/review/segments/{segment_id}")
async def patch_review_segment(task_id: str, segment_id: str, patch: ReviewSegmentPatch):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    if not segment_id.startswith("clip_"):
        return JSONResponse(status_code=400, content={"detail": "Invalid segment id"})

    review = _load_review_state(task_dir)
    segments = review.setdefault("segments", {})
    if not isinstance(segments, dict):
        segments = {}
        review["segments"] = segments

    current = segments.get(segment_id, {})
    if not isinstance(current, dict):
        current = {}

    updates = patch.model_dump(exclude_unset=True, exclude_none=True)
    if "status" in updates and updates["status"] not in {
        "pending",
        "approved",
        "skipped",
        "needs_adjustment",
    }:
        return JSONResponse(status_code=422, content={"detail": "Invalid review status"})

    current.update(updates)
    current["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    segments[segment_id] = current
    _write_review_state(task_dir, review)
    return {"task_id": task_id, "segment_id": segment_id, "review": current}


@router.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    original = task_dir / "original.mp4"
    if not original.exists():
        return JSONResponse(status_code=409, content={"detail": "original.mp4 not found"})

    (task_dir / "state.json").write_text(
        json.dumps(
            {"state": "UPLOADED", "message": "Retry requested", "step": "uploaded"},
            ensure_ascii=False,
            indent=2,
        )
    )
    start_pipeline.delay(task_id, str(original))
    return {"task_id": task_id, "status": "queued"}


@router.post("/api/tasks/{task_id}/clips/{segment_id}/reprocess")
async def reprocess_task_clip(task_id: str, segment_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    enriched = _read_json(task_dir / "enriched_segments.json", [])
    if not isinstance(enriched, list):
        return JSONResponse(status_code=409, content={"detail": "No enriched segments found"})

    if not segment_id.startswith("clip_"):
        return JSONResponse(status_code=400, content={"detail": "Invalid segment id"})
    try:
        idx = int(segment_id.replace("clip_", ""))
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid segment id"})
    if idx < 0 or idx >= len(enriched):
        return JSONResponse(status_code=404, content={"detail": "Segment not found"})

    _write_clip_job_api(
        task_dir,
        segment_id,
        {
            "status": "queued",
            "queued_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": "",
        },
    )
    result = reprocess_clip.delay(task_id, str(task_dir), segment_id)
    _write_clip_job_api(task_dir, segment_id, {"celery_id": result.id})
    return {"task_id": task_id, "segment_id": segment_id, "status": "queued", "celery_id": result.id}


@router.get("/api/tasks/{task_id}/clips/{segment_id}/reprocess")
async def get_reprocess_task_clip(task_id: str, segment_id: str):
    task_dir = _task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    jobs = _read_json(task_dir / "clip_jobs.json", {})
    job = jobs.get(segment_id, {}) if isinstance(jobs, dict) else {}
    return {"task_id": task_id, "segment_id": segment_id, "job": job if isinstance(job, dict) else {}}


@router.websocket("/ws/tasks/{task_id}")
async def ws_task_progress(websocket: WebSocket, task_id: str):
    task_dir = UPLOAD_DIR / task_id
    if not task_dir.exists():
        await websocket.close(code=4040, reason="Task not found")
        return

    await websocket.accept()

    sm = TaskStateMachine(task_dir)
    last_state = None

    try:
        while True:
            current = sm.read_state()
            state_key = current.get("state", "UPLOADED")

            if state_key != last_state:
                await websocket.send_json(current)
                last_state = state_key

            if state_key in ("COMPLETED", "ERROR"):
                break

            await asyncio.sleep(0.5)

            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except (asyncio.TimeoutError, WebSocketDisconnect):
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
