import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

UPLOAD_DIR = Path("uploads")

_TASK_ID_RE = re.compile(r"^[a-f0-9\-]{36}$", re.IGNORECASE)
_SEGMENT_ID_RE = re.compile(r"^clip_\d{3,}$")

router = APIRouter()


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _commerce_dir(task_id: str, segment_id: str) -> Path:
    return UPLOAD_DIR / task_id / "commerce" / segment_id


def _clip_meta(task_id: str, segment_id: str) -> dict[str, Any] | None:
    meta_path = UPLOAD_DIR / task_id / "clips" / f"{segment_id}_meta.json"
    meta = _read_json(meta_path, None)
    return meta if isinstance(meta, dict) else None


def _default_analysis(product_name: str, confidence: float) -> dict[str, Any]:
    return {
        "status": "not_started",
        "provider": "gemini",
        "confidence": confidence,
        "product_type": product_name if product_name and product_name != "未知商品" else "待识别商品",
        "visible_attributes": {
            "color": "待识别",
            "fit": "待识别",
            "sleeve": "待识别",
            "scene": "待识别",
        },
        "selling_points": [],
        "uncertain_fields": ["材质", "尺码", "品牌"],
        "updated_at": "",
    }


def _default_copywriting() -> dict[str, Any]:
    return {
        "status": "not_started",
        "douyin": {
            "title": "",
            "description": "",
            "hashtags": [],
            "compliance": ["标题建议 30 字内", "避免绝对化用语", "未确认材质不写实锤"],
        },
        "taobao": {
            "title": "",
            "selling_points": [],
            "detail_modules": [],
            "compliance": ["商品标题建议 30 汉字内", "材质/尺码需人工确认", "AI 图需标注示意"],
        },
        "updated_at": "",
    }


def _default_images() -> dict[str, Any]:
    return {
        "status": "not_started",
        "items": [
            {"key": "model_front", "label": "正面穿搭", "status": "not_started", "url": ""},
            {"key": "model_side", "label": "侧面角度", "status": "not_started", "url": ""},
            {"key": "model_back", "label": "背面/细节", "status": "not_started", "url": ""},
            {"key": "detail_page", "label": "淘宝详情页示例", "status": "not_started", "url": ""},
        ],
        "updated_at": "",
    }


@router.get("/api/commerce/clips/{task_id}/{segment_id}")
async def get_clip_commerce_asset(task_id: str, segment_id: str):
    if not _TASK_ID_RE.match(task_id) or not _SEGMENT_ID_RE.match(segment_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id or segment_id format"})

    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        return JSONResponse(status_code=404, content={"detail": "Clip not found"})

    commerce_dir = _commerce_dir(task_id, segment_id)
    product_name = str(meta.get("product_name") or "未知商品")
    confidence = float(meta.get("confidence") or 0)
    analysis = _read_json(commerce_dir / "product_analysis.json", _default_analysis(product_name, confidence))
    copywriting = _read_json(commerce_dir / "copywriting.json", _default_copywriting())
    images = _read_json(commerce_dir / "images.json", _default_images())

    return {
        "clip": {
            "clip_id": f"{task_id}/{segment_id}",
            "task_id": task_id,
            "segment_id": segment_id,
            "product_name": product_name,
            "duration": meta.get("duration", 0),
            "start_time": meta.get("start_time", 0),
            "end_time": meta.get("end_time", 0),
            "confidence": confidence,
            "video_url": f"/api/clips/{task_id}/{segment_id}/download",
            "thumbnail_url": f"/api/clips/{task_id}/{segment_id}/thumbnail",
            "has_video": (UPLOAD_DIR / task_id / "clips" / f"{segment_id}.mp4").exists(),
            "has_thumbnail": (UPLOAD_DIR / task_id / "covers" / f"{segment_id}.jpg").exists(),
        },
        "analysis": analysis,
        "copywriting": copywriting,
        "images": images,
        "state": _read_json(commerce_dir / "state.json", {"status": "not_started", "message": "尚未生成 AI 商品素材"}),
    }
