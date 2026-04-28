import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, JSONResponse

from app.services.gemini_vision_client import GeminiVisionClient
from app.services.openai_image_client import OpenAIImageClient

UPLOAD_DIR = Path("uploads")

_TASK_ID_RE = re.compile(r"^[a-f0-9\-]{36}$", re.IGNORECASE)
_SEGMENT_ID_RE = re.compile(r"^clip_\d{3,}$")
_IMAGE_NAME_RE = re.compile(r"^[a-z0-9_]+\.png$")
_IMAGE_KEYS = {"model_front", "model_side", "model_back", "detail_page"}

router = APIRouter()


class CommerceBatchRequest(BaseModel):
    clip_ids: list[str] = Field(default_factory=list, max_length=50)
    actions: list[str] = Field(default_factory=lambda: ["analyze", "copywriting", "images"])


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
        return JSONResponse(status_code=400, content={"detail": "任务或片段 ID 格式无效"})
    return None


def _commerce_image_url(task_id: str, segment_id: str, filename: str) -> str:
    return f"/api/commerce/clips/{task_id}/{segment_id}/images/{filename}"


def _commerce_job_path(task_id: str, segment_id: str) -> Path:
    return _commerce_dir(task_id, segment_id) / "job.json"


def _write_commerce_job(task_id: str, segment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _commerce_job_path(task_id, segment_id)
    current = _read_json(path, {})
    if not isinstance(current, dict):
        current = {}
    current.update(payload)
    current["updated_at"] = _now_iso()
    _write_json(path, current)
    _write_json(_commerce_dir(task_id, segment_id) / "state.json", {
        "status": current.get("status", "not_started"),
        "message": current.get("message", "尚未生成 AI 商品素材"),
    })
    return current


def _read_commerce_job(task_id: str, segment_id: str) -> dict[str, Any]:
    job = _read_json(_commerce_job_path(task_id, segment_id), {})
    return job if isinstance(job, dict) else {}


def _derive_commerce_status(analysis: dict[str, Any], copywriting: dict[str, Any], images: dict[str, Any], job: dict[str, Any]) -> str:
    if job.get("status") in {"queued", "running", "failed"}:
        return str(job["status"])
    statuses = [analysis.get("status"), copywriting.get("status"), images.get("status")]
    if all(status == "completed" for status in statuses):
        return "completed"
    if any(status == "completed" for status in statuses):
        return "partial"
    return "not_started"


def commerce_status_for_clip(task_id: str, segment_id: str) -> dict[str, Any]:
    meta = _clip_meta(task_id, segment_id) or {}
    product_name = str(meta.get("product_name") or "未知商品")
    confidence = float(meta.get("confidence") or 0)
    commerce_dir = _commerce_dir(task_id, segment_id)
    analysis = _read_json(commerce_dir / "product_analysis.json", _default_analysis(product_name, confidence))
    copywriting = _read_json(commerce_dir / "copywriting.json", _default_copywriting())
    images = _read_json(commerce_dir / "images.json", _default_images())
    job = _read_commerce_job(task_id, segment_id)
    return {
        "status": _derive_commerce_status(analysis, copywriting, images, job),
        "analysis_status": analysis.get("status", "not_started") if isinstance(analysis, dict) else "not_started",
        "copywriting_status": copywriting.get("status", "not_started") if isinstance(copywriting, dict) else "not_started",
        "images_status": images.get("status", "not_started") if isinstance(images, dict) else "not_started",
        "job": job,
    }


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


def _merge_image_items(existing: Any, default_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(existing, dict) or not isinstance(existing.get("items"), list):
        return default_items
    by_key = {str(item.get("key")): item for item in default_items if isinstance(item, dict)}
    for item in existing["items"]:
        if isinstance(item, dict) and item.get("key") in by_key:
            by_key[str(item["key"])] = item
    return [by_key[item["key"]] for item in default_items]


def run_commerce_actions(task_id: str, segment_id: str, actions: list[str], image_keys: list[str] | None = None) -> dict[str, Any]:
    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        raise FileNotFoundError("未找到该片段")

    cover = _cover_path(task_id, segment_id)
    commerce_dir = _commerce_dir(task_id, segment_id)
    settings = _task_settings(task_id)
    normalized_actions = [action for action in actions if action in {"analyze", "copywriting", "images"}]
    normalized_image_keys = [key for key in (image_keys or []) if key in _IMAGE_KEYS]
    if not normalized_actions:
        raise ValueError("没有可执行的商品素材生成动作")

    _write_commerce_job(
        task_id,
        segment_id,
        {
            "status": "running",
            "actions": normalized_actions,
            "image_keys": normalized_image_keys,
            "message": "正在生成 AI 商品素材",
            "started_at": _now_iso(),
            "error": "",
        },
    )

    if "analyze" in normalized_actions:
        if not cover.exists():
            raise FileNotFoundError("片段封面不存在")
        api_key = str(_get_setting(settings, "commerce_gemini_api_key", "")).strip()
        if not api_key:
            raise ValueError("Gemini API Key 未配置，请先在系统设置中填写")
        _write_commerce_job(task_id, segment_id, {"message": "正在调用 Gemini 识别商品封面", "current_action": "analyze"})
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

    if "copywriting" in normalized_actions:
        analysis = _read_json(commerce_dir / "product_analysis.json", None)
        if not isinstance(analysis, dict) or analysis.get("status") != "completed":
            raise ValueError("请先完成 Gemini 商品识别")
        api_key = str(_get_setting(settings, "commerce_gemini_api_key", "")).strip()
        if not api_key:
            raise ValueError("Gemini API Key 未配置，请先在系统设置中填写")
        _write_commerce_job(task_id, segment_id, {"message": "正在生成抖音和淘宝文案", "current_action": "copywriting"})
        client = GeminiVisionClient(
            api_key=api_key,
            api_base=str(_get_setting(settings, "commerce_gemini_api_base", "https://generativelanguage.googleapis.com")),
            model=str(_get_setting(settings, "commerce_gemini_model", "gemini-3-flash-preview")),
            timeout=int(_get_setting(settings, "commerce_gemini_timeout_seconds", 150)),
        )
        result = client.generate_copywriting(analysis, str(meta.get("product_name") or ""))
        _write_json(commerce_dir / "copywriting.json", {"status": "completed", **result, "updated_at": _now_iso()})

    if "images" in normalized_actions:
        if not cover.exists():
            raise FileNotFoundError("片段封面不存在")
        analysis = _read_json(commerce_dir / "product_analysis.json", _default_analysis(str(meta.get("product_name") or ""), float(meta.get("confidence") or 0)))
        if not isinstance(analysis, dict):
            analysis = _default_analysis(str(meta.get("product_name") or ""), float(meta.get("confidence") or 0))
        api_key = str(_get_setting(settings, "commerce_image_api_key", "")).strip()
        if not api_key:
            raise ValueError("OpenAI Image API Key 未配置，请先在系统设置中填写")
        client = OpenAIImageClient(
            api_key=api_key,
            api_base=str(_get_setting(settings, "commerce_image_api_base", "https://api.openai.com/v1")),
            model=str(_get_setting(settings, "commerce_image_model", "gpt-image-2")),
            timeout=int(_get_setting(settings, "commerce_image_timeout_seconds", 500)),
        )
        image_dir = commerce_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        existing_images = _read_json(commerce_dir / "images.json", _default_images())
        default_items = _default_images()["items"]
        items = _merge_image_items(existing_images, default_items)
        prompts = _build_image_prompts(analysis)
        if normalized_image_keys:
            prompts = [prompt for prompt in prompts if prompt["key"] in normalized_image_keys]
        for image_prompt in prompts:
            _write_commerce_job(task_id, segment_id, {"message": f"正在生成{image_prompt['label']}", "current_action": "images", "current_item": image_prompt["key"]})
            filename = f"{image_prompt['key']}.png"
            image_bytes = client.generate_with_reference(
                image_prompt["prompt"],
                cover,
                size=str(_get_setting(settings, "commerce_image_size", "2K")),
                quality=str(_get_setting(settings, "commerce_image_quality", "auto")),
            )
            (image_dir / filename).write_bytes(image_bytes)
            completed_item = {
                "key": image_prompt["key"],
                "label": image_prompt["label"],
                "status": "completed",
                "url": _commerce_image_url(task_id, segment_id, filename),
            }
            items = [completed_item if item["key"] == completed_item["key"] else item for item in items]
            _write_json(commerce_dir / "images.json", {"status": "running", "items": items, "updated_at": _now_iso()})
        _write_json(commerce_dir / "images.json", {"status": "completed", "items": items, "updated_at": _now_iso()})

    result = commerce_status_for_clip(task_id, segment_id)
    _write_commerce_job(
        task_id,
        segment_id,
        {
            "status": "completed",
            "message": "AI 商品素材生成完成",
            "finished_at": _now_iso(),
            "current_action": "",
            "current_item": "",
            "error": "",
        },
    )
    return result


@router.get("/api/commerce/clips/{task_id}/{segment_id}")
async def get_clip_commerce_asset(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        return JSONResponse(status_code=404, content={"detail": "未找到该片段"})

    commerce_dir = _commerce_dir(task_id, segment_id)
    product_name = str(meta.get("product_name") or "未知商品")
    confidence = float(meta.get("confidence") or 0)
    analysis = _read_json(commerce_dir / "product_analysis.json", _default_analysis(product_name, confidence))
    copywriting = _read_json(commerce_dir / "copywriting.json", _default_copywriting())
    images = _read_json(commerce_dir / "images.json", _default_images())
    job = _read_commerce_job(task_id, segment_id)

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
            "preview_url": f"/api/clips/{task_id}/{segment_id}/preview",
            "thumbnail_url": f"/api/clips/{task_id}/{segment_id}/thumbnail",
            "has_video": (UPLOAD_DIR / task_id / "clips" / f"{segment_id}.mp4").exists(),
            "has_thumbnail": (UPLOAD_DIR / task_id / "covers" / f"{segment_id}.jpg").exists(),
        },
        "analysis": analysis,
        "copywriting": copywriting,
        "images": images,
        "state": _read_json(commerce_dir / "state.json", {"status": "not_started", "message": "尚未生成 AI 商品素材"}),
        "job": job,
    }


@router.post("/api/commerce/clips/{task_id}/{segment_id}/analyze")
def analyze_clip_cover(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    return _queue_commerce_task(task_id, segment_id, ["analyze"])


@router.post("/api/commerce/clips/{task_id}/{segment_id}/copywriting")
def generate_clip_copywriting(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    return _queue_commerce_task(task_id, segment_id, ["copywriting"])


@router.post("/api/commerce/clips/{task_id}/{segment_id}/images")
def generate_clip_images(task_id: str, segment_id: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid

    return _queue_commerce_task(task_id, segment_id, ["images"])


@router.post("/api/commerce/clips/{task_id}/{segment_id}/images/{item_key}")
def generate_clip_image_item(task_id: str, segment_id: str, item_key: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid
    if item_key not in _IMAGE_KEYS:
        return JSONResponse(status_code=400, content={"detail": "图片类型无效"})

    return _queue_commerce_task(task_id, segment_id, ["images"], image_keys=[item_key])


def _queue_commerce_task(task_id: str, segment_id: str, actions: list[str], image_keys: list[str] | None = None):
    meta = _clip_meta(task_id, segment_id)
    if meta is None:
        return JSONResponse(status_code=404, content={"detail": "未找到该片段"})
    from app.tasks.pipeline import process_commerce_assets

    job = _write_commerce_job(
        task_id,
        segment_id,
        {
            "status": "queued",
            "actions": actions,
            "image_keys": image_keys or [],
            "message": "AI 商品素材任务已排队",
            "queued_at": _now_iso(),
            "error": "",
        },
    )
    result = process_commerce_assets.delay(task_id, str(UPLOAD_DIR / task_id), segment_id, actions, image_keys)
    job = _write_commerce_job(task_id, segment_id, {"celery_id": result.id})
    return {"task_id": task_id, "segment_id": segment_id, "status": "queued", "job": job}


@router.post("/api/commerce/batch")
def queue_commerce_batch(request: CommerceBatchRequest):
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for clip_id in request.clip_ids:
        if "/" not in clip_id:
            rejected.append({"clip_id": clip_id, "detail": "片段 ID 格式无效"})
            continue
        task_id, segment_id = clip_id.split("/", 1)
        invalid = _validate_ids(task_id, segment_id)
        if invalid:
            rejected.append({"clip_id": clip_id, "detail": "任务或片段 ID 格式无效"})
            continue
        meta = _clip_meta(task_id, segment_id)
        if meta is None:
            rejected.append({"clip_id": clip_id, "detail": "未找到该片段"})
            continue
        response = _queue_commerce_task(task_id, segment_id, request.actions)
        if isinstance(response, JSONResponse):
            rejected.append({"clip_id": clip_id, "detail": "任务排队失败"})
        else:
            accepted.append(response)
    return {"accepted": accepted, "rejected": rejected, "total": len(request.clip_ids)}


@router.get("/api/commerce/clips/{task_id}/{segment_id}/images/{filename}")
def get_commerce_image(task_id: str, segment_id: str, filename: str):
    invalid = _validate_ids(task_id, segment_id)
    if invalid:
        return invalid
    if not _IMAGE_NAME_RE.match(filename):
        return JSONResponse(status_code=400, content={"detail": "Invalid image filename"})
    image_path = _commerce_dir(task_id, segment_id) / "images" / filename
    if not image_path.exists():
        return JSONResponse(status_code=404, content={"detail": "图片不存在"})
    return FileResponse(image_path, media_type="image/png")
