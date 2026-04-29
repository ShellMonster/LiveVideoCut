import json
import logging
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
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default))
