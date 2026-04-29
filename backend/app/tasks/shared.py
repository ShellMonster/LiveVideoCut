import json
import logging
import os
import subprocess
import time
from pathlib import Path

from app.api.settings import SettingsRequest
from app.services.dashscope_asr_client import DashScopeASRClient
from app.services.volcengine_asr_client import VolcengineASRClient
from app.services.volcengine_vc_client import VolcengineVCClient
from app.utils.json_io import read_json, read_json_silent

logger = logging.getLogger(__name__)


def _log_elapsed(label: str, started_at: float) -> None:
    logger.info("%s finished in %.2fs", label, time.perf_counter() - started_at)


def _read_json_file(path: Path, fallback):
    return read_json(path, fallback)


def _need_asr(settings: SettingsRequest) -> bool:
    """ASR is needed when downstream logic needs transcript text."""
    subtitle_on = settings.subtitle_mode.value != "off"
    llm_on = settings.enable_llm_analysis
    sensitive_on = settings.sensitive_filter_enabled and bool(settings.sensitive_words)
    return subtitle_on or llm_on or sensitive_on


def _create_asr_client(settings: SettingsRequest) -> DashScopeASRClient | VolcengineASRClient | VolcengineVCClient:
    """Create ASR client based on settings.asr_provider.
    
    Credentials are read from env vars (VOLCENGINE_ASR_API_KEY, TOS_AK etc.)
    via each client's __init__ fallback. We only pass non-empty values from
    settings so that empty strings from the frontend don't override env vars.
    """
    from app.tasks.pipeline import (
        DashScopeASRClient,
        VolcengineASRClient,
        VolcengineVCClient,
    )

    def _opt(val: str | None) -> str | None:
        return val if val else None

    if settings.asr_provider.value == "volcengine":
        return VolcengineASRClient(
            api_key=_opt(settings.asr_api_key),
            tos_ak=_opt(settings.tos_ak),
            tos_sk=_opt(settings.tos_sk),
            tos_bucket=_opt(settings.tos_bucket),
            tos_region=_opt(settings.tos_region),
            tos_endpoint=_opt(settings.tos_endpoint),
        )
    if settings.asr_provider.value == "volcengine_vc":
        return VolcengineVCClient(
            api_key=_opt(settings.asr_api_key),
            tos_ak=_opt(settings.tos_ak),
            tos_sk=_opt(settings.tos_sk),
            tos_bucket=_opt(settings.tos_bucket),
            tos_region=_opt(settings.tos_region),
            tos_endpoint=_opt(settings.tos_endpoint),
        )
    return DashScopeASRClient()


def _load_task_settings(task_dir: str | Path) -> SettingsRequest:
    task_path = Path(task_dir)
    settings_path = task_path / "settings.json"

    payload: dict[str, object] = {}

    raw_settings = read_json_silent(settings_path, {})
    if isinstance(raw_settings, dict):
        payload = raw_settings

    secrets_path = task_path / "secrets.json"
    raw_secrets = read_json_silent(secrets_path, {})
    if isinstance(raw_secrets, dict):
        payload.update(raw_secrets)

    env_api_key = os.getenv("VLM_API_KEY", "").strip()
    if not str(payload.get("api_key", "")).strip() and env_api_key:
        payload["api_key"] = env_api_key

    if not settings_path.exists():
        legacy_api_base = os.getenv("VLM_BASE_URL")
        legacy_model = os.getenv("VLM_MODEL")
        if legacy_api_base:
            payload.setdefault("api_base", legacy_api_base)
        if legacy_model:
            payload.setdefault("model", legacy_model)

    return SettingsRequest.model_validate(payload)


def _find_video(task_path: Path) -> Path | None:
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"}
    for ext in video_extensions:
        matches = list(task_path.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


def _get_video_duration(video_path: str) -> float:
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError) as exc:
        logger.warning(
            "Failed to detect video duration for %s, falling back to 3600s: %s",
            video_path,
            exc,
        )
        return 3600.0
