import os
from fastapi import APIRouter
from redis import Redis, RedisError

from app.config import UPLOAD_DIR
from app.services.memory_cache import TTLMemoryCache
from app.services.resource_detector import calculate_parallelism
from app.utils.json_io import read_json_silent as _read_json

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RESOURCE_CACHE_TTL_SECONDS = 3.0

router = APIRouter()
_resources_cache = TTLMemoryCache(max_size=8)


def _redis_status() -> str:
    client: Redis | None = None
    try:
        client = Redis.from_url(REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
        return "ok" if client.ping() else "error"
    except RedisError as exc:
        return f"error: {exc.__class__.__name__}"
    except OSError as exc:
        return f"error: {exc.__class__.__name__}"
    finally:
        if client is not None:
            client.close()


@router.get("/api/system/resources")
async def get_system_resources():
    cache_key = f"{UPLOAD_DIR.resolve()}:{REDIS_URL}"
    cached = _resources_cache.get(cache_key)
    if cached is not None:
        return cached

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

    payload = {
        "cpu_cores": resources["cpu_cores"],
        "memory_gb": resources["memory_gb"],
        "clip_workers": resources["clip_workers"],
        "frame_workers": resources["frame_workers"],
        "queue": queue,
        "redis": _redis_status(),
    }
    _resources_cache.set(cache_key, payload, RESOURCE_CACHE_TTL_SECONDS)
    return payload
