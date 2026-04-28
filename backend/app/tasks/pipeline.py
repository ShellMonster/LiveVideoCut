# pyright: reportImplicitRelativeImport=false, reportAttributeAccessIssue=false

import json
import logging
import os
import subprocess
import time
import datetime
from pathlib import Path
from typing import Any, cast

from celery import Celery, chain

# Settings model
from app.api.settings import SettingsRequest

# Services (re-exported for test monkeypatching compatibility)
from app.services.clothing_change_detector import ClothingChangeDetector
from app.services.cleanup import TempFileCleaner
from app.services.error_handler import PipelineErrorHandler
from app.services.ffmpeg_builder import FFmpegBuilder
from app.services.dashscope_asr_client import DashScopeASRClient
from app.services.volcengine_asr_client import VolcengineASRClient
from app.services.volcengine_vc_client import VolcengineVCClient
from app.services.asr_errors import AuthError, TranscriptionError
from app.services.product_matcher import ProductNameMatcher
from app.services.segment_validator import SegmentValidator
from app.services.srt_generator import SRTGenerator
from app.services.state_machine import TaskStateMachine
from app.services.vlm_client import VLMClient
from app.services.vlm_confirmor import VLMConfirmor
from app.services.filler_filter import filter_subtitle_words, compute_filler_cut_ranges
from app.services.cover_selector import select_cover_frame
from app.services.resource_detector import calculate_parallelism
from app.services.text_segment_analyzer import TextSegmentAnalyzer
from app.services.segment_fusion import fuse_candidates, fused_to_segments
from app.services.bgm_selector import BGMSelector, DEFAULT_BGM

# Shared utilities (re-exported for test monkeypatching compatibility)
from app.tasks.shared import (
    _log_elapsed,
    _need_asr,
    _create_asr_client,
    _load_task_settings,
    _find_video,
    _get_video_duration,
)

# Stage implementations
from app.tasks.stages.visual_prescreen import run_visual_prescreen
from app.tasks.stages.vlm_confirm import run_vlm_confirm
from app.tasks.stages.enrich_segments import run_enrich_segments
from app.tasks.stages.process_clips import (
    run_process_clips,
    _process_single_clip,
    build_clip_basename,
    ASSETS_DIR,
    DEFAULT_WATERMARK,
)

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "clipper",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=1800,
    task_time_limit=3600,
    worker_disable_rate_limits=True,
)


@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,))
def start_pipeline(self, task_id: str, file_path: str) -> str:
    task_dir = str(Path(file_path).parent)
    settings = _load_task_settings(task_dir)
    visual_prescreen_task = cast(Any, visual_prescreen)
    vlm_confirm_task = cast(Any, vlm_confirm)
    enrich_segments_task = cast(Any, enrich_segments)
    process_clips_task = cast(Any, process_clips)

    workflow = chain(
        visual_prescreen_task.si(task_id, file_path, task_dir),
        vlm_confirm_task.si(
            task_id,
            task_dir,
            settings.api_key,
            settings.vlm_provider.value,
            settings.api_base,
            settings.model,
            settings.review_mode.value,
            settings.enable_vlm,
            settings.export_mode.value,
            settings.review_strictness.value,
        ),
        enrich_segments_task.si(task_id, task_dir),
        process_clips_task.si(task_id, task_dir),
    )
    workflow.apply_async()

    return task_id


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def visual_prescreen(
    self, task_id: str, video_path: str, task_dir: str
) -> dict[str, Any]:
    try:
        return run_visual_prescreen(task_id, video_path, task_dir)
    except Exception as exc:
        PipelineErrorHandler(task_dir=Path(task_dir)).handle_error("VISUAL_FAILED", str(exc), current_state="UPLOADED")
        raise self.retry(exc=exc, countdown=2**self.request.retries)


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def vlm_confirm(
    self,
    task_id: str,
    task_dir: str,
    api_key: str,
    provider: str = "qwen",
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: str = "qwen-vl-plus",
    review_mode: str = "segment_multiframe",
    enable_vlm: bool = True,
    export_mode: str = "smart",
    review_strictness: str = "standard",
) -> dict[str, Any]:
    try:
        return run_vlm_confirm(
            task_id, task_dir, api_key, provider, base_url, model,
            review_mode, enable_vlm, export_mode, review_strictness,
        )
    except Exception as exc:
        PipelineErrorHandler(task_dir=Path(task_dir)).handle_error("VLM_FAILED", str(exc), current_state="VISUAL_SCREENING")
        raise self.retry(exc=exc, countdown=2**self.request.retries)


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def enrich_segments(
    self,
    task_id: str,
    task_dir: str,
) -> dict[str, Any]:
    try:
        return run_enrich_segments(task_id, task_dir)
    except Exception as exc:
        PipelineErrorHandler(task_dir=Path(task_dir)).handle_error("ASR_FAILED", str(exc), current_state="VLM_CONFIRMING")
        raise self.retry(exc=exc, countdown=2**self.request.retries)


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def process_clips(self, task_id: str, task_dir: str) -> dict[str, Any]:
    try:
        return run_process_clips(task_id, task_dir)
    except Exception as exc:
        PipelineErrorHandler(task_dir=Path(task_dir)).handle_error("EXPORT_FAILED", str(exc), current_state="PROCESSING")
        raise self.retry(exc=exc, countdown=2**self.request.retries)


def _read_json_file(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _write_clip_job(task_path: Path, segment_id: str, payload: dict[str, Any]) -> None:
    jobs_path = task_path / "clip_jobs.json"
    jobs = _read_json_file(jobs_path, {})
    if not isinstance(jobs, dict):
        jobs = {}
    current = jobs.get(segment_id, {})
    if not isinstance(current, dict):
        current = {}
    current.update(payload)
    current["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    jobs[segment_id] = current
    jobs_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2))


@celery_app.task(bind=True, max_retries=1)
def process_commerce_assets(self, task_id: str, task_dir: str, segment_id: str, actions: list[str]) -> dict[str, Any]:
    try:
        from app.api.commerce import run_commerce_actions

        return run_commerce_actions(task_id, segment_id, actions)
    except Exception as exc:
        commerce_dir = Path(task_dir) / "commerce" / segment_id
        commerce_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "failed",
            "message": f"AI 商品素材生成失败：{exc}",
            "error": str(exc),
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        (commerce_dir / "job.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        (commerce_dir / "state.json").write_text(
            json.dumps({"status": "failed", "message": payload["message"]}, ensure_ascii=False, indent=2)
        )
        raise


def _load_review_segment(task_path: Path, segment_id: str) -> tuple[int, dict[str, Any]]:
    if not segment_id.startswith("clip_"):
        raise ValueError("Invalid segment id")
    idx = int(segment_id.replace("clip_", ""))
    segments = _read_json_file(task_path / "enriched_segments.json", [])
    if not isinstance(segments, list) or idx >= len(segments):
        raise ValueError(f"Segment not found: {segment_id}")
    segment = dict(segments[idx])

    review = _read_json_file(task_path / "review.json", {})
    overrides = {}
    if isinstance(review, dict):
        review_segments = review.get("segments", {})
        if isinstance(review_segments, dict) and isinstance(review_segments.get(segment_id), dict):
            overrides = review_segments[segment_id]
    segment.update(overrides)
    return idx, segment


@celery_app.task(bind=True, max_retries=1)
def reprocess_clip(self, task_id: str, task_dir: str, segment_id: str) -> dict[str, Any]:
    task_path = Path(task_dir)
    try:
        _write_clip_job(
            task_path,
            segment_id,
            {
                "status": "running",
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "error": "",
            },
        )

        settings = _load_task_settings(task_path)
        video_path = _find_video(task_path)
        if not video_path:
            raise FileNotFoundError("No video file found")

        idx, segment = _load_review_segment(task_path, segment_id)
        transcript = _read_json_file(task_path / "transcript.json", [])
        if not isinstance(transcript, list):
            transcript = []

        frames_index = task_path / "frames" / "frames.json"
        pre_sampled_frames = _read_json_file(frames_index, [])
        if not isinstance(pre_sampled_frames, list):
            pre_sampled_frames = []

        clips_dir = task_path / "clips"
        srt_dir = task_path / "srt"
        covers_dir = task_path / "covers"
        clips_dir.mkdir(parents=True, exist_ok=True)
        srt_dir.mkdir(parents=True, exist_ok=True)
        covers_dir.mkdir(parents=True, exist_ok=True)

        bgm_selector = BGMSelector.with_user_library(ASSETS_DIR / "bgm" / "bgm_library.json")
        result = _process_single_clip(
            idx,
            segment,
            video_path,
            clips_dir,
            srt_dir,
            covers_dir,
            transcript,
            settings,
            pre_sampled_frames,
            bgm_selector,
            set(),
        )
        if result is None:
            raise RuntimeError("Clip export failed")

        _write_clip_job(
            task_path,
            segment_id,
            {
                "status": "completed",
                "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "error": "",
            },
        )
        return {"task_id": task_id, "segment_id": segment_id, "status": "completed"}
    except Exception as exc:
        _write_clip_job(
            task_path,
            segment_id,
            {
                "status": "failed",
                "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "error": str(exc),
            },
        )
        raise
