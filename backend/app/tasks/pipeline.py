# pyright: reportImplicitRelativeImport=false, reportAttributeAccessIssue=false

import json
import logging
import os
from pathlib import Path
from typing import Any, cast

from celery import Celery, chain

from app.api.settings import SettingsRequest
from app.services.adaptive_similarity import AdaptiveSimilarityAnalyzer
from app.services.cleanup import TempFileCleaner
from app.services.error_handler import PipelineErrorHandler
from app.services.ffmpeg_builder import FFmpegBuilder
from app.services.frame_extractor import FrameExtractor
from app.services.faster_whisper_client import FasterWhisperClient
from app.services.product_matcher import ProductNameMatcher
from app.services.scene_detector import SceneDetector
from app.services.segment_validator import SegmentValidator
from app.services.siglip_encoder import FashionSigLIPEncoder
from app.services.srt_generator import SRTGenerator
from app.services.state_machine import TaskStateMachine
from app.services.vlm_client import VLMClient
from app.services.vlm_confirmor import VLMConfirmor

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "clipper",
    broker=REDIS_URL,
    backend=REDIS_URL,
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
            settings.api_base,
            settings.model,
            settings.review_mode.value,
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
        state = sm.transition("UPLOADED", "EXTRACTING_FRAMES", step="extracting_frames")

        detector = SceneDetector()
        scenes = detector.detect(
            video_path,
            output_dir=str(task_path / "scenes"),
            threshold=settings.scene_threshold,
        )
        state = sm.transition(
            "EXTRACTING_FRAMES", "SCENE_DETECTING", step="scene_detecting"
        )

        extractor = FrameExtractor()
        frames = extractor.extract(
            video_path,
            scenes,
            output_dir=str(task_path / "frames"),
            sample_fps=settings.frame_sample_fps,
        )
        state = sm.transition(
            "SCENE_DETECTING", "VISUAL_SCREENING", step="visual_screening"
        )

        encoder = FashionSigLIPEncoder()
        frame_paths = [str(f["path"]) for f in frames]
        embeddings = encoder.encode_batch(frame_paths)

        timestamps = [float(f["timestamp"]) for f in frames]
        analyzer = AdaptiveSimilarityAnalyzer()
        candidates = analyzer.analyze(
            embeddings,
            timestamps,
            cooldown_seconds=float(settings.recall_cooldown_seconds),
            candidate_looseness=settings.candidate_looseness.value,
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
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: str = "qwen-vl-plus",
    review_mode: str = "segment_multiframe",
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

        client = VLMClient(api_key=api_key, base_url=base_url, model=model)
        confirmor = VLMConfirmor(vlm_client=client)
        confirmed = confirmor.confirm_candidates(
            candidates, frames_dir, task_id=task_id, review_mode=review_mode
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
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    try:
        sm.transition("VLM_CONFIRMING", "TRANSCRIBING", step="transcribing")

        confirmed_file = task_path / "vlm" / "confirmed_segments.json"
        if not confirmed_file.exists():
            logger.error("No confirmed segments found: %s", confirmed_file)
            return {"segments_count": 0, "validated_count": 0}

        segments = json.loads(confirmed_file.read_text())

        video_path = _find_video(task_path)
        if not video_path:
            logger.error("No video file found in %s", task_dir)
            return {"segments_count": len(segments), "validated_count": 0}

        asr_client = FasterWhisperClient()
        transcript = asr_client.transcribe(str(video_path))

        transcript_file = task_path / "transcript.json"
        transcript_file.write_text(json.dumps(transcript, ensure_ascii=False, indent=2))

        cleaner.cleanup_chunks(task_dir)

        matcher = ProductNameMatcher()
        enriched = matcher.match(segments, transcript)

        video_duration = _get_video_duration(str(video_path))

        validator = SegmentValidator()
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

        video_path = _find_video(task_path)
        if not video_path:
            logger.error("No video file found in %s", task_dir)
            sm.transition("PROCESSING", "ERROR", message="No video file found")
            return {"clips_count": 0, "output_dir": str(task_path / "clips")}

        clips_dir = task_path / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        srt_dir = task_path / "srt"
        srt_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir = task_path / "thumbnails"
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        srt_gen = SRTGenerator()
        ffmpeg = FFmpegBuilder()

        processed = []
        for idx, seg in enumerate(segments):
            seg_label = seg.get("product_name", f"segment_{idx}")
            safe_label = build_clip_basename(idx, seg_label)

            srt_path = str((srt_dir / f"{safe_label}.srt").resolve())
            output_path = str((clips_dir / f"{safe_label}.mp4").resolve())
            thumbnail_path = str((thumbs_dir / f"{safe_label}.jpg").resolve())

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
            srt_gen.generate(sub_segments, srt_path)

            try:
                result = ffmpeg.process_clip(
                    input_path=str(video_path),
                    segment=seg,
                    srt_path=srt_path,
                    bgm_path=DEFAULT_BGM,
                    watermark_path=DEFAULT_WATERMARK,
                    output_path=output_path,
                    thumbnail_path=thumbnail_path,
                )
                processed.append(result)
                logger.info(
                    "Processed clip %d/%d: %s", idx + 1, len(segments), safe_label
                )
            except Exception:
                logger.exception("Failed to process clip %d: %s", idx, safe_label)

        cleaner.cleanup_srt(task_dir)

        sm.transition("PROCESSING", "COMPLETED", step="completed")

        return {
            "clips_count": len(processed),
            "output_dir": str(clips_dir),
        }
    except Exception as exc:
        err.handle_error("EXPORT_FAILED", str(exc), current_state="PROCESSING")
        raise self.retry(exc=exc, countdown=2**self.request.retries)
