import os
import time
import logging
from pathlib import Path
from typing import Any
from collections.abc import Sequence

from app.utils.json_io import write_json

logger = logging.getLogger(__name__)


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


def _do_transcribe(
    task_path: Path,
    settings: Any,
    video_path: Path,
    *,
    context: str,
) -> list[dict[str, Any]]:
    from app.tasks.pipeline import (
        AuthError,
        TranscriptionError,
        _create_asr_client,
        _need_asr,
    )

    if not _need_asr(settings):
        logger.info("ASR skipped (subtitles off, LLM off, %s path)", context)
        transcript: list[dict[str, Any]] = []
    else:
        asr_client = _create_asr_client(settings)
        try:
            transcript = asr_client.transcribe(str(video_path))
        except AuthError as e:
            logger.warning("ASR auth failed [%s]: %s, continuing without transcript", e.provider, e)
            transcript = []
        except TranscriptionError as e:
            logger.error("ASR transcription failed [%s]: %s", e.provider, e)
            raise

    transcript_file = task_path / "transcript.json"
    write_json(transcript_file, transcript)
    return transcript


def run_enrich_segments(
    task_id: str,
    task_dir: str,
) -> dict[str, Any]:
    from app.tasks.pipeline import (
        TaskStateMachine,
        PipelineErrorHandler,
        TempFileCleaner,
        ProductNameMatcher,
        SegmentValidator,
        TextSegmentAnalyzer,
        fuse_candidates,
        fused_to_segments,
        _load_task_settings,
        _log_elapsed,
        _get_video_duration,
        _find_video,
        _need_asr,
        _read_json_file,
    )
    from app.tasks.stages.vlm_confirm import _build_export_segments_from_candidates

    task_path = Path(task_dir)
    settings = _load_task_settings(task_path)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    enrich_started_at = time.perf_counter()
    sm.transition("VLM_CONFIRMING", "TRANSCRIBING", step="transcribing")

    export_mode = settings.export_mode.value

    if export_mode == "all_candidates":
        candidates_file = task_path / "candidates.json"
        if not candidates_file.exists():
            logger.error("No candidates found: %s", candidates_file)
            return {"segments_count": 0, "validated_count": 0}

        candidates = _read_json_file(candidates_file, [])
        if not isinstance(candidates, list):
            candidates = []
        video_path = _find_video(task_path)
        if not video_path:
            logger.error("No video file found in %s", task_dir)
            return {"segments_count": len(candidates), "validated_count": 0}

        transcript = _do_transcribe(task_path, settings, video_path, context="all_candidates")

        export_segments = _attach_transcript_text(
            _build_export_segments_from_candidates(candidates), transcript
        )
        output_file = task_path / "enriched_segments.json"
        write_json(output_file, export_segments)
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

        scenes = _read_json_file(scenes_file, [])
        if not isinstance(scenes, list):
            scenes = []
        video_path = _find_video(task_path)
        if not video_path:
            logger.error("No video file found in %s", task_dir)
            return {"segments_count": len(scenes), "validated_count": 0}

        transcript = _do_transcribe(task_path, settings, video_path, context="all_scenes")

        export_segments = _attach_transcript_text(
            _build_export_segments_from_scenes(scenes), transcript
        )
        output_file = task_path / "enriched_segments.json"
        write_json(output_file, export_segments)
        sm.transition("TRANSCRIBING", "PROCESSING", step="processing")
        return {
            "segments_count": len(export_segments),
            "validated_count": len(export_segments),
        }

    confirmed_file = task_path / "vlm" / "confirmed_segments.json"
    if not confirmed_file.exists():
        logger.error("No confirmed segments found: %s", confirmed_file)
        return {"segments_count": 0, "validated_count": 0}

    segments = _read_json_file(confirmed_file, [])
    if not isinstance(segments, list):
        segments = []

    video_path = _find_video(task_path)
    if not video_path:
        logger.error("No video file found in %s", task_dir)
        return {"segments_count": len(segments), "validated_count": 0}

    transcript = _do_transcribe(task_path, settings, video_path, context=export_mode)
    _log_elapsed("enrich_segments.transcribe", enrich_started_at)

    cleaner.cleanup_chunks(task_dir)

    if _need_asr(settings) and settings.enable_llm_analysis:
        llm_key = settings.llm_api_key or os.getenv("LLM_API_KEY", "")
        llm_base = settings.llm_api_base or os.getenv("LLM_API_BASE", "")
        llm_model = settings.llm_model or os.getenv("LLM_MODEL", "")
        llm_type = (settings.llm_type.value if hasattr(settings.llm_type, "value") else settings.llm_type) or os.getenv("LLM_TYPE", "openai")
        if llm_key and llm_base and llm_model:
            try:
                sm.transition("TRANSCRIBING", "LLM_ANALYZING", step="llm_analysis")
                analyzer = TextSegmentAnalyzer(
                    api_key=llm_key,
                    api_base=llm_base,
                    model=llm_model,
                    llm_type=llm_type,
                )
                granularity = getattr(settings, "segment_granularity", "single_item")
                granularity = granularity.value if hasattr(granularity, "value") else granularity
                llm_started_at = time.perf_counter()
                text_boundaries = analyzer.analyze(transcript, segment_granularity=granularity)
                _log_elapsed("enrich_segments.llm_analysis", llm_started_at)
                logger.info("LLM text analysis found %d boundaries", len(text_boundaries))

                text_boundaries_file = task_path / "text_boundaries.json"
                write_json(text_boundaries_file, text_boundaries)

                candidates_file = task_path / "candidates.json"
                visual_candidates = _read_json_file(candidates_file, []) if candidates_file.exists() else []
                if not isinstance(visual_candidates, list):
                    visual_candidates = []
                video_duration = _get_video_duration(str(video_path))

                fused = fuse_candidates(visual_candidates, text_boundaries, video_duration, segment_granularity=granularity)
                fused_file = task_path / "fused_candidates.json"
                write_json(fused_file, fused)

                logger.info("Fused %d visual + %d text → %d candidates", len(visual_candidates), len(text_boundaries), len(fused))

                if fused:
                    segments = fused_to_segments(fused, video_duration)
                    logger.info("Using %d fused segments (replacing VLM segments)", len(segments))

                sm.transition("LLM_ANALYZING", "TRANSCRIBING", step="transcribing")
            except Exception as e:
                logger.warning("LLM text analysis failed, continuing without it: %s", str(e))

    # Snap segment boundaries to transcript sentence boundaries
    if transcript and getattr(settings, "boundary_snap", True):
        from app.services.boundary_snapper import snap_to_sentence_boundaries
        segments = snap_to_sentence_boundaries(
            segments, transcript,
            min_duration=float(settings.min_segment_duration_seconds),
        )

    # LLM boundary refinement (review and adjust boundaries for narrative quality)
    if transcript and getattr(settings, "enable_boundary_refinement", False):
        llm_key = settings.llm_api_key or os.getenv("LLM_API_KEY", "")
        llm_base = settings.llm_api_base or os.getenv("LLM_API_BASE", "")
        llm_model = settings.llm_model or os.getenv("LLM_MODEL", "")
        llm_type = str(getattr(settings, "llm_type", "openai"))

        if llm_key:
            from app.services.boundary_refiner import refine_boundaries
            segments = refine_boundaries(
                segments, transcript,
                llm_key=llm_key, llm_base=llm_base, llm_model=llm_model,
                llm_type=llm_type,
                min_duration=float(settings.min_segment_duration_seconds),
            )
        else:
            logger.warning("LLM boundary refinement enabled but no API key configured, skipping")

    enrich_post_started_at = time.perf_counter()
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
    write_json(output_file, validated)
    _log_elapsed("enrich_segments.postprocess", enrich_post_started_at)

    sm.transition("TRANSCRIBING", "PROCESSING", step="processing")

    return {
        "segments_count": len(segments),
        "validated_count": len(validated),
    }
