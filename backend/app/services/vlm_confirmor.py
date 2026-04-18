# pyright: reportImplicitRelativeImport=false, reportExplicitAny=false
"""VLM confirmation orchestrator — confirms candidate segments via Qwen-VL-Plus."""

import json
import logging
from pathlib import Path
from typing import Any

from app.services.vlm_client import VLMClient
from app.services.vlm_parser import VLMResponseParser

logger = logging.getLogger(__name__)


class VLMConfirmor:
    """Orchestrates VLM confirmation of candidate segments.

    For each candidate segment, compares first and last frame via VLM.
    Only keeps segments where is_different=true.
    """

    PROMPT_TEMPLATE: str = """你是一位专业的服装商品分析师。请仔细对比这两张直播截图，从以下5个维度判断是否展示了不同的服装商品：

1. 服装类型：上衣/裙子/裤子/外套/配饰/无服装展示
2. 主色调：主要颜色（红/黑/白/蓝/绿/粉/黄/灰/棕/多色）
3. 图案纹理：纯色/条纹/碎花/格子/印花/刺绣/无
4. 版型剪裁：修身/宽松/A字/直筒/oversize/无
5. 穿着方式：单穿/叠搭/配饰变化/模特展示/无

请严格按以下JSON格式回复（不要添加任何其他文字）：
{
  "is_different": true或false,
  "confidence": 0.0到1.0的置信度,
  "dimensions": {
    "type": {"same": true/false, "value_1": "...", "value_2": "..."},
    "color": {"same": true/false, "value_1": "...", "value_2": "..."},
    "pattern": {"same": true/false, "value_1": "...", "value_2": "..."},
    "cut": {"same": true/false, "value_1": "...", "value_2": "..."},
    "wear": {"same": true/false, "value_1": "...", "value_2": "..."}
  },
  "product_1": {"type": "服装类型", "color": "颜色", "style": "款式描述"},
  "product_2": {"type": "服装类型", "color": "颜色", "style": "款式描述"}
}

判断规则：
- 如果两张图中是同一件衣服（仅角度/姿态不同），is_different=false
- 如果图中没有服装展示（只有人脸/空镜头），is_different=false
- 只有确实换了不同商品时才设为true"""

    REVIEW_CONFIDENCE_THRESHOLDS: dict[str, float] = {
        "strict": 0.7,
        "standard": 0.6,
        "loose": 0.5,
    }

    def __init__(self, vlm_client: VLMClient):
        self.client: VLMClient = vlm_client
        self.parser: VLMResponseParser = VLMResponseParser()

    def confirm_candidates(
        self,
        candidates: list[dict[str, Any]],
        frames_dir: str,
        task_id: str = "",
        review_mode: str = "adjacent_frames",
        review_strictness: str = "standard",
    ) -> list[dict[str, Any]]:
        """For each candidate segment, compare first and last frame via VLM.

        Only keeps segments where is_different=true.
        Returns confirmed segments with product info.
        """
        confirmed = []
        frame_records = self._load_frame_records(frames_dir)
        confidence_threshold = self.REVIEW_CONFIDENCE_THRESHOLDS.get(
            review_strictness, self.REVIEW_CONFIDENCE_THRESHOLDS["standard"]
        )

        for candidate in candidates:
            try:
                raw_response = self._review_candidate(
                    candidate=candidate,
                    frames_dir=frames_dir,
                    frame_records=frame_records,
                    review_mode=review_mode,
                )
            except (FileNotFoundError, KeyError):
                logger.warning("Missing frames for candidate, skipping")
                continue
            except RuntimeError as e:
                logger.error("VLM call failed for candidate: %s", e)
                continue

            try:
                parsed = self.parser.parse(raw_response)
            except Exception as e:
                logger.error("Failed to parse VLM response for candidate: %s", e)
                continue

            if not parsed.get("is_different", False):
                continue

            if float(parsed.get("confidence", 0.0)) < confidence_threshold:
                continue

            product_info = parsed.get("product_2", {})
            if not product_info:
                product_info = parsed.get("product_1", {})

            confirmed.append(
                {
                    "start_time": candidate.get("timestamp", 0.0),
                    "end_time": candidate.get(
                        "end_time", candidate.get("timestamp", 0.0)
                    ),
                    "confidence": parsed.get("confidence", 0.0),
                    "product_info": {
                        "type": product_info.get("type", ""),
                        "color": product_info.get("color", ""),
                        "style": product_info.get("style", ""),
                        "description": f"{product_info.get('type', '')} {product_info.get('color', '')} {product_info.get('style', '')}".strip(),
                    },
                    "low_confidence": parsed.get("low_confidence", True),
                }
            )

        if task_id:
            self._save_results(confirmed, task_id)

        return confirmed

    def _review_candidate(
        self,
        candidate: dict[str, Any],
        frames_dir: str,
        frame_records: list[dict[str, Any]],
        review_mode: str,
    ) -> str:
        if review_mode == "segment_multiframe":
            frame_paths = self._get_segment_multiframe_paths(candidate, frame_records)
            if frame_paths is not None:
                return self.client.compare_frames_multi(
                    frame_paths, self.PROMPT_TEMPLATE
                )

            logger.info(
                "Candidate missing usable segment boundaries for multiframe review, falling back to adjacent frames"
            )

        frame1, frame2 = self._get_key_frames(candidate, frames_dir, frame_records)
        return self.client.compare_frames(frame1, frame2, self.PROMPT_TEMPLATE)

    def _get_key_frames(
        self,
        candidate: dict[str, Any],
        frames_dir: str,
        frame_records: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Get first and last frame paths for a candidate segment."""
        all_frames = frame_records or self._load_frame_records(frames_dir)
        frame_idx = candidate.get("frame_idx", 0)
        if not all_frames:
            raise FileNotFoundError(f"No frames found in {frames_dir}")

        first_idx = max(0, frame_idx - 1)
        last_idx = min(len(all_frames) - 1, frame_idx)
        return str(all_frames[first_idx]["path"]), str(all_frames[last_idx]["path"])

    def _get_segment_multiframe_paths(
        self, candidate: dict[str, Any], frame_records: list[dict[str, Any]]
    ) -> list[str] | None:
        start_time = candidate.get("start_time")
        end_time = candidate.get("end_time")
        if start_time is None or end_time is None or end_time <= start_time:
            return None

        segment_frames = [
            frame
            for frame in frame_records
            if start_time <= float(frame["timestamp"]) <= end_time
        ]
        if len(segment_frames) < 3:
            return None

        midpoint = start_time + ((end_time - start_time) / 2)
        targets = [start_time, midpoint, end_time]
        selected_paths: list[str] = []
        used_paths: set[str] = set()

        for target in targets:
            closest = min(
                segment_frames,
                key=lambda frame: abs(float(frame["timestamp"]) - float(target)),
            )
            frame_path = str(closest["path"])
            if frame_path in used_paths:
                return None
            used_paths.add(frame_path)
            selected_paths.append(frame_path)

        return selected_paths

    def _load_frame_records(self, frames_dir: str) -> list[dict[str, Any]]:
        frames_path = Path(frames_dir)
        frames_json = frames_path / "frames.json"
        if frames_json.exists():
            records = json.loads(frames_json.read_text())
            return sorted(records, key=lambda frame: float(frame.get("timestamp", 0.0)))

        all_frames: list[dict[str, Any]] = []
        scene_dirs = sorted(frames_path.glob("scene*"))
        if not scene_dirs:
            scene_dirs = [frames_path]

        index = 0
        for scene_dir in scene_dirs:
            for jpg in sorted(scene_dir.glob("frame_*.jpg")):
                all_frames.append(
                    {
                        "path": str(jpg),
                        "timestamp": float(index),
                    }
                )
                index += 1

        return all_frames

    def _save_results(self, confirmed: list[dict[str, Any]], task_id: str) -> None:
        """Save confirmed segments to JSON file."""
        # Determine task_dir from task_id (convention: uploads/{task_id})
        task_dir = Path("uploads") / task_id
        vlm_dir = task_dir / "vlm"
        vlm_dir.mkdir(parents=True, exist_ok=True)

        output_file = vlm_dir / "confirmed_segments.json"
        output_file.write_text(json.dumps(confirmed, ensure_ascii=False, indent=2))
        logger.info("Saved %d confirmed segments to %s", len(confirmed), output_file)
