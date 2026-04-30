# pyright: reportImplicitRelativeImport=false, reportFunctionMemberAccess=false

import json
import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.api.settings import SENSITIVE_FIELDS, SettingsRequest
from app.config import UPLOAD_DIR
from app.services import app_settings
from app.services.list_index import refresh_task_index
from app.services.validator import MAX_FILE_SIZE, ValidationError, VideoValidator
from app.tasks.pipeline import start_pipeline
from app.utils.json_io import write_json

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

    payload = app_settings.merge_with_global_defaults(payload, UPLOAD_DIR)

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

    # 4. Save file (streaming write to avoid OOM on large videos)
    dest = task_dir / "original.mp4"
    _CHUNK_SIZE = 1024 * 1024
    with dest.open("wb") as f:
        while chunk := await file.read(_CHUNK_SIZE):
            f.write(chunk)

    # 4.1 Validate actual file size on disk (Content-Length header can be spoofed)
    actual_size = dest.stat().st_size
    if actual_size > MAX_FILE_SIZE:
        dest.unlink(missing_ok=True)
        gb = actual_size / (1024**3)
        raise HTTPException(
            status_code=422,
            detail=f"File too large: {gb:.1f}GB. Maximum size is 20GB.",
        )

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
    metadata["created_at"] = datetime.now(UTC).isoformat()
    metadata["original_filename"] = file.filename or "unknown.mp4"
    meta_path = task_dir / "meta.json"
    write_json(meta_path, metadata)

    settings_path = task_dir / "settings.json"
    full_payload = resolved_settings.model_dump(mode="json")

    safe_payload = {k: v for k, v in full_payload.items() if k not in SENSITIVE_FIELDS}
    write_json(settings_path, safe_payload)

    secrets_payload = {k: v for k, v in full_payload.items() if k in SENSITIVE_FIELDS and v}
    if secrets_payload:
        secrets_path = task_dir / "secrets.json"
        write_json(secrets_path, secrets_payload)
        secrets_path.chmod(0o600)

    # 7. Dispatch Celery task
    refresh_task_index(UPLOAD_DIR, task_id)
    start_pipeline.delay(task_id, file_path)

    return {"task_id": task_id, "metadata": metadata}
