import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.responses import JSONResponse

from app.services.state_machine import TaskStateMachine

UPLOAD_DIR = Path("uploads")

router = APIRouter()


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
