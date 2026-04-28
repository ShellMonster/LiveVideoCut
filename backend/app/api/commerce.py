import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.services.gemini_vision_client import GeminiVisionClient
from app.services.openai_image_client import OpenAIImageClient

UPLOAD_DIR = Path("uploads")

_TASK_ID_RE = re.compile(r"^[a-f0-9\-]{36}$", re.IGNORECASE)
_SEGMENT_ID_RE = re.compile(r"^clip_\d{3,}$")
_IMAGE_NAME_RE = re.compile(r"^[a-z0-9_]+\.png$")

router = APIRouter()


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _commerce_dir(task_id: str, segment_id: str) -> Path:
    return UPLOAD_DIR / task_id / "commerce" / segment_id


def _clip_meta(task_id: str, segment_id: str) -> dict[str, Any] | None:
    meta_path = UPLOAD_DIR / task_id / "clips" / f"{segment_id}_meta.json"
    meta = _read_json(meta_path, None)
    return meta if isinstance(meta, dict) else None


def _cover_path(task_id: str, segment_id: str) -> Path:
    return UPLOAD_DIR / task_id / "covers" / f"{segment_id}.jpg"


def _task_settings(task_id: str) -> dict[str, Any]:
    task_dir = UPLOAD_DIR / task_id
    settings = _read_json(task_dir / "settings.json", {})
    secrets = _read_json(task_dir / "secrets.json", {})
    payload: dict[str, Any] = {}
    if isinstance(settings, dict):
        payload.update(settings)
    if isinstance(secrets, dict):
        payload.update(secrets)
    return payload


def _get_setting(settings: dict[str, Any], key: str, default: Any) -> Any:
    value = settings.get(key)
    if value in (None, ""):
        return default
    return value


def _validate_ids(task_id: str, segment_id: str) -> JSONResponse | None:
    if not _TASK_ID_RE.match(task_id) or not _SEGMENT_ID_RE.match(segment_id):
        return JSONResponse(status_code=400, content={"detail": "Invalid task_id or segment_id format"})
    return None


def _commerce_image_url(task_id: str, segment_id: str, filename: str) -> str:
    return f"/api/commerce/clips/{task_id}/{segment_id}/images/{filename}"


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


def _build_image_prompts(analysis: dict[str, Any]) -> list[dict[str, str]]:
    product_type = str(analysis.get("product_type") or "服装商品")
    attrs = analysis.get("visible_attributes") if isinstance(analysis.get("visible_attributes"), dict) else {}
    color = str(attrs.get("color") or "参考图颜色")
    fit = str(attrs.get("fit") or "参考图版型")
    selling_points = "、".join(str(item) for item in analysis.get("selling_points", [])[:4]) if isinstance(analysis.get("selling_points"), list) else ""
    base = (
        f"参考片段封面中的{color}{product_type}，保持商品颜色、版型和可见细节一致，"
        f"版型：{fit}。卖点参考：{selling_points or '干净自然、适合电商展示'}。"
        "不要添加品牌 logo，不要生成夸张文字，不要改变商品主体。"
    )
    return [
        {
            "key": "model_front",
            "label": "正面穿搭",
            "prompt": f"{base} 生成一张真人模特正面穿着效果图，浅色棚拍背景，电商商品图质感，全身或半身清晰展示。",
        },
        {
            "key": "model_side",
            "label": "侧面角度",
            "prompt": f"{base} 生成一张真人模特侧面 45 度穿着效果图，突出廓形和垂坠感，浅色棚拍背景。",
        },
        {
            "key": "model_back",
            "label": "背面/细节",
            "prompt": f"{base} 生成一张背面或局部细节展示图，突出领口、袖口、面料纹理等可见细节，电商详情风格。",
        },
        {
            "key": "detail_page",
            "label": "淘宝详情页示例",
            "prompt": f"{base} 生成一张淘宝商品详情页装修示例长图，包含主视觉、卖点区、细节区、穿搭场景区，中文文案只用短标签并标注效果示意。",
        },
    ]


@router.get("/api/commerce/clips/{task_id}/{segment_id}")
async def get_clip_commerce_asset(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

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


@router.post("/api/commerce/clips/{task_id}/{segment_id}/analyze")
def analyze_clip_cover(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        return JSONResponse(status_code=404, content={"detail": "Clip not found"})

    cover = _cover_path(task_id, segment_id)
    if not cover.exists():
        return JSONResponse(status_code=404, content={"detail": "Clip cover not found"})

    settings = _task_settings(task_id)
    api_key = str(_get_setting(settings, "commerce_gemini_api_key", "")).strip()
    if not api_key:
        return JSONResponse(status_code=400, content={"detail": "Gemini API Key is not configured for this task"})

    commerce_dir = _commerce_dir(task_id, segment_id)
    _write_json(commerce_dir / "state.json", {"status": "running", "message": "正在调用 Gemini 识别商品封面"})

    try:
        client = GeminiVisionClient(
            api_key=api_key,
            api_base=str(_get_setting(settings, "commerce_gemini_api_base", "https://generativelanguage.googleapis.com")),
            model=str(_get_setting(settings, "commerce_gemini_model", "gemini-3-flash-preview")),
            timeout=int(_get_setting(settings, "commerce_gemini_timeout_seconds", 150)),
        )
        result = client.analyze_cover(cover, str(meta.get("product_name") or ""))
        payload = {
            "status": "completed",
            "provider": "gemini",
            "confidence": result["confidence"],
            "product_type": result["product_type"],
            "visible_attributes": result["visible_attributes"],
            "selling_points": result["selling_points"],
            "uncertain_fields": result["uncertain_fields"],
            "updated_at": _now_iso(),
        }
        _write_json(commerce_dir / "product_analysis.json", payload)
        _write_json(commerce_dir / "state.json", {"status": "completed", "message": "Gemini 商品识别已完成"})
        return payload
    except Exception as exc:
        _write_json(commerce_dir / "state.json", {"status": "failed", "message": f"Gemini 商品识别失败：{exc}"})
        return JSONResponse(status_code=502, content={"detail": f"Gemini 商品识别失败：{exc}"})


@router.post("/api/commerce/clips/{task_id}/{segment_id}/copywriting")
def generate_clip_copywriting(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        return JSONResponse(status_code=404, content={"detail": "Clip not found"})

    commerce_dir = _commerce_dir(task_id, segment_id)
    analysis = _read_json(commerce_dir / "product_analysis.json", None)
    if not isinstance(analysis, dict) or analysis.get("status") != "completed":
        return JSONResponse(status_code=400, content={"detail": "请先完成 Gemini 商品识别"})

    settings = _task_settings(task_id)
    api_key = str(_get_setting(settings, "commerce_gemini_api_key", "")).strip()
    if not api_key:
        return JSONResponse(status_code=400, content={"detail": "Gemini API Key is not configured for this task"})

    _write_json(commerce_dir / "state.json", {"status": "running", "message": "正在生成抖音和淘宝文案"})
    try:
        client = GeminiVisionClient(
            api_key=api_key,
            api_base=str(_get_setting(settings, "commerce_gemini_api_base", "https://generativelanguage.googleapis.com")),
            model=str(_get_setting(settings, "commerce_gemini_model", "gemini-3-flash-preview")),
            timeout=int(_get_setting(settings, "commerce_gemini_timeout_seconds", 150)),
        )
        result = client.generate_copywriting(analysis, str(meta.get("product_name") or ""))
        payload = {"status": "completed", **result, "updated_at": _now_iso()}
        _write_json(commerce_dir / "copywriting.json", payload)
        _write_json(commerce_dir / "state.json", {"status": "completed", "message": "平台文案已生成"})
        return payload
    except Exception as exc:
        _write_json(commerce_dir / "state.json", {"status": "failed", "message": f"平台文案生成失败：{exc}"})
        return JSONResponse(status_code=502, content={"detail": f"平台文案生成失败：{exc}"})


@router.post("/api/commerce/clips/{task_id}/{segment_id}/images")
def generate_clip_images(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        return JSONResponse(status_code=404, content={"detail": "Clip not found"})

    cover = _cover_path(task_id, segment_id)
    if not cover.exists():
        return JSONResponse(status_code=404, content={"detail": "Clip cover not found"})

    commerce_dir = _commerce_dir(task_id, segment_id)
    analysis = _read_json(commerce_dir / "product_analysis.json", _default_analysis(str(meta.get("product_name") or ""), float(meta.get("confidence") or 0)))
    if not isinstance(analysis, dict):
        analysis = _default_analysis(str(meta.get("product_name") or ""), float(meta.get("confidence") or 0))

    settings = _task_settings(task_id)
    api_key = str(_get_setting(settings, "commerce_image_api_key", "")).strip()
    if not api_key:
        return JSONResponse(status_code=400, content={"detail": "OpenAI Image API Key is not configured for this task"})

    _write_json(commerce_dir / "state.json", {"status": "running", "message": "正在调用 OpenAI Image 生成商品素材图"})
    try:
        client = OpenAIImageClient(
            api_key=api_key,
            api_base=str(_get_setting(settings, "commerce_image_api_base", "https://api.openai.com/v1")),
            model=str(_get_setting(settings, "commerce_image_model", "gpt-image-2")),
            timeout=int(_get_setting(settings, "commerce_image_timeout_seconds", 500)),
        )
        image_dir = commerce_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for image_prompt in _build_image_prompts(analysis):
            filename = f"{image_prompt['key']}.png"
            image_bytes = client.generate_with_reference(
                image_prompt["prompt"],
                cover,
                size=str(_get_setting(settings, "commerce_image_size", "1024x1536")),
                quality=str(_get_setting(settings, "commerce_image_quality", "auto")),
            )
            (image_dir / filename).write_bytes(image_bytes)
            items.append(
                {
                    "key": image_prompt["key"],
                    "label": image_prompt["label"],
                    "status": "completed",
                    "url": _commerce_image_url(task_id, segment_id, filename),
                }
            )

        payload = {"status": "completed", "items": items, "updated_at": _now_iso()}
        _write_json(commerce_dir / "images.json", payload)
        _write_json(commerce_dir / "state.json", {"status": "completed", "message": "AI 商品素材图已生成"})
        return payload
    except Exception as exc:
        _write_json(commerce_dir / "state.json", {"status": "failed", "message": f"AI 商品素材图生成失败：{exc}"})
        return JSONResponse(status_code=502, content={"detail": f"AI 商品素材图生成失败：{exc}"})


@router.get("/api/commerce/clips/{task_id}/{segment_id}/images/{filename}")
def get_commerce_image(task_id: str, segment_id: str, filename: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid
    if not _IMAGE_NAME_RE.match(filename):
        return JSONResponse(status_code=400, content={"detail": "Invalid image filename"})
    image_path = _commerce_dir(task_id, segment_id) / "images" / filename
    if not image_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Image not found"})
    return FileResponse(image_path, media_type="image/png")
