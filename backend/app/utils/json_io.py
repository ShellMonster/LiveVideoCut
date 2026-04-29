import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def read_json(path: str | Path, fallback: Any, *, log_errors: bool = True) -> Any:
    json_path = Path(path)
    if not json_path.exists():
        return fallback
    try:
        return json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        if log_errors:
            logger.warning("Failed to read JSON file %s, using fallback", json_path, exc_info=True)
        return fallback


def read_json_silent(path: str | Path, fallback: Any) -> Any:
    return read_json(path, fallback, log_errors=False)


def write_json(
    path: str | Path,
    payload: Any,
    *,
    ensure_parent: bool = True,
    json_default: Callable[[Any], Any] | None = None,
) -> None:
    json_path = Path(path)
    if ensure_parent:
        json_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=json_default)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=json_path.parent,
            prefix=f".{json_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, json_path)
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
