import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

UPLOAD_DIR = Path("uploads")

router = APIRouter()


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _review_status(task_dir: Path, segment_id: str) -> str:
    review = _read_json(task_dir / "review.json", {})
    if not isinstance(review, dict):
        return "pending"
    segments = review.get("segments", {})
    if not isinstance(segments, dict):
        return "pending"
    entry = segments.get(segment_id, {})
    if not isinstance(entry, dict):
        return "pending"
    return str(entry.get("status", "pending"))


def _task_created_at(task_dir: Path) -> str:
    meta = _read_json(task_dir / "meta.json", {})
    if isinstance(meta, dict) and meta.get("created_at"):
        return str(meta["created_at"])
    return ""


@router.get("/api/assets/clips")
async def list_clip_assets(
    status: str | None = Query(None),
    project_id: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
    duration: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    if not UPLOAD_DIR.exists():
        return {
            "items": [],
            "summary": {
                "total": 0,
                "pending": 0,
                "approved": 0,
                "skipped": 0,
                "needs_adjustment": 0,
                "downloadable": 0,
                "total_size": 0,
            },
            "total": 0,
            "offset": offset,
            "limit": limit,
        }

    items: list[dict[str, Any]] = []
    for task_dir in sorted(UPLOAD_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        if project_id and task_dir.name != project_id:
            continue

        clips_dir = task_dir / "clips"
        if not clips_dir.is_dir():
            continue

        created_at = _task_created_at(task_dir)
        for meta_file in sorted(clips_dir.glob("clip_*_meta.json")):
            segment_id = meta_file.stem.replace("_meta", "")
            video_path = clips_dir / f"{segment_id}.mp4"
            cover_path = task_dir / "covers" / f"{segment_id}.jpg"
            meta = _read_json(meta_file, {})
            if not isinstance(meta, dict):
                continue

            review_status = _review_status(task_dir, segment_id)
            if status and review_status != status:
                continue

            clip_duration = meta.get("duration", 0)
            if duration == "short" and clip_duration >= 30:
                continue
            if duration == "medium" and not (30 <= clip_duration <= 90):
                continue
            if duration == "long" and clip_duration <= 90:
                continue

            file_size = video_path.stat().st_size if video_path.exists() else 0
            item = {
                "clip_id": f"{task_dir.name}/{segment_id}",
                "task_id": task_dir.name,
                "segment_id": segment_id,
                "product_name": meta.get("product_name", "未知商品"),
                "duration": clip_duration,
                "start_time": meta.get("start_time", 0),
                "end_time": meta.get("end_time", 0),
                "confidence": meta.get("confidence", 0),
                "review_status": review_status,
                "file_size": file_size,
                "created_at": created_at,
                "video_url": f"/api/clips/{task_dir.name}/{segment_id}/download",
                "thumbnail_url": f"/api/clips/{task_dir.name}/{segment_id}/thumbnail",
                "has_video": video_path.exists(),
                "has_thumbnail": cover_path.exists(),
            }

            normalized_q = (q or "").strip().lower()
            if normalized_q and not any(
                normalized_q in str(value or "").lower()
                for value in [
                    item["product_name"],
                    item["task_id"],
                    item["clip_id"],
                    item["segment_id"],
                ]
            ):
                continue

            items.append(item)

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)

    summary = {
        "total": len(items),
        "pending": sum(1 for item in items if item["review_status"] == "pending"),
        "approved": sum(1 for item in items if item["review_status"] == "approved"),
        "skipped": sum(1 for item in items if item["review_status"] == "skipped"),
        "needs_adjustment": sum(
            1 for item in items if item["review_status"] == "needs_adjustment"
        ),
        "downloadable": sum(1 for item in items if item["has_video"]),
        "total_size": sum(int(item["file_size"]) for item in items),
    }

    page = items[offset : offset + limit]
    return {
        "items": page,
        "summary": summary,
        "total": len(items),
        "offset": offset,
        "limit": limit,
    }
