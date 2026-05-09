import time
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from app.api.settings import SettingsRequest
from app.services.bgm_selector import BGMSelector, DEFAULT_BGM
from app.services.subtitle_overrides import (
    MAX_SUBTITLE_OVERRIDE_LINES,
    sanitize_subtitle_override_text,
)
from app.services.sensitive_filter import (
    compute_sensitive_cut_ranges,
    find_sensitive_hits,
    merge_cut_ranges,
    remove_sensitive_subtitle_segments,
)
from app.utils.json_io import write_json

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets"
DEFAULT_WATERMARK = str(ASSETS_DIR / "watermark.png")


def build_clip_basename(index: int, _product_name: str) -> str:
    """Return a stable ASCII-only basename for exported clip artifacts."""
    return f"clip_{index:03d}"


def build_clip_metadata(
    segment: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "product_name": segment.get("product_name", "未知商品"),
        "duration": result.get(
            "duration",
            float(segment.get("end_time", 0.0)) - float(segment.get("start_time", 0.0)),
        ),
        "start_time": segment.get("start_time", 0.0),
        "end_time": segment.get("end_time", 0.0),
        "confidence": segment.get("confidence", 0),
    }
    merged_count = segment.get("merged_from_count", 1)
    if merged_count > 1:
        meta["merged_from_count"] = merged_count
        if segment.get("sub_ranges"):
            meta["sub_ranges"] = segment["sub_ranges"]
        if segment.get("group_id"):
            meta["group_id"] = segment["group_id"]
    return meta


def _merge_segments(segments: list[dict[str, Any]], merge_count: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
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
    sub_ranges = segment.get("sub_ranges")
    merged_count = segment.get("merged_from_count", 1)

    if merged_count > 1 and sub_ranges:
        subtitle_segments: list[dict[str, Any]] = []
        timeline_offset = 0.0

        for sr in sub_ranges:
            sr_start = float(sr["start_time"])
            sr_end = float(sr["end_time"])
            sr_duration = sr_end - sr_start

            for item in transcript:
                if not isinstance(item, dict):
                    continue
                start = float(item.get("start_time", 0.0))
                end = float(item.get("end_time", 0.0))
                text = item.get("text", "").strip()
                if not text:
                    continue
                if start >= sr_end or end <= sr_start:
                    continue

                clipped_start = max(start, sr_start)
                clipped_end = min(end, sr_end)
                relative_start = timeline_offset + (clipped_start - sr_start)
                relative_end = timeline_offset + (clipped_end - sr_start)

                seg_entry: dict[str, Any] = {
                    "text": text,
                    "start_time": round(relative_start, 3),
                    "end_time": round(relative_end, 3),
                }

                words = item.get("words")
                if words and isinstance(words, list):
                    filtered_words = []
                    for w in words:
                        ws = float(w.get("begin_time", w.get("start_time", 0.0)))
                        we = float(w.get("end_time", 0.0))
                        if ws >= sr_end or we <= sr_start:
                            continue
                        ws = max(ws, sr_start)
                        we = min(we, sr_end)
                        filtered_words.append({
                            **w,
                            "begin_time": round(timeline_offset + (ws - sr_start), 3),
                            "end_time": round(timeline_offset + (we - sr_start), 3),
                        })
                    if filtered_words:
                        seg_entry["words"] = filtered_words

                seg_duration = seg_entry["end_time"] - seg_entry["start_time"]
                if seg_duration < 0.05 and not seg_entry.get("words"):
                    continue

                subtitle_segments.append(seg_entry)

            timeline_offset += sr_duration

        return subtitle_segments

    clip_start = float(segment.get("start_time", 0.0))
    clip_end = float(segment.get("end_time", 0.0))
    overrides = segment.get("subtitle_overrides")
    if isinstance(overrides, list) and overrides:
        subtitle_segments: list[dict[str, Any]] = []
        for item in overrides[:MAX_SUBTITLE_OVERRIDE_LINES]:
            if not isinstance(item, dict):
                continue
            try:
                start = float(item.get("start_time", 0.0))
                end = float(item.get("end_time", 0.0))
            except (TypeError, ValueError):
                continue
            text = sanitize_subtitle_override_text(item.get("text", ""))
            if not text or end <= start:
                continue
            relative_start = max(start, clip_start) - clip_start
            relative_end = min(end, clip_end) - clip_start
            if relative_end <= relative_start:
                continue
            subtitle_segments.append({
                "text": text,
                "start_time": relative_start,
                "end_time": relative_end,
            })
        if subtitle_segments:
            return subtitle_segments

    subtitle_segments: list[dict[str, Any]] = []

    for transcript_segment in transcript:
        transcript_start = float(transcript_segment.get("start_time", 0.0))
        transcript_end = float(transcript_segment.get("end_time", 0.0))
        if transcript_start > clip_end or transcript_end < clip_start:
            continue

        relative_start = max(transcript_start, clip_start) - clip_start
        relative_end = min(transcript_end, clip_end) - clip_start

        subtitle_segment: dict[str, Any] = {
            "text": "",
            "start_time": relative_start,
            "end_time": relative_end,
        }

        words = []
        for word in transcript_segment.get("words", []) or []:
            word_start = float(word.get("start_time", transcript_start))
            word_end = float(word.get("end_time", transcript_end))
            if word_start > clip_end or word_end < clip_start:
                continue
            rel_start = max(word_start, clip_start) - clip_start
            rel_end = min(word_end, clip_end) - clip_start
            if rel_end <= rel_start:
                continue
            words.append(
                {
                    "text": word.get("text", ""),
                    "start_time": rel_start,
                    "end_time": rel_end,
                    "probability": word.get("probability", 0.0),
                }
            )

        subtitle_segment["text"] = (
            "".join(w["text"] for w in words) if words else transcript_segment.get("text", "")
        )

        if words:
            subtitle_segment["words"] = words

        # 过滤零时长幽灵片段：边界对齐可能产生 start==end 的单字残留，
        # 会在 ASS Layer 0 产生与下一段重叠的 dialogue，导致字幕和跳动分两行
        seg_duration = subtitle_segment["end_time"] - subtitle_segment["start_time"]
        if seg_duration < 0.05 and not words:
            continue

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
    pre_sampled_frames: list[dict[str, Any]] | None = None,
    bgm_path: str | None = None,
) -> dict[str, Any] | None:
    """Process a single clip — designed for ProcessPoolExecutor (module-level for pickling)."""
    from app.tasks.pipeline import (
        SRTGenerator,
        FFmpegBuilder,
        select_cover_frame,
        filter_subtitle_words,
        compute_filler_cut_ranges,
    )

    try:
        clip_started_at = time.perf_counter()
        seg_label = seg.get("product_name", f"segment_{idx}")
        safe_label = build_clip_basename(idx, seg_label)

        output_path = str((clips_dir / f"{safe_label}.mp4").resolve())
        thumbnail_path = str((covers_dir / f"{safe_label}.jpg").resolve())

        subtitle_started_at = time.perf_counter()
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

        filler_cut_ranges: list[dict[str, object]] = []
        if filler_mode == "video":
            filler_cut_ranges = compute_filler_cut_ranges(sub_segments)

        sensitive_words = getattr(settings, "sensitive_words", [])
        sensitive_enabled = bool(getattr(settings, "sensitive_filter_enabled", False) and sensitive_words)
        sensitive_mode = getattr(settings, "sensitive_filter_mode", "video_segment")
        sensitive_mode_value = sensitive_mode.value if hasattr(sensitive_mode, "value") else str(sensitive_mode)
        sensitive_match_mode = getattr(settings, "sensitive_match_mode", "contains")
        sensitive_match_value = (
            sensitive_match_mode.value
            if hasattr(sensitive_match_mode, "value")
            else str(sensitive_match_mode)
        )
        sensitive_cut_ranges: list[dict[str, object]] = []
        if sensitive_enabled:
            hits = find_sensitive_hits(
                sub_segments,
                list(sensitive_words),
                match_mode=sensitive_match_value,
            )
            if hits and sensitive_mode_value == "drop_clip":
                logger.info(
                    "Skipping clip %s due to sensitive words: %s",
                    safe_label,
                    sorted({word for hit in hits for word in hit.get("matched_words", [])}),
                )
                return None
            sensitive_cut_ranges = compute_sensitive_cut_ranges(
                sub_segments,
                list(sensitive_words),
                match_mode=sensitive_match_value,
            )
            if sensitive_cut_ranges:
                sub_segments = remove_sensitive_subtitle_segments(
                    sub_segments,
                    list(sensitive_words),
                    match_mode=sensitive_match_value,
                )

        cut_ranges = merge_cut_ranges(
            filler_cut_ranges,
            sensitive_cut_ranges,
        )

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
                    subtitle_position=settings.subtitle_position.value,
                    custom_position_y=settings.custom_position_y,
                    font_size=getattr(settings, "subtitle_font_size", 45),
                    highlight_font_size=getattr(
                        settings,
                        "subtitle_highlight_font_size",
                        55,
                    ),
                )
            except Exception:
                logger.warning(
                    "Subtitle asset generation failed for %s, exporting without subtitles",
                    safe_label,
                    exc_info=True,
                )
                effective_subtitle_mode = "off"
        logger.info("Clip %s subtitle preparation finished in %.2fs", safe_label, time.perf_counter() - subtitle_started_at)

        cover_strategy = getattr(settings, "cover_strategy", "content_first")
        video_speed = getattr(settings, "video_speed", 1.0)
        export_resolution = getattr(settings, "export_resolution", "1080p")
        cover_started_at = time.perf_counter()
        cover_ts = select_cover_frame(
            video_path=str(video_path),
            clip_start=float(seg.get("start_time", 0.0)),
            clip_end=float(seg.get("end_time", 0.0)),
            strategy=cover_strategy,
            output_path=thumbnail_path,
            pre_sampled_frames=pre_sampled_frames,
        )
        thumbnail_precreated = Path(thumbnail_path).exists()
        logger.info("Clip %s cover selection finished in %.2fs", safe_label, time.perf_counter() - cover_started_at)

        ffmpeg = FFmpegBuilder()
        selected_bgm = bgm_path if bgm_path else DEFAULT_BGM
        export_started_at = time.perf_counter()

        is_merged = seg.get("merged_from_count", 1) > 1 and seg.get("sub_ranges")

        if is_merged:
            sub_ranges = seg["sub_ranges"]
            cmd = ffmpeg.build_cross_segment_concat_command(
                input_path=str(video_path),
                sub_ranges=sub_ranges,
                srt_path=clip_srt_path,
                bgm_path=selected_bgm,
                output_path=output_path,
                subtitle_position=settings.subtitle_position.value,
                subtitle_template=settings.subtitle_template.value,
                custom_position_y=settings.custom_position_y,
                video_speed=video_speed,
                export_resolution=export_resolution,
                bgm_enabled=getattr(settings, "bgm_enabled", True),
                bgm_volume=getattr(settings, "bgm_volume", 0.25),
                original_volume=getattr(settings, "original_volume", 1.0),
                ffmpeg_preset=getattr(settings, "ffmpeg_preset", "fast").value
                if hasattr(getattr(settings, "ffmpeg_preset", "fast"), "value")
                else getattr(settings, "ffmpeg_preset", "fast"),
                ffmpeg_crf=getattr(settings, "ffmpeg_crf", 23),
                subtitle_font_size=getattr(settings, "subtitle_font_size", 45),
            )
            logger.info("Cross-segment concat clip %s: %d sub-ranges", safe_label, len(sub_ranges))

            started_at = time.perf_counter()
            logger.info("Processing clip: %s → %s", str(video_path), output_path)
            cmd_result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if cmd_result.returncode != 0 and clip_srt_path:
                logger.warning(
                    "FFmpeg cross-segment concat failed with subtitles, retrying without: %s",
                    cmd_result.stderr[-500:] if cmd_result.stderr else "",
                )
                cmd = ffmpeg.build_cross_segment_concat_command(
                    input_path=str(video_path),
                    sub_ranges=sub_ranges,
                    srt_path=None,
                    bgm_path=selected_bgm,
                    output_path=output_path,
                    video_speed=video_speed,
                    export_resolution=export_resolution,
                    bgm_enabled=getattr(settings, "bgm_enabled", True),
                    bgm_volume=getattr(settings, "bgm_volume", 0.25),
                    original_volume=getattr(settings, "original_volume", 1.0),
                    ffmpeg_preset=getattr(settings, "ffmpeg_preset", "fast").value
                    if hasattr(getattr(settings, "ffmpeg_preset", "fast"), "value")
                    else getattr(settings, "ffmpeg_preset", "fast"),
                    ffmpeg_crf=getattr(settings, "ffmpeg_crf", 23),
                )
                cmd_result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if cmd_result.returncode != 0:
                logger.error(
                    "FFmpeg cross-segment concat failed: %s",
                    cmd_result.stderr[-500:] if cmd_result.stderr else "",
                )
                raise RuntimeError(f"FFmpeg cross-segment concat failed: {cmd_result.returncode}")

            logger.info("Cross-segment FFmpeg finished in %.2fs", time.perf_counter() - started_at)

            total_duration = sum(sr["end_time"] - sr["start_time"] for sr in sub_ranges)
            result = {
                "output_path": output_path,
                "thumbnail_path": thumbnail_path,
                "duration": total_duration / video_speed if video_speed != 1.0 else total_duration,
            }

            if thumbnail_precreated and Path(thumbnail_path).exists():
                logger.info("Thumbnail already exists, skipping extraction: %s", thumbnail_path)
            else:
                first_sr_start = sub_ranges[0]["start_time"]
                thumb_ts = cover_ts if cover_ts is not None else first_sr_start + 1.0
                thumb_cmd = ffmpeg.build_thumbnail_command(
                    str(video_path), thumb_ts, thumbnail_path,
                )
                thumb_result = subprocess.run(thumb_cmd, capture_output=True, text=True, timeout=60)
                if thumb_result.returncode != 0:
                    logger.warning(
                        "Thumbnail extraction failed: %s",
                        thumb_result.stderr[-300:] if thumb_result.stderr else "",
                    )
        else:
            result = ffmpeg.process_clip(
                input_path=str(video_path),
                segment=seg,
                srt_path=clip_srt_path,
                bgm_path=selected_bgm,
                watermark_path=DEFAULT_WATERMARK,
                output_path=output_path,
                thumbnail_path=thumbnail_path,
                subtitle_mode=effective_subtitle_mode,
                subtitle_position=settings.subtitle_position.value,
                subtitle_template=settings.subtitle_template.value,
                custom_position_y=settings.custom_position_y,
                filler_cut_ranges=cut_ranges or None,
                cover_timestamp=cover_ts,
                video_speed=video_speed,
                export_resolution=export_resolution,
                bgm_enabled=getattr(settings, "bgm_enabled", True),
                bgm_volume=getattr(settings, "bgm_volume", 0.25),
                original_volume=getattr(settings, "original_volume", 1.0),
                thumbnail_precreated=thumbnail_precreated,
                ffmpeg_preset=getattr(settings, "ffmpeg_preset", "fast").value
                if hasattr(getattr(settings, "ffmpeg_preset", "fast"), "value")
                else getattr(settings, "ffmpeg_preset", "fast"),
                ffmpeg_crf=getattr(settings, "ffmpeg_crf", 23),
                subtitle_font_size=getattr(settings, "subtitle_font_size", 45),
            )
        logger.info("Clip %s FFmpeg export finished in %.2fs", safe_label, time.perf_counter() - export_started_at)

        meta_path = clips_dir / f"{safe_label}_meta.json"
        write_json(meta_path, build_clip_metadata(seg, result))

        logger.info("Clip %s total processing finished in %.2fs", safe_label, time.perf_counter() - clip_started_at)
        return result
    except Exception:
        logger.exception("Failed to process clip %d: %s", idx, build_clip_basename(idx, ""))
        return None


def run_process_clips(task_id: str, task_dir: str) -> dict[str, Any]:
    from app.tasks.pipeline import (
        TaskStateMachine,
        PipelineErrorHandler,
        TempFileCleaner,
        SRTGenerator,
        FFmpegBuilder,
        calculate_parallelism,
        _load_task_settings,
        _read_json_file,
        _log_elapsed,
        _find_video,
    )

    task_path = Path(task_dir)
    settings = _load_task_settings(task_path)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)
    cleaner = TempFileCleaner()

    process_started_at = time.perf_counter()
    enriched_file = task_path / "enriched_segments.json"
    if not enriched_file.exists():
        logger.error("No enriched segments found: %s", enriched_file)
        sm.transition("PROCESSING", "ERROR", message="No enriched segments found")
        return {"clips_count": 0, "output_dir": str(task_path / "clips")}

    segments = _read_json_file(enriched_file, [])
    if not isinstance(segments, list):
        logger.error("Invalid enriched_segments.json format: %s", enriched_file)
        sm.transition("PROCESSING", "ERROR", message="Invalid enriched_segments.json format")
        return {"clips_count": 0, "output_dir": str(task_path / "clips")}
    if not segments:
        logger.warning("Empty segments for task %s", task_id)
        sm.transition("PROCESSING", "COMPLETED", step="completed")
        return {"clips_count": 0, "output_dir": str(task_path / "clips")}

    # Filter out segments where person is not present (empty screen)
    # Two-layer filter:
    #   1. Overall person presence ratio must be >= 60%
    #   2. No person-absent gap >= 8s at segment start
    PERSON_OVERALL_THRESHOLD = 0.6
    PERSON_START_GAP_SECONDS = 8.0
    # person_presence.json is written to scenes/ subdir by ClothingChangeDetector
    person_presence_file = task_path / "scenes" / "person_presence.json"
    if person_presence_file.exists():
        person_presence = _read_json_file(person_presence_file, [])
        if not isinstance(person_presence, list):
            person_presence = []
        if person_presence:
            filtered_segments = []
            for seg in segments:
                seg_start = seg.get("start_time", 0.0)
                seg_end = seg.get("end_time", 0.0)
                frames_in_seg = [
                    p for p in person_presence
                    if seg_start <= p["timestamp"] <= seg_end
                ]
                if frames_in_seg:
                    person_ratio = sum(
                        1 for p in frames_in_seg if p.get("person_present", True)
                    ) / len(frames_in_seg)
                else:
                    person_ratio = 1.0  # no frame data → keep

                # Layer 1: overall presence threshold
                if person_ratio < PERSON_OVERALL_THRESHOLD:
                    logger.info(
                        "Skipping segment '%s' (%.1fs-%.1fs): person present in only %.0f%% of frames (threshold %.0f%%)",
                        seg.get("product_name", ""),
                        seg_start, seg_end, person_ratio * 100,
                        PERSON_OVERALL_THRESHOLD * 100,
                    )
                    continue

                # Layer 2: check for consecutive person-absent gap at segment start
                # Find the first frame with person present
                first_present_ts = None
                for p in frames_in_seg:
                    if p.get("person_present", False):
                        first_present_ts = p["timestamp"]
                        break
                if first_present_ts is not None:
                    start_gap = first_present_ts - seg_start
                    if start_gap >= PERSON_START_GAP_SECONDS:
                        logger.info(
                            "Skipping segment '%s' (%.1fs-%.1fs): no person for first %.1fs (threshold %.1fs)",
                            seg.get("product_name", ""),
                            seg_start, seg_end, start_gap,
                            PERSON_START_GAP_SECONDS,
                        )
                        continue
                elif not frames_in_seg:
                    pass  # no frame data → keep (handled above)
                else:
                    # All frames show no person → already caught by layer 1
                    continue

                filtered_segments.append(seg)
            skipped = len(segments) - len(filtered_segments)
            if skipped > 0:
                logger.info("Person presence filter: %d/%d segments kept (%d empty-screen segments dropped)",
                            len(filtered_segments), len(segments), skipped)
            segments = filtered_segments
    else:
        logger.debug("No person_presence.json found, skipping person presence filter")

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
        transcript = _read_json_file(transcript_file, [])
        if not isinstance(transcript, list):
            transcript = []

    pre_sampled_frames: list[dict[str, Any]] = []
    frames_index = task_path / "frames" / "frames.json"
    if frames_index.exists():
        pre_sampled_frames = _read_json_file(frames_index, [])
        if not isinstance(pre_sampled_frames, list):
            pre_sampled_frames = []
        logger.info("Loaded %d pre-sampled frames for cover selection", len(pre_sampled_frames))

    parallelism = calculate_parallelism()
    clip_workers = int(min(parallelism["clip_workers"], len(segments)))

    bgm_enabled = getattr(settings, "bgm_enabled", True)
    bgm_map: dict[int, str] = {}
    if bgm_enabled:
        bgm_selector = BGMSelector.with_user_library(ASSETS_DIR / "bgm" / "bgm_library.json")
        used_bgm_ids: set[str] = set()
        for idx, seg in enumerate(segments):
            selected = bgm_selector.select_for_segment(seg, used_bgm_ids)
            bgm_map[idx] = selected

    processed: list[dict[str, Any]] = []
    if clip_workers > 1 and len(segments) > 1:
        logger.info("Processing %d clips with %d workers", len(segments), clip_workers)
        with ThreadPoolExecutor(max_workers=clip_workers) as executor:
            futures = {}
            for idx, seg in enumerate(segments):
                future = executor.submit(
                    _process_single_clip,
                    idx, seg, video_path, clips_dir, srt_dir, covers_dir,
                    transcript, settings, pre_sampled_frames, bgm_map.get(idx),
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
                transcript, settings, pre_sampled_frames, bgm_map.get(idx),
            )
            if result is not None:
                processed.append(result)
                logger.info(
                    "Processed clip %d/%d: %s",
                    idx + 1, len(segments), build_clip_basename(idx, ""),
                )

    sm.transition("PROCESSING", "COMPLETED", step="completed")
    _log_elapsed("process_clips", process_started_at)
    cleaner.cleanup_frames(task_dir)

    return {
        "clips_count": len(processed),
        "output_dir": str(clips_dir),
    }
