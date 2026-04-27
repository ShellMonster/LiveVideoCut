import io
import json
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

UPLOAD_DIR = Path("uploads")

_TASK_ID_RE = re.compile(r"^[a-f0-9\-]{36}$", re.IGNORECASE)
_CLIP_NAME_RE = re.compile(r"^clip_\d{3,}$")

router = APIRouter()


def _clips_dir(task_id: str) -> Path:
    return UPLOAD_DIR / task_id / "clips"


def _collect_clips(clips_dir: Path) -> list[dict]:
    """Scan clips directory and build metadata list."""
    clips = []
    for meta_file in sorted(clips_dir.glob("clip_*_meta.json")):
        meta = json.loads(meta_file.read_text())
        stem = meta_file.stem.replace("_meta", "")
        clip_id = f"{clips_dir.parent.name}/{stem}"
        video_path = clips_dir / f"{stem}.mp4"
        thumb_path = clips_dir.parent / "covers" / f"{stem}.jpg"

        clips.append(
            {
                "clip_id": clip_id,
                "product_name": meta.get("product_name", "未知商品"),
                "duration": meta.get("duration", 0),
                "start_time": meta.get("start_time", 0),
                "end_time": meta.get("end_time", 0),
                "confidence": meta.get("confidence", 0),
                "video_url": f"/api/clips/{clip_id}/download",
                "thumbnail_url": f"/api/clips/{clip_id}/thumbnail",
                "has_video": video_path.exists(),
                "has_thumbnail": thumb_path.exists(),
            }
        )
    return clips


@router.get("/api/tasks/{task_id}/clips")
async def list_clips(task_id: str):
    if not _TASK_ID_RE.match(task_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id format"})
    clips_dir = _clips_dir(task_id)
    if not clips_dir.exists():
        return JSONResponse(
            status_code=404, content={"detail": "No clips found for task"}
        )

    clips = _collect_clips(clips_dir)
    return {"task_id": task_id, "clips": clips, "total": len(clips)}


@router.get("/api/clips/{task_id}/{clip_name}/download")
async def download_clip(task_id: str, clip_name: str):
    if not _TASK_ID_RE.match(task_id) or not _CLIP_NAME_RE.match(clip_name):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id or clip_name format"})
    video_path = _clips_dir(task_id) / f"{clip_name}.mp4"
    if not video_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Clip not found"})

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{clip_name}.mp4",
    )


@router.get("/api/clips/{task_id}/{clip_name}/thumbnail")
async def get_thumbnail(task_id: str, clip_name: str):
    if not _TASK_ID_RE.match(task_id) or not _CLIP_NAME_RE.match(clip_name):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id or clip_name format"})
    thumb_path = UPLOAD_DIR / task_id / "covers" / f"{clip_name}.jpg"
    if not thumb_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Thumbnail not found"})

    return FileResponse(
        path=str(thumb_path),
        media_type="image/jpeg",
    )


@router.get("/api/clips/batch")
async def batch_download(ids: str = ""):
    """Download multiple clips as a ZIP file.

    Query param `ids` is comma-separated clip_id values like "task1/clip_001,task1/clip_002".
    """
    if not ids:
        return JSONResponse(status_code=400, content={"detail": "No clip ids provided"})

    clip_ids = [cid.strip() for cid in ids.split(",") if cid.strip()]
    if not clip_ids:
        return JSONResponse(status_code=400, content={"detail": "No valid clip ids"})
    if len(clip_ids) > 20:
        return JSONResponse(status_code=400, content={"detail": "Too many clip ids (max 20)"})

    def _generate_zip():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for clip_id in clip_ids:
                parts = clip_id.split("/")
                if len(parts) != 2:
                    continue
                tid, cname = parts
                if not _TASK_ID_RE.match(tid) or not _CLIP_NAME_RE.match(cname):
                    continue
                video_path = _clips_dir(tid) / f"{cname}.mp4"
                if video_path.exists():
                    zf.write(str(video_path), arcname=f"{cname}.mp4")
        buffer.seek(0)
        yield buffer.read()

    return StreamingResponse(
        _generate_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=clips.zip"},
    )
