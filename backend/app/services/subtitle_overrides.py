import re
from typing import Any

MAX_SUBTITLE_OVERRIDE_LINES = 500
MAX_SUBTITLE_OVERRIDE_TEXT_CHARS = 240
MAX_SUBTITLE_OVERRIDE_TOTAL_TEXT_CHARS = 30_000

_ASS_CONTROL_RE = re.compile(r"[{}\\]")
_ASS_OVERRIDE_BLOCK_RE = re.compile(r"\{\\[^{}]*\}")
_ASCII_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_subtitle_override_text(text: Any) -> str:
    value = _ASCII_CONTROL_RE.sub("", str(text))
    return _WHITESPACE_RE.sub(" ", value).strip()


def has_ass_control_chars(text: str) -> bool:
    return bool(_ASS_CONTROL_RE.search(text))


def sanitize_subtitle_override_text(text: Any) -> str:
    value = _ASS_OVERRIDE_BLOCK_RE.sub("", str(text))
    value = normalize_subtitle_override_text(value)
    value = _ASS_CONTROL_RE.sub("", value)
    return value[:MAX_SUBTITLE_OVERRIDE_TEXT_CHARS].strip()
