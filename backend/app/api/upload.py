# pyright: reportImplicitRelativeImport=false, reportFunctionMemberAccess=false

import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.api.settings import SettingsRequest
from app.services.validator import ValidationError, VideoValidator
from app.tasks.pipeline import start_pipeline

UPLOAD_DIR = Path("uploads")

router = APIRouter()
validator = VideoValidator()


def _resolve_upload_settings(settings_json: str | None) -> SettingsRequest:
    payload: dict[str, object] = {}

    if settings_json:
        try:
            parsed = json.loads(settings_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "type": "json_invalid",
                        "loc": ["body", "settings_json"],
                        "msg": f"Invalid JSON: {exc.msg}",
                        "input": settings_json,
                    }
                ],
            ) from exc

        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "type": "model_type",
                        "loc": ["body", "settings_json"],
                        "msg": "settings_json must decode to an object",
                        "input": parsed,
                    }
                ],
            )
        payload = parsed

    env_api_key = os.getenv("VLM_API_KEY", "").strip()
    if not str(payload.get("api_key", "")).strip() and env_api_key:
        payload["api_key"] = env_api_key

    if not settings_json:
        legacy_api_base = os.getenv("VLM_BASE_URL")
        legacy_model = os.getenv("VLM_MODEL")
        if legacy_api_base:
            payload.setdefault("api_base", legacy_api_base)
        if legacy_model:
            payload.setdefault("model", legacy_model)

    try:
        return SettingsRequest.model_validate(payload)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.post("/api/upload")
async def upload_file(file: UploadFile, settings_json: str | None = Form(None)):
    # 1. Validate extension
    validator.validate_format(file.filename or "")

    # 2. Validate size (content-length header)
    validator.validate_size(file.size or 0)

    resolved_settings = _resolve_upload_settings(settings_json)

    # 3. Generate task_id and create directory
    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # 4. Save file
    dest = task_dir / "original.mp4"
    content = await file.read()
    dest.write_bytes(content)

    # 5. Validate codec + audio with ffprobe on saved file
    file_path = str(dest)
    try:
        validator.validate_codec(file_path)
        validator.validate_audio(file_path)
    except ValidationError:
        # Clean up invalid file
        dest.unlink(missing_ok=True)
        task_dir.rmdir()
        raise

    # 6. Get metadata and save
    metadata = validator.get_metadata(file_path)
    meta_path = task_dir / "meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2))

    settings_path = task_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            resolved_settings.model_dump(mode="json"), ensure_ascii=False, indent=2
        )
    )

    # 7. Dispatch Celery task
    start_pipeline.delay(task_id, file_path)

    return {"task_id": task_id, "metadata": metadata}
