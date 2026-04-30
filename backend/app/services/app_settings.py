"""Persistent application settings backed by SQLite.

The existing uploads/index.sqlite3 file is a rebuildable list cache. This module
keeps user-editable global settings in a separate database so settings survive
browser cache clears without becoming part of the task index cache.
"""

from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import sqlite3
from typing import Any

from app.config import DEFAULT_API_BASES, DEFAULT_MODELS, UPLOAD_DIR

APP_CONFIG_DB = "app_config.sqlite3"


SETTING_DEFAULTS: dict[str, Any] = {
    "enable_vlm": True,
    "export_mode": "smart",
    "vlm_provider": "qwen",
    "api_key": "",
    "api_base": DEFAULT_API_BASES["qwen"],
    "model": DEFAULT_MODELS["qwen"],
    "review_strictness": "standard",
    "review_mode": "segment_multiframe",
    "scene_threshold": 27,
    "frame_sample_fps": 0.5,
    "recall_cooldown_seconds": 15,
    "candidate_looseness": "standard",
    "min_segment_duration_seconds": 25,
    "dedupe_window_seconds": 90,
    "merge_count": 1,
    "allow_returned_product": True,
    "max_candidate_count": 20,
    "subtitle_mode": "karaoke",
    "subtitle_position": "bottom",
    "subtitle_template": "clean",
    "subtitle_font_size": 60,
    "subtitle_highlight_font_size": 72,
    "filter_filler_mode": "off",
    "sensitive_filter_enabled": False,
    "sensitive_words": [],
    "sensitive_filter_mode": "video_segment",
    "sensitive_match_mode": "contains",
    "cover_strategy": "content_first",
    "video_speed": 1.25,
    "boundary_snap": True,
    "enable_boundary_refinement": False,
    "custom_position_y": None,
    "asr_provider": "volcengine_vc",
    "asr_api_key": "",
    "tos_ak": "",
    "tos_sk": "",
    "tos_bucket": "mp3-srt",
    "tos_region": "cn-beijing",
    "tos_endpoint": "tos-cn-beijing.volces.com",
    "enable_llm_analysis": False,
    "llm_api_key": "",
    "llm_api_base": "",
    "llm_model": "",
    "llm_type": "openai",
    "export_resolution": "1080p",
    "segment_granularity": "single_item",
    "change_detection_fusion_mode": "any_signal",
    "change_detection_sensitivity": "balanced",
    "clothing_yolo_confidence": 0.25,
    "ffmpeg_preset": "fast",
    "ffmpeg_crf": 23,
    "bgm_enabled": True,
    "bgm_volume": 0.25,
    "original_volume": 1.0,
    "commerce_gemini_api_key": "",
    "commerce_gemini_api_base": "https://generativelanguage.googleapis.com",
    "commerce_gemini_model": "gemini-3-flash-preview",
    "commerce_gemini_timeout_seconds": 150,
    "commerce_image_api_key": "",
    "commerce_image_api_base": "https://api.openai.com/v1",
    "commerce_image_model": "gpt-image-2",
    "commerce_image_size": "2K",
    "commerce_image_quality": "auto",
    "commerce_image_timeout_seconds": 500,
}

SENSITIVE_SETTING_KEYS = frozenset(
    {
        "api_key",
        "asr_api_key",
        "tos_ak",
        "tos_sk",
        "llm_api_key",
        "commerce_gemini_api_key",
        "commerce_image_api_key",
    }
)

ENV_SETTING_KEYS: dict[str, str] = {
    "api_key": "VLM_API_KEY",
    "api_base": "VLM_BASE_URL",
    "model": "VLM_MODEL",
    "asr_api_key": "VOLCENGINE_ASR_API_KEY",
    "tos_ak": "TOS_AK",
    "tos_sk": "TOS_SK",
    "tos_bucket": "TOS_BUCKET",
    "tos_region": "TOS_REGION",
    "tos_endpoint": "TOS_ENDPOINT",
    "llm_api_key": "LLM_API_KEY",
    "llm_api_base": "LLM_API_BASE",
    "llm_model": "LLM_MODEL",
    "llm_type": "LLM_TYPE",
    "commerce_gemini_api_key": "COMMERCE_GEMINI_API_KEY",
    "commerce_gemini_api_base": "COMMERCE_GEMINI_API_BASE",
    "commerce_gemini_model": "COMMERCE_GEMINI_MODEL",
    "commerce_image_api_key": "COMMERCE_IMAGE_API_KEY",
    "commerce_image_api_base": "COMMERCE_IMAGE_API_BASE",
    "commerce_image_model": "COMMERCE_IMAGE_MODEL",
    "commerce_image_size": "COMMERCE_IMAGE_SIZE",
    "commerce_image_quality": "COMMERCE_IMAGE_QUALITY",
}


def _db_path(upload_dir: Path = UPLOAD_DIR) -> Path:
    return upload_dir / APP_CONFIG_DB


def _connect(upload_dir: Path = UPLOAD_DIR) -> sqlite3.Connection:
    upload_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path(upload_dir), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'string',
            sensitive INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "json"
    if value is None:
        return "null"
    return "string"


def _serialize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        import json

        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _deserialize(value: str, value_type: str) -> Any:
    if value_type == "bool":
        return value.lower() == "true"
    if value_type == "int":
        try:
            return int(value)
        except ValueError:
            return 0
    if value_type == "float":
        try:
            return float(value)
        except ValueError:
            return 0.0
    if value_type == "json":
        import json

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    if value_type == "null":
        return None
    return value


def _env_defaults() -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for setting_key, env_key in ENV_SETTING_KEYS.items():
        value = os.getenv(env_key, "").strip()
        if value:
            defaults[setting_key] = value
    return defaults


def read_saved_settings(upload_dir: Path = UPLOAD_DIR) -> dict[str, Any]:
    with _connect(upload_dir) as conn:
        rows = conn.execute("SELECT key, value, value_type FROM app_settings").fetchall()
    return {str(row["key"]): _deserialize(str(row["value"]), str(row["value_type"])) for row in rows}


def get_current_settings(upload_dir: Path = UPLOAD_DIR) -> dict[str, Any]:
    current = dict(SETTING_DEFAULTS)
    current.update(_env_defaults())
    current.update(read_saved_settings(upload_dir))
    return current


def save_current_settings(payload: dict[str, Any], upload_dir: Path = UPLOAD_DIR) -> dict[str, Any]:
    allowed = set(SETTING_DEFAULTS)
    now = datetime.now(UTC).isoformat()
    with _connect(upload_dir) as conn:
        for key, value in payload.items():
            if key not in allowed:
                continue
            if value is None or (isinstance(value, str) and value == ""):
                conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
                continue
            value_type = _value_type(value)
            conn.execute(
                """
                INSERT INTO app_settings (key, value, value_type, sensitive, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    value_type = excluded.value_type,
                    sensitive = excluded.sensitive,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    _serialize(value),
                    value_type,
                    1 if key in SENSITIVE_SETTING_KEYS else 0,
                    now,
                ),
            )
        conn.commit()
    return get_current_settings(upload_dir)


def reset_current_settings(upload_dir: Path = UPLOAD_DIR) -> dict[str, Any]:
    with _connect(upload_dir) as conn:
        conn.execute("DELETE FROM app_settings")
        conn.commit()
    return get_current_settings(upload_dir)


def merge_with_global_defaults(payload: dict[str, Any], upload_dir: Path = UPLOAD_DIR) -> dict[str, Any]:
    merged = get_current_settings(upload_dir)
    for key, value in payload.items():
        if value in (None, "") and key in merged and merged[key] not in (None, ""):
            continue
        merged[key] = value

    provider = str(payload.get("vlm_provider") or "").strip()
    if provider in DEFAULT_API_BASES:
        if not str(payload.get("api_base") or "").strip():
            merged["api_base"] = DEFAULT_API_BASES[provider]
        if not str(payload.get("model") or "").strip():
            merged["model"] = DEFAULT_MODELS[provider]
    return merged
