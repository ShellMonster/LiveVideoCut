# pyright: reportImplicitRelativeImport=false, reportAttributeAccessIssue=false

import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast
from collections.abc import Sequence

from celery import Celery, chain

from app.api.settings import SettingsRequest
from app.services.clothing_change_detector import ClothingChangeDetector
from app.services.cleanup import TempFileCleaner
from app.services.error_handler import PipelineErrorHandler
from app.services.ffmpeg_builder import FFmpegBuilder
from app.services.dashscope_asr_client import DashScopeASRClient
from app.services.volcengine_asr_client import VolcengineASRClient
from app.services.volcengine_vc_client import VolcengineVCClient
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

logger = logging.getLogger(__name__)


def _create_asr_client(settings: SettingsRequest) -> DashScopeASRClient | VolcengineASRClient | VolcengineVCClient:
    """Create ASR client based on settings.asr_provider."""
    if settings.asr_provider.value == "volcengine":
        return VolcengineASRClient(
            api_key=settings.asr_api_key,
            tos_ak=settings.tos_ak,
            tos_sk=settings.tos_sk,
            tos_bucket=settings.tos_bucket,
            tos_region=settings.tos_region,
            tos_endpoint=settings.tos_endpoint,
        )
    if settings.asr_provider.value == "volcengine_vc":
        return VolcengineVCClient(
            api_key=settings.asr_api_key,
            tos_ak=settings.tos_ak,
            tos_sk=settings.tos_sk,
            tos_bucket=settings.tos_bucket,
            tos_region=settings.tos_region,
            tos_endpoint=settings.tos_endpoint,
        )
    return DashScopeASRClient()

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


def _load_task_settings(task_dir: str | Path) -> SettingsRequest:
    task_path = Path(task_dir)
    settings_path = task_path / "settings.json"

    if settings_path.exists():
        return SettingsRequest.model_validate_json(settings_path.read_text())

    payload: dict[str, object] = {
        "api_key": os.getenv("VLM_API_KEY", ""),
    }
    legacy_api_base = os.getenv("VLM_BASE_URL")
    legacy_model = os.getenv("VLM_MODEL")
    if legacy_api_base:
        payload["api_base"] = legacy_api_base
    if legacy_model:
        payload["model"] = legacy_model
    return SettingsRequest.model_validate(payload)


def _build_confirmed_segments_without_vlm(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    confirmed_segments: list[dict[str, Any]] = []
    for candidate in candidates:
        timestamp = float(candidate.get("timestamp", 0.0))
        confidence = float(candidate.get("similarity", 0.0))
        confirmed_segments.append(
            {
                "start_time": timestamp,
                "end_time": timestamp,
                "confidence": confidence,
                "product_info": {},
                "low_confidence": True,
            }
        )
    return confirmed_segments


def _build_export_segments_from_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "start_time": float(candidate.get("timestamp", 0.0)),
            "end_time": float(candidate.get("timestamp", 0.0)),
            "confidence": float(candidate.get("similarity", 0.0)),
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "export_mode",
        }
        for candidate in candidates
    ]


def _build_export_segments_from_scenes(
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "start_time": float(scene.get("start_time", 0.0)),
            "end_time": float(scene.get("end_time", 0.0)),
            "confidence": 0.0,
            "product_info": {},
            "low_confidence": True,
            "product_name": "未命名商品",
            "name_source": "export_mode",
        }
        for scene in scenes
    ]


def _attach_transcript_text(
    segments: list[dict[str, Any]], transcript: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    enriched_segments: list[dict[str, Any]] = []
    for segment in segments:
        start_time = float(segment.get("start_time", 0.0))
        end_time = float(segment.get("end_time", 0.0))
        relevant_texts: list[str] = []

        for transcript_segment in transcript:
            transcript_start = float(transcript_segment.get("start_time", 0.0))
            transcript_end = float(transcript_segment.get("end_time", 0.0))
            if transcript_start <= end_time and transcript_end >= start_time:
                text = str(transcript_segment.get("text", "")).strip()
                if text:
                    relevant_texts.append(text)

        enriched_segment = dict(segment)
        enriched_segment["text"] = " ".join(relevant_texts).strip()
        enriched_segments.append(enriched_segment)

    return enriched_segments


def _write_confirmed_segments(
    task_path: Path, confirmed_segments: list[dict[str, Any]]
) -> None:
    vlm_dir = task_path / "vlm"
    vlm_dir.mkdir(parents=True, exist_ok=True)
    output_file = vlm_dir / "confirmed_segments.json"
    output_file.write_text(json.dumps(confirmed_segments, ensure_ascii=False, indent=2))


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
    task_path = Path(task_dir)
    settings = _load_task_settings(task_path)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    try:
        sm.transition("UPLOADED", "EXTRACTING_FRAMES", step="extracting_frames")

        frames_dir = task_path / "frames" / "scene000"
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_pattern = str(frames_dir / "frame_%05d.jpg")
        sample_fps = settings.frame_sample_fps

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-vf",
                f"fps={sample_fps}",
                "-q:v",
                "2",
                frame_pattern,
            ],
            capture_output=True,
            timeout=600,
            check=True,
        )

        frames = []
        for jpg in sorted(frames_dir.glob("frame_*.jpg")):
            frame_num = int(jpg.stem.split("_")[1])
            frames.append(
                {
                    "path": str(jpg),
                    "timestamp": round((frame_num - 1) / sample_fps, 3),
                    "scene_idx": 0,
                }
            )
        logger.info("Extracted %d frames at %.2f fps", len(frames), sample_fps)

        sm.transition("EXTRACTING_FRAMES", "SCENE_DETECTING", step="scene_detecting")

        clothing_detector = ClothingChangeDetector(
            hist_threshold=0.90,
            min_scene_gap=float(settings.recall_cooldown_seconds),
            merge_window=16.0,
        )
        candidates = clothing_detector.detect_from_frames(
            frames,
            output_dir=str(task_path / "scenes"),
        )
        sm.transition("SCENE_DETECTING", "VISUAL_SCREENING", step="visual_screening")

        # 同时生成 scenes.json（供 all_scenes 模式使用）
        video_duration = _get_video_duration(video_path)
        scenes = ClothingChangeDetector.detect_scenes_from_candidates(
            candidates,
            video_duration,
        )
        scenes_dir = task_path / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        (scenes_dir / "scenes.json").write_text(
            json.dumps(scenes, ensure_ascii=False, indent=2),
        )

        candidates_file = task_path / "candidates.json"
        candidates_file.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))

        cleaner.cleanup_frames(task_dir)

        return {
            "candidates_count": len(candidates),
            "scenes_count": len(scenes),
            "frames_count": len(frames),
        }
    except Exception as exc:
        err.handle_error("VISUAL_FAILED", str(exc), current_state="UPLOADED")
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
    task_path = Path(task_dir)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)

    try:
        sm.transition("VISUAL_SCREENING", "VLM_CONFIRMING", step="vlm_confirming")

        candidates_file = task_path / "candidates.json"
        if not candidates_file.exists():
            return {"confirmed_count": 0, "total_candidates": 0}

        candidates = json.loads(candidates_file.read_text())
        frames_dir = str(task_path / "frames")

        if export_mode == "smart" and not enable_vlm:
            export_mode = "no_vlm"

        if export_mode == "no_vlm":
            confirmed = _build_confirmed_segments_without_vlm(candidates)
            _write_confirmed_segments(task_path, confirmed)
            return {
                "confirmed_count": len(confirmed),
                "total_candidates": len(candidates),
            }

        if export_mode in {"all_candidates", "all_scenes"}:
            return {
                "confirmed_count": 0,
                "total_candidates": len(candidates),
            }

        logger.info(
            "Starting VLM confirm for task %s with provider=%s model=%s base_url=%s review_mode=%s",
            task_id,
            provider,
            model,
            base_url,
            review_mode,
        )

        client = VLMClient(
            api_key=api_key,
            provider=provider,
            base_url=base_url,
            model=model,
        )
        confirmor = VLMConfirmor(vlm_client=client)
        confirmed = confirmor.confirm_candidates(
            candidates,
            frames_dir,
            task_id=task_id,
            review_mode=review_mode,
            review_strictness=review_strictness,
        )

        return {
            "confirmed_count": len(confirmed),
            "total_candidates": len(candidates),
        }
    except Exception as exc:
        err.handle_error("VLM_FAILED", str(exc), current_state="VISUAL_SCREENING")
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
    task_path = Path(task_dir)
    settings = _load_task_settings(task_path)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    try:
        sm.transition("VLM_CONFIRMING", "TRANSCRIBING", step="transcribing")

        export_mode = settings.export_mode.value

        if export_mode == "all_candidates":
            candidates_file = task_path / "candidates.json"
            if not candidates_file.exists():
                logger.error("No candidates found: %s", candidates_file)
                return {"segments_count": 0, "validated_count": 0}

            candidates = json.loads(candidates_file.read_text())
            video_path = _find_video(task_path)
            if not video_path:
                logger.error("No video file found in %s", task_dir)
                return {"segments_count": len(candidates), "validated_count": 0}

            asr_client = _create_asr_client(settings)
            transcript = asr_client.transcribe(str(video_path))

            transcript_file = task_path / "transcript.json"
            transcript_file.write_text(
                json.dumps(transcript, ensure_ascii=False, indent=2)
            )

            export_segments = _attach_transcript_text(
                _build_export_segments_from_candidates(candidates), transcript
            )
            output_file = task_path / "enriched_segments.json"
            output_file.write_text(
                json.dumps(export_segments, ensure_ascii=False, indent=2)
            )
            sm.transition("TRANSCRIBING", "PROCESSING", step="processing")
            return {
                "segments_count": len(export_segments),
                "validated_count": len(export_segments),
            }

        if export_mode == "all_scenes":
            scenes_file = task_path / "scenes" / "scenes.json"
            if not scenes_file.exists():
                logger.error("No scenes found: %s", scenes_file)
                return {"segments_count": 0, "validated_count": 0}

            scenes = json.loads(scenes_file.read_text())
            video_path = _find_video(task_path)
            if not video_path:
                logger.error("No video file found in %s", task_dir)
                return {"segments_count": len(scenes), "validated_count": 0}

            asr_client = _create_asr_client(settings)
            if getattr(settings, "asr_enabled", True):
                transcript = asr_client.transcribe(str(video_path))
            else:
                logger.info("ASR disabled, skipping transcription (all_scenes path)")
                transcript = []

            transcript_file = task_path / "transcript.json"
            transcript_file.write_text(
                json.dumps(transcript, ensure_ascii=False, indent=2)
            )

            export_segments = _attach_transcript_text(
                _build_export_segments_from_scenes(scenes), transcript
            )
            output_file = task_path / "enriched_segments.json"
            output_file.write_text(
                json.dumps(export_segments, ensure_ascii=False, indent=2)
            )
            sm.transition("TRANSCRIBING", "PROCESSING", step="processing")
            return {
                "segments_count": len(export_segments),
                "validated_count": len(export_segments),
            }

        confirmed_file = task_path / "vlm" / "confirmed_segments.json"
        if not confirmed_file.exists():
            logger.error("No confirmed segments found: %s", confirmed_file)
            return {"segments_count": 0, "validated_count": 0}

        segments = json.loads(confirmed_file.read_text())

        video_path = _find_video(task_path)
        if not video_path:
            logger.error("No video file found in %s", task_dir)
            return {"segments_count": len(segments), "validated_count": 0}

        asr_client = _create_asr_client(settings)
        if getattr(settings, "asr_enabled", True):
            transcript = asr_client.transcribe(str(video_path))
        else:
            logger.info("ASR disabled, skipping transcription")
            transcript = []

        transcript_file = task_path / "transcript.json"
        transcript_file.write_text(json.dumps(transcript, ensure_ascii=False, indent=2))

        cleaner.cleanup_chunks(task_dir)

        if getattr(settings, "asr_enabled", True) and settings.enable_llm_analysis and settings.llm_api_key and settings.llm_api_base and settings.llm_model:
            try:
                sm.transition("TRANSCRIBING", "LLM_ANALYZING", step="llm_analysis")
                analyzer = TextSegmentAnalyzer(
                    api_key=settings.llm_api_key,
                    api_base=settings.llm_api_base,
                    model=settings.llm_model,
                    llm_type=settings.llm_type.value,
                )
                granularity = getattr(settings, "segment_granularity", "single_item")
                granularity = granularity.value if hasattr(granularity, "value") else granularity
                text_boundaries = analyzer.analyze(transcript, segment_granularity=granularity)
                logger.info("LLM text analysis found %d boundaries", len(text_boundaries))

                text_boundaries_file = task_path / "text_boundaries.json"
                text_boundaries_file.write_text(
                    json.dumps(text_boundaries, ensure_ascii=False, indent=2)
                )

                candidates_file = task_path / "candidates.json"
                visual_candidates = json.loads(candidates_file.read_text()) if candidates_file.exists() else []
                video_duration = _get_video_duration(str(video_path))

                fused = fuse_candidates(visual_candidates, text_boundaries, video_duration, segment_granularity=granularity)
                fused_file = task_path / "fused_candidates.json"
                fused_file.write_text(json.dumps(fused, ensure_ascii=False, indent=2))

                logger.info("Fused %d visual + %d text → %d candidates", len(visual_candidates), len(text_boundaries), len(fused))

                if fused:
                    segments = fused_to_segments(fused, video_duration)
                    logger.info("Using %d fused segments (replacing VLM segments)", len(segments))

                sm.transition("LLM_ANALYZING", "TRANSCRIBING", step="transcribing")
            except Exception as e:
                logger.warning("LLM text analysis failed, continuing without it: %s", str(e))

        matcher = ProductNameMatcher()
        enriched = matcher.match(segments, transcript)

        video_duration = _get_video_duration(str(video_path))

        validator = SegmentValidator(
            min_duration=float(settings.min_segment_duration_seconds),
            dedupe_window=float(settings.dedupe_window_seconds),
            allow_returned_product=settings.allow_returned_product,
        )
        validated = validator.validate(enriched, video_duration)

        output_file = task_path / "enriched_segments.json"
        output_file.write_text(json.dumps(validated, ensure_ascii=False, indent=2))

        sm.transition("TRANSCRIBING", "PROCESSING", step="processing")

        return {
            "segments_count": len(segments),
            "validated_count": len(validated),
        }
    except Exception as exc:
        err.handle_error("ASR_FAILED", str(exc), current_state="VLM_CONFIRMING")
        raise self.retry(exc=exc, countdown=2**self.request.retries)


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
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return 3600.0


ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
DEFAULT_BGM = str(ASSETS_DIR / "default_bgm.mp3")
DEFAULT_WATERMARK = str(ASSETS_DIR / "watermark.png")


def build_clip_basename(index: int, _product_name: str) -> str:
    """Return a stable ASCII-only basename for exported clip artifacts."""
    return f"clip_{index:03d}"


def build_clip_metadata(
    segment: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    return {
        "product_name": segment.get("product_name", "未知商品"),
        "duration": result.get(
            "duration",
            float(segment.get("end_time", 0.0)) - float(segment.get("start_time", 0.0)),
        ),
        "start_time": segment.get("start_time", 0.0),
        "end_time": segment.get("end_time", 0.0),
        "confidence": segment.get("confidence", 0),
    }


def _merge_segments(segments: list[dict], merge_count: int) -> list[dict]:
    merged: list[dict] = []
    for i in range(0, len(segments), merge_count):
        batch = segments[i : i + merge_count]
        if len(batch) == 1:
            merged.append(batch[0])
            continue
        start_time = float(batch[0].get("start_time", 0.0))
        end_time = float(batch[-1].get("end_time", 0.0))
        texts = [s.get("text", "") for s in batch if s.get("text")]
        merged.append({
            **batch[0],
            "start_time": start_time,
            "end_time": end_time,
            "text": " ".join(texts),
            "product_name": batch[0].get("product_name", "未知商品"),
        })
    logger.info(
        "Merged %d segments into %d (merge_count=%d)",
        len(segments), len(merged), merge_count,
    )
    return merged


def _collect_clip_subtitle_segments(
    segment: dict[str, Any], transcript: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    clip_start = float(segment.get("start_time", 0.0))
    clip_end = float(segment.get("end_time", 0.0))
    subtitle_segments: list[dict[str, Any]] = []

    for transcript_segment in transcript:
        transcript_start = float(transcript_segment.get("start_time", 0.0))
        transcript_end = float(transcript_segment.get("end_time", 0.0))
        if transcript_start > clip_end or transcript_end < clip_start:
            continue

        relative_start = max(transcript_start, clip_start) - clip_start
        relative_end = min(transcript_end, clip_end) - clip_start

        subtitle_segment = {
            "text": transcript_segment.get("text", ""),
            "start_time": relative_start,
            "end_time": relative_end,
        }

        words = []
        for word in transcript_segment.get("words", []) or []:
            word_start = float(word.get("start_time", transcript_start))
            word_end = float(word.get("end_time", transcript_end))
            if word_start > clip_end or word_end < clip_start:
                continue
            words.append(
                {
                    "text": word.get("text", ""),
                    "start_time": max(word_start, clip_start) - clip_start,
                    "end_time": min(word_end, clip_end) - clip_start,
                    "probability": word.get("probability", 0.0),
                }
            )

        if words:
            subtitle_segment["words"] = words

        subtitle_segments.append(subtitle_segment)

    return subtitle_segments


def _process_single_clip(
    idx: int,
    seg: dict[str, Any],
    video_path: Path,
    clips_dir: Path,
    srt_dir: Path,
    covers_dir: Path,
    transcript: list[dict[str, Any]],
    settings: SettingsRequest,
) -> dict[str, Any] | None:
    """Process a single clip — designed for ProcessPoolExecutor (module-level for pickling)."""
    try:
        seg_label = seg.get("product_name", f"segment_{idx}")
        safe_label = build_clip_basename(idx, seg_label)

        output_path = str((clips_dir / f"{safe_label}.mp4").resolve())
        thumbnail_path = str((covers_dir / f"{safe_label}.jpg").resolve())

        sub_segments = _collect_clip_subtitle_segments(seg, transcript)
        if not sub_segments:
            seg_text = seg.get("text", "")
            sub_segments = (
                [
                    {
                        "text": seg_text,
                        "start_time": 0.0,
                        "end_time": seg.get("end_time", 0.0)
                        - seg.get("start_time", 0.0),
                    }
                ]
                if seg_text
                else []
            )

        filler_mode = getattr(settings, "filter_filler_mode", "off")
        if filler_mode in ("subtitle", "video"):
            sub_segments = filter_subtitle_words(sub_segments)

        filler_cut_ranges: list = []
        if filler_mode == "video":
            filler_cut_ranges = compute_filler_cut_ranges(sub_segments)

        srt_gen = SRTGenerator()
        has_word_timing = any(bool(item.get("words")) for item in sub_segments)
        effective_subtitle_mode = srt_gen.resolve_phase1_export_mode(
            settings.subtitle_mode.value,
            has_text=bool(sub_segments),
            has_word_timing=has_word_timing,
        )
        clip_srt_path: str | None = None
        if effective_subtitle_mode != "off":
            try:
                subtitle_ext = (
                    ".ass" if effective_subtitle_mode == "karaoke" else ".srt"
                )
                subtitle_path = str(
                    (srt_dir / f"{safe_label}{subtitle_ext}").resolve()
                )
                clip_srt_path = srt_gen.generate(
                    sub_segments,
                    subtitle_path,
                    mode=effective_subtitle_mode,
                )
            except Exception:
                logger.warning(
                    "Subtitle asset generation failed for %s, exporting without subtitles",
                    safe_label,
                    exc_info=True,
                )
                effective_subtitle_mode = "off"

        cover_strategy = getattr(settings, "cover_strategy", "content_first")
        video_speed = getattr(settings, "video_speed", 1.0)
        export_resolution = getattr(settings, "export_resolution", "1080p")
        cover_ts = select_cover_frame(
            video_path=str(video_path),
            clip_start=float(seg.get("start_time", 0.0)),
            clip_end=float(seg.get("end_time", 0.0)),
            strategy=cover_strategy,
        )

        ffmpeg = FFmpegBuilder()
        result = ffmpeg.process_clip(
            input_path=str(video_path),
            segment=seg,
            srt_path=clip_srt_path,
            bgm_path=DEFAULT_BGM,
            watermark_path=DEFAULT_WATERMARK,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
            subtitle_mode=effective_subtitle_mode,
            subtitle_position=settings.subtitle_position.value,
            subtitle_template=settings.subtitle_template.value,
            custom_position_y=settings.custom_position_y,
            filler_cut_ranges=filler_cut_ranges or None,
            cover_timestamp=cover_ts,
            video_speed=video_speed,
            export_resolution=export_resolution,
        )

        meta_path = clips_dir / f"{safe_label}_meta.json"
        meta_path.write_text(
            json.dumps(
                build_clip_metadata(seg, result), ensure_ascii=False, indent=2
            )
        )

        return result
    except Exception:
        logger.exception("Failed to process clip %d: %s", idx, build_clip_basename(idx, ""))
        return None


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def process_clips(self, task_id: str, task_dir: str) -> dict[str, Any]:
    task_path = Path(task_dir)
    settings = _load_task_settings(task_path)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    try:
        enriched_file = task_path / "enriched_segments.json"
        if not enriched_file.exists():
            logger.error("No enriched segments found: %s", enriched_file)
            sm.transition("PROCESSING", "ERROR", message="No enriched segments found")
            return {"clips_count": 0, "output_dir": str(task_path / "clips")}

        segments = json.loads(enriched_file.read_text())
        if not segments:
            logger.warning("Empty segments for task %s", task_id)
            sm.transition("PROCESSING", "COMPLETED", step="completed")
            return {"clips_count": 0, "output_dir": str(task_path / "clips")}

        merge_count = getattr(settings, "merge_count", 1)
        if merge_count > 1:
            segments = _merge_segments(segments, merge_count)

        video_path = _find_video(task_path)
        if not video_path:
            logger.error("No video file found in %s", task_dir)
            sm.transition("PROCESSING", "ERROR", message="No video file found")
            return {"clips_count": 0, "output_dir": str(task_path / "clips")}

        clips_dir = task_path / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        srt_dir = task_path / "srt"
        srt_dir.mkdir(parents=True, exist_ok=True)
        covers_dir = task_path / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)

        transcript_file = task_path / "transcript.json"
        transcript = []
        if transcript_file.exists():
            transcript = json.loads(transcript_file.read_text())

        parallelism = calculate_parallelism()
        clip_workers = min(parallelism["clip_workers"], len(segments))

        processed: list[dict[str, Any]] = []
        if clip_workers > 1 and len(segments) > 1:
            logger.info("Processing %d clips with %d workers", len(segments), clip_workers)
            with ThreadPoolExecutor(max_workers=clip_workers) as executor:
                futures = {}
                for idx, seg in enumerate(segments):
                    future = executor.submit(
                        _process_single_clip,
                        idx, seg, video_path, clips_dir, srt_dir, covers_dir,
                        transcript, settings,
                    )
                    futures[future] = idx

                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result()
                        if result is not None:
                            processed.append(result)
                            logger.info(
                                "Processed clip %d/%d: %s",
                                idx + 1, len(segments), build_clip_basename(idx, ""),
                            )
                    except Exception:
                        logger.exception("Failed to process clip %d", idx)
        else:
            for idx, seg in enumerate(segments):
                result = _process_single_clip(
                    idx, seg, video_path, clips_dir, srt_dir, covers_dir,
                    transcript, settings,
                )
                if result is not None:
                    processed.append(result)
                    logger.info(
                        "Processed clip %d/%d: %s",
                        idx + 1, len(segments), build_clip_basename(idx, ""),
                    )

        sm.transition("PROCESSING", "COMPLETED", step="completed")

        return {
            "clips_count": len(processed),
            "output_dir": str(clips_dir),
        }
    except Exception as exc:
        err.handle_error("EXPORT_FAILED", str(exc), current_state="PROCESSING")
        raise self.retry(exc=exc, countdown=2**self.request.retries)
