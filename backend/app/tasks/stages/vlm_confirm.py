import json
import time
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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


def _write_confirmed_segments(
    task_path: Path, confirmed_segments: list[dict[str, Any]]
) -> None:
    vlm_dir = task_path / "vlm"
    vlm_dir.mkdir(parents=True, exist_ok=True)
    output_file = vlm_dir / "confirmed_segments.json"
    output_file.write_text(json.dumps(confirmed_segments, ensure_ascii=False, indent=2))


def run_vlm_confirm(
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
    from app.tasks.pipeline import (
        TaskStateMachine,
        PipelineErrorHandler,
        VLMClient,
        VLMConfirmor,
        _log_elapsed,
    )

    task_path = Path(task_dir)
    sm = TaskStateMachine(task_dir=task_path)
    err = PipelineErrorHandler(task_dir=task_path)

    stage_started_at = time.perf_counter()
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
    _log_elapsed("vlm_confirm.confirm_candidates", stage_started_at)

    return {
        "confirmed_count": len(confirmed),
        "total_candidates": len(candidates),
    }
