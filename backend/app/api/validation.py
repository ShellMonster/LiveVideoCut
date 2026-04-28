import re

TASK_ID_RE = re.compile(r"^[a-f0-9\-]{36}$", re.IGNORECASE)
SAFE_TASK_DIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
SEGMENT_ID_RE = re.compile(r"^clip_\d{3,}$")
IMAGE_NAME_RE = re.compile(r"^[a-z0-9_]+\.png$")


def is_task_id(value: str) -> bool:
    return bool(TASK_ID_RE.match(value))


def is_safe_task_dir(value: str) -> bool:
    return bool(SAFE_TASK_DIR_RE.match(value))


def is_segment_id(value: str) -> bool:
    return bool(SEGMENT_ID_RE.match(value))
