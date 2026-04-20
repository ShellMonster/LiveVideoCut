import asyncio
import datetime
import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.responses import JSONResponse

from app.services.state_machine import TaskStateMachine

UPLOAD_DIR = Path("uploads")

router = APIRouter()


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
