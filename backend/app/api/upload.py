import json
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile

from app.services.validator import ValidationError, VideoValidator
from app.tasks.pipeline import start_pipeline

UPLOAD_DIR = Path("uploads")

router = APIRouter()
validator = VideoValidator()


@router.post("/api/upload")
async def upload_file(file: UploadFile):
    # 1. Validate extension
    validator.validate_format(file.filename or "")

    # 2. Validate size (content-length header)
    validator.validate_size(file.size or 0)

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

    # 7. Dispatch Celery task
    start_pipeline.delay(task_id, file_path)

    return {"task_id": task_id, "metadata": metadata}
