from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi import HTTPException

from app.services.bgm_selector import DEFAULT_SELECTOR

router = APIRouter()


@router.get("/api/music/library")
async def get_music_library():
    return DEFAULT_SELECTOR.library_info


@router.get("/api/music/{track_id}/audio")
async def get_music_audio(track_id: str):
    path = DEFAULT_SELECTOR.get_track_path(track_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Track not found: {track_id}")
    return FileResponse(path, media_type="audio/mpeg")
