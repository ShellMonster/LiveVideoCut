import asyncio
import datetime
import io
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator, model_validator
from starlette.responses import JSONResponse, StreamingResponse

from app.api.task_helpers import (
    deletable_task_dir_or_404,
    diagnostic_event_log,
    diagnostics_fingerprint,
    diagnostics_payload,
    load_review_state,
    review_fingerprint,
    review_payload,
    summary_fingerprint,
    summary_from_task_dir,
    task_dir_or_404,
    write_clip_job_api,
    write_review_state,
)
from app.api.validation import is_segment_id, is_task_id
from app.config import UPLOAD_DIR
from app.services.memory_cache import FingerprintMemoryCache
from app.services.subtitle_overrides import (
    MAX_SUBTITLE_OVERRIDE_LINES,
    MAX_SUBTITLE_OVERRIDE_TEXT_CHARS,
    MAX_SUBTITLE_OVERRIDE_TOTAL_TEXT_CHARS,
    has_ass_control_chars,
    normalize_subtitle_override_text,
)
from app.services.state_machine import TaskStateMachine
from app.services.list_index import delete_task_index, query_tasks, refresh_task_index, status_group
from app.tasks.pipeline import reprocess_clip, start_pipeline
from app.utils.json_io import read_json_silent as _read_json, write_json

logger = logging.getLogger(__name__)

router = APIRouter()
_task_summary_cache = FingerprintMemoryCache(max_size=128)
_task_diagnostics_cache = FingerprintMemoryCache(max_size=64)
_task_events_cache = FingerprintMemoryCache(max_size=128)
_task_review_cache = FingerprintMemoryCache(max_size=64)


def _route_task_dir_or_404(task_id: str):
    return task_dir_or_404(task_id, upload_dir=UPLOAD_DIR)


def _route_deletable_task_dir_or_404(task_id: str):
    return deletable_task_dir_or_404(task_id, upload_dir=UPLOAD_DIR)


class SubtitleOverridePatch(BaseModel):
    start_time: float
    end_time: float
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = normalize_subtitle_override_text(value)
        if not normalized:
            raise ValueError("Subtitle text cannot be empty")
        if len(normalized) > MAX_SUBTITLE_OVERRIDE_TEXT_CHARS:
            raise ValueError(
                f"Subtitle text cannot exceed {MAX_SUBTITLE_OVERRIDE_TEXT_CHARS} characters"
            )
        if has_ass_control_chars(normalized):
            raise ValueError("Subtitle text cannot contain ASS control characters")
        return normalized

    @model_validator(mode="after")
    def validate_time_range(self) -> "SubtitleOverridePatch":
        if self.end_time <= self.start_time:
            raise ValueError("Subtitle end_time must be greater than start_time")
        return self


class ReviewSegmentPatch(BaseModel):
    product_name: str | None = None
    title: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    status: str | None = None
    cover_strategy: str | None = None
    note: str | None = None
    subtitle_overrides: list[SubtitleOverridePatch] | None = None

    @field_validator("subtitle_overrides")
    @classmethod
    def validate_subtitle_overrides(
        cls,
        value: list[SubtitleOverridePatch] | None,
    ) -> list[SubtitleOverridePatch] | None:
        if value is None:
            return value
        if len(value) > MAX_SUBTITLE_OVERRIDE_LINES:
            raise ValueError(
                f"Subtitle overrides cannot exceed {MAX_SUBTITLE_OVERRIDE_LINES} lines"
            )
        total_chars = sum(len(item.text) for item in value)
        if total_chars > MAX_SUBTITLE_OVERRIDE_TOTAL_TEXT_CHARS:
            raise ValueError(
                f"Subtitle overrides cannot exceed {MAX_SUBTITLE_OVERRIDE_TOTAL_TEXT_CHARS} total characters"
            )
        return value


@router.get("/api/tasks")
async def list_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
):
    if not UPLOAD_DIR.exists():
        return {
            "items": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
            "summary": {
                "total": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "uploaded": 0,
                "clip_count": 0,
            },
        }

    try:
        return query_tasks(
            UPLOAD_DIR,
            offset=offset,
            limit=limit,
            status=status,
            q=q,
        )
    except Exception:
        logger.warning("SQLite task list index failed, falling back to file scan", exc_info=True)

    items: list[dict] = []
    summary = {
        "total": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "uploaded": 0,
        "clip_count": 0,
    }
    for entry in os.scandir(UPLOAD_DIR):
        if not entry.is_dir():
            continue

        state_path = os.path.join(entry.path, "state.json")
        if not os.path.exists(state_path):
            continue

        try:
            state_data = _read_json(Path(state_path), None)
            if not isinstance(state_data, dict):
                continue
        except OSError:
            continue

        task_state = state_data.get("state", "UPLOADED")

        task_id = entry.name

        meta_path = os.path.join(entry.path, "meta.json")
        meta: dict = {}
        if os.path.exists(meta_path):
            try:
                loaded_meta = _read_json(Path(meta_path), {})
                if isinstance(loaded_meta, dict):
                    meta = loaded_meta
            except OSError:
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
                    pm = _read_json(mf, {})
                    first_product = pm.get("product_name", "") if isinstance(pm, dict) else ""
                except OSError:
                    pass
                break
            if first_product and first_product != "未命名商品":
                display_name = first_product
        if not display_name:
            display_name = f"{clip_count}个片段的视频" if clip_count > 0 else "视频"

        item = {
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
        }

        summary["total"] += 1
        summary[status_group(task_state)] += 1
        summary["clip_count"] += clip_count

        if status:
            if status == "processing":
                if status_group(task_state) != "processing":
                    continue
            elif task_state != status:
                continue

        normalized_q = (q or "").strip().lower()
        if normalized_q and not any(
            normalized_q in str(value or "").lower()
            for value in [
                item["task_id"],
                item["original_filename"],
                item["display_name"],
            ]
        ):
            continue

        items.append(item)

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

    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "summary": summary,
    }


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    task_dir = _route_deletable_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    shutil.rmtree(task_dir)
    delete_task_index(UPLOAD_DIR, task_id)
    return {"detail": "Task deleted", "task_id": task_id}


@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    if not is_task_id(task_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id format"})
    task_dir = UPLOAD_DIR / task_id
    if not task_dir.exists():
        return JSONResponse(status_code=404, content={"detail": "Task not found"})

    sm = TaskStateMachine(task_dir)
    state = sm.read_state()

    meta_file = task_dir / "meta.json"
    metadata = {}
    if meta_file.exists():
        metadata = _read_json(meta_file, {})

    return {"task_id": task_id, **state, "metadata": metadata}


@router.get("/api/tasks/{task_id}/summary")
async def get_task_summary(task_id: str):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    fingerprint = summary_fingerprint(task_dir)
    cache_key = f"summary:{task_dir.resolve()}"
    cached = _task_summary_cache.get(cache_key, fingerprint)
    if cached is not None:
        return cached
    payload = summary_from_task_dir(task_dir)
    _task_summary_cache.set(cache_key, fingerprint, payload)
    return payload


@router.get("/api/tasks/{task_id}/diagnostics")
async def get_task_diagnostics(task_id: str):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    fingerprint = diagnostics_fingerprint(task_dir)
    cache_key = f"diagnostics:{task_dir.resolve()}"
    cached = _task_diagnostics_cache.get(cache_key, fingerprint)
    if cached is not None:
        return cached
    payload = diagnostics_payload(task_dir)
    _task_diagnostics_cache.set(cache_key, fingerprint, payload)
    return payload


@router.get("/api/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    fingerprint = diagnostics_fingerprint(task_dir)
    cache_key = f"events:{task_dir.resolve()}"
    cached = _task_events_cache.get(cache_key, fingerprint)
    if cached is not None:
        return cached
    payload = {"task_id": task_id, "events": diagnostic_event_log(task_dir)}
    _task_events_cache.set(cache_key, fingerprint, payload)
    return payload


@router.get("/api/tasks/{task_id}/diagnostics/export")
async def export_task_diagnostics(task_id: str):
    task_dir = _route_task_dir_or_404(task_id)
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
    task_dir = _route_task_dir_or_404(task_id)
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
    excluded_names = {"secrets.json"}
    allowed_suffixes = {"_meta.json", ".ass", ".srt"}
    media_suffixes = {".mp4", ".jpg", ".jpeg", ".png"}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in task_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(task_dir).as_posix()
            if path.name in excluded_names:
                continue
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
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    fingerprint = review_fingerprint(task_dir)
    cache_key = f"review:{task_dir.resolve()}"
    cached = _task_review_cache.get(cache_key, fingerprint)
    if cached is not None:
        return cached
    payload = review_payload(task_dir)
    _task_review_cache.set(cache_key, fingerprint, payload)
    return payload


@router.patch("/api/tasks/{task_id}/review/segments/{segment_id}")
async def patch_review_segment(task_id: str, segment_id: str, patch: ReviewSegmentPatch):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    if not is_segment_id(segment_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid segment id"})

    review = load_review_state(task_dir)
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
    write_review_state(task_dir, review)
    refresh_task_index(UPLOAD_DIR, task_id)
    return {"task_id": task_id, "segment_id": segment_id, "review": current}


@router.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    original = task_dir / "original.mp4"
    if not original.exists():
        return JSONResponse(status_code=409, content={"detail": "original.mp4 not found"})

    write_json(
        task_dir / "state.json",
        {"state": "UPLOADED", "message": "Retry requested", "step": "uploaded"},
    )
    refresh_task_index(UPLOAD_DIR, task_id)
    start_pipeline.delay(task_id, str(original))
    return {"task_id": task_id, "status": "queued"}


@router.post("/api/tasks/{task_id}/clips/{segment_id}/reprocess")
async def reprocess_task_clip(task_id: str, segment_id: str):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir

    enriched = _read_json(task_dir / "enriched_segments.json", [])
    if not isinstance(enriched, list):
        return JSONResponse(status_code=409, content={"detail": "No enriched segments found"})

    if not is_segment_id(segment_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid segment id"})
    try:
        idx = int(segment_id.replace("clip_", ""))
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid segment id"})
    if idx < 0 or idx >= len(enriched):
        return JSONResponse(status_code=404, content={"detail": "Segment not found"})

    write_clip_job_api(
        task_dir,
        segment_id,
        {
            "status": "queued",
            "queued_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": "",
        },
    )
    result = reprocess_clip.delay(task_id, str(task_dir), segment_id)
    write_clip_job_api(task_dir, segment_id, {"celery_id": result.id})
    refresh_task_index(UPLOAD_DIR, task_id)
    return {"task_id": task_id, "segment_id": segment_id, "status": "queued", "celery_id": result.id}


@router.get("/api/tasks/{task_id}/clips/{segment_id}/reprocess")
async def get_reprocess_task_clip(task_id: str, segment_id: str):
    task_dir = _route_task_dir_or_404(task_id)
    if isinstance(task_dir, JSONResponse):
        return task_dir
    jobs = _read_json(task_dir / "clip_jobs.json", {})
    job = jobs.get(segment_id, {}) if isinstance(jobs, dict) else {}
    return {"task_id": task_id, "segment_id": segment_id, "job": job if isinstance(job, dict) else {}}


@router.websocket("/ws/tasks/{task_id}")
async def ws_task_progress(websocket: WebSocket, task_id: str):
    if not is_task_id(task_id):
        await websocket.close(code=4000, reason="Invalid task_id format")
        return
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
