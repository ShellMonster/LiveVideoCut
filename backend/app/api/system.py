import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.services.resource_detector import calculate_parallelism

UPLOAD_DIR = Path("uploads")

router = APIRouter()


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


@router.get("/api/system/resources")
async def get_system_resources():
    resources = calculate_parallelism()
    queue = {
        "waiting": 0,
        "active": 0,
        "completed": 0,
        "failed": 0,
    }

    if UPLOAD_DIR.exists():
        for task_dir in UPLOAD_DIR.iterdir():
            if not task_dir.is_dir():
                continue
            state = _read_json(task_dir / "state.json", {})
            raw_state = state.get("state") if isinstance(state, dict) else None
            if raw_state == "UPLOADED":
                queue["waiting"] += 1
            elif raw_state == "COMPLETED":
                queue["completed"] += 1
            elif raw_state == "ERROR":
                queue["failed"] += 1
            elif raw_state:
                queue["active"] += 1

    return {
        "cpu_cores": resources["cpu_cores"],
        "memory_gb": resources["memory_gb"],
        "clip_workers": resources["clip_workers"],
        "frame_workers": resources["frame_workers"],
        "queue": queue,
        "redis": "unknown",
    }
