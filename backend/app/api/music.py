import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from mutagen.mp3 import HeaderNotFoundError, MP3
from pydantic import BaseModel

from app.services.bgm_selector import DEFAULT_SELECTOR
from app.services.memory_cache import FingerprintMemoryCache, path_fingerprint

logger = logging.getLogger(__name__)

router = APIRouter()
_music_library_cache = FingerprintMemoryCache(max_size=4)

USER_BGM_DIR = Path("/app/uploads/bgm_library")
USER_LIBRARY_PATH = USER_BGM_DIR / "library.json"
LOCK_PATH = USER_BGM_DIR / "library.json.lock"

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB


class TrackPatch(BaseModel):
    title: str | None = None
    mood: list[str] | None = None
    categories: list[str] | None = None
    tempo: str | None = None
    energy: str | None = None
    genre: str | None = None


@contextmanager
def _library_lock():
    USER_BGM_DIR.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _read_user_library() -> list[dict]:
    if not USER_LIBRARY_PATH.exists():
        return []
    raw = USER_LIBRARY_PATH.read_text()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.exception("Corrupted user BGM library: %s", USER_LIBRARY_PATH)
        raise RuntimeError("User BGM library is corrupted, aborting write to prevent data loss")


def _write_user_library(tracks: list[dict]) -> None:
    USER_BGM_DIR.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=USER_BGM_DIR, suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(tracks, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(USER_LIBRARY_PATH))
        _music_library_cache.clear()
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _merged_library() -> list[dict]:
    try:
        user_tracks = _read_user_library()
    except RuntimeError:
        user_tracks = []
    for t in user_tracks:
        t["source"] = "user"
    built_tracks = DEFAULT_SELECTOR.library_info
    built_ids = {t["id"] for t in user_tracks}
    for t in built_tracks:
        if t["id"] not in built_ids:
            t["source"] = "built-in"
    return user_tracks + [t for t in built_tracks if t["id"] not in built_ids]


@router.get("/api/music/library")
def get_music_library():
    fingerprint = path_fingerprint([USER_LIBRARY_PATH])
    cached = _music_library_cache.get("library", fingerprint)
    if cached is not None:
        return cached
    library = _merged_library()
    _music_library_cache.set("library", fingerprint, library)
    return library


@router.post("/api/music/upload")
def upload_music(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="Only MP3 files are accepted")

    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20MB limit")

    hex_id = uuid4().hex[:8]
    track_id = f"user_{hex_id}"
    filename = f"{track_id}.mp3"

    USER_BGM_DIR.mkdir(parents=True, exist_ok=True)
    dest = USER_BGM_DIR / filename

    tmp_fd, tmp_path = tempfile.mkstemp(dir=USER_BGM_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(content)
        try:
            mp3 = MP3(tmp_path)
        except HeaderNotFoundError:
            Path(tmp_path).unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Invalid MP3 file")
        duration = mp3.info.length
    except HTTPException:
        raise
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Failed to read MP3 metadata")

    os.replace(tmp_path, str(dest))

    title = Path(file.filename).stem if file.filename else track_id
    entry = {
        "id": track_id,
        "file": filename,
        "title": title,
        "mood": ["happy"],
        "genre": "",
        "tempo": "medium",
        "energy": "medium",
        "categories": ["default"],
        "duration_s": round(duration, 2),
        "source": "user",
    }

    with _library_lock():
        tracks = _read_user_library()
        tracks.append(entry)
        _write_user_library(tracks)

    return entry


@router.delete("/api/music/{track_id}")
def delete_music(track_id: str):
    with _library_lock():
        tracks = _read_user_library()
        target_idx = None
        for i, t in enumerate(tracks):
            if t["id"] == track_id:
                target_idx = i
                break

        if target_idx is None:
            raise HTTPException(status_code=404, detail="Track not found or is built-in")

        removed = tracks.pop(target_idx)
        _write_user_library(tracks)

    mp3_path = USER_BGM_DIR / removed["file"]
    if mp3_path.exists():
        mp3_path.unlink()

    return {"detail": "deleted", "id": track_id}


@router.patch("/api/music/{track_id}")
def patch_music(track_id: str, patch: TrackPatch):
    with _library_lock():
        tracks = _read_user_library()
        target = None
        for t in tracks:
            if t["id"] == track_id:
                target = t
                break

        if target is None:
            raise HTTPException(status_code=404, detail="Track not found or is built-in")

        for field in ("title", "mood", "categories", "tempo", "energy", "genre"):
            val = getattr(patch, field)
            if val is not None:
                target[field] = val

        _write_user_library(tracks)
        target["source"] = "user"
    return target


@router.get("/api/music/{track_id}/audio")
def get_music_audio(track_id: str):
    try:
        user_tracks = _read_user_library()
    except RuntimeError:
        user_tracks = []
    for t in user_tracks:
        if t["id"] == track_id:
            path = USER_BGM_DIR / t["file"]
            if path.exists():
                return FileResponse(path, media_type="audio/mpeg")

    path = DEFAULT_SELECTOR.get_track_path(track_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Track not found: {track_id}")
    return FileResponse(path, media_type="audio/mpeg")
