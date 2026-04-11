"""VLM confirmation orchestrator — confirms candidate segments via Qwen-VL-Plus."""

import json
import logging
from pathlib import Path

from app.services.vlm_client import VLMClient
from app.services.vlm_parser import VLMResponseParser

logger = logging.getLogger(__name__)


class VLMConfirmor:
    """Orchestrates VLM confirmation of candidate segments.

    For each candidate segment, compares first and last frame via VLM.
    Only keeps segments where is_different=true.
    """

    PROMPT_TEMPLATE = """你是一位专业的服装商品分析师。请仔细对比这两张直播截图，从以下5个维度判断是否展示了不同的服装商品：

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

    def __init__(self, vlm_client: VLMClient):
        self.client = vlm_client
        self.parser = VLMResponseParser()

    def confirm_candidates(
        self, candidates: list[dict], frames_dir: str, task_id: str = ""
    ) -> list[dict]:
        """For each candidate segment, compare first and last frame via VLM.

        Only keeps segments where is_different=true.
        Returns confirmed segments with product info.
        """
        confirmed = []

        for candidate in candidates:
            try:
                frame1, frame2 = self._get_key_frames(candidate, frames_dir)
            except (FileNotFoundError, KeyError):
                logger.warning("Missing frames for candidate, skipping")
                continue

            try:
                raw_response = self.client.compare_frames(
                    frame1, frame2, self.PROMPT_TEMPLATE
                )
            except RuntimeError as e:
                logger.error("VLM call failed for candidate: %s", e)
                continue

            parsed = self.parser.parse(raw_response)

            if not parsed.get("is_different", False):
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

    def _get_key_frames(self, candidate: dict, frames_dir: str) -> tuple[str, str]:
        """Get first and last frame paths for a candidate segment."""
        frames_path = Path(frames_dir)
        frame_idx = candidate.get("frame_idx", 0)

        # Look for frames in scene subdirectories
        scene_dirs = sorted(frames_path.glob("scene*"))
        if not scene_dirs:
            # Flat frame directory
            all_frames = sorted(frames_path.glob("frame_*.jpg"))
            if len(all_frames) < 2:
                raise FileNotFoundError(f"Not enough frames in {frames_dir}")
            first_idx = max(0, frame_idx - 1)
            last_idx = min(len(all_frames) - 1, frame_idx)
            return str(all_frames[first_idx]), str(all_frames[last_idx])

        # Scene-based: find frames in scene directories
        all_frames = []
        for scene_dir in scene_dirs:
            all_frames.extend(sorted(scene_dir.glob("frame_*.jpg")))

        if not all_frames:
            raise FileNotFoundError(f"No frames found in {frames_dir}")

        first_idx = max(0, frame_idx - 1)
        last_idx = min(len(all_frames) - 1, frame_idx)
        return str(all_frames[first_idx]), str(all_frames[last_idx])

    def _save_results(self, confirmed: list[dict], task_id: str) -> None:
        """Save confirmed segments to JSON file."""
        from app.services.state_machine import TaskStateMachine

        # Determine task_dir from task_id (convention: uploads/{task_id})
        task_dir = Path("uploads") / task_id
        vlm_dir = task_dir / "vlm"
        vlm_dir.mkdir(parents=True, exist_ok=True)

        output_file = vlm_dir / "confirmed_segments.json"
        output_file.write_text(json.dumps(confirmed, ensure_ascii=False, indent=2))
        logger.info("Saved %d confirmed segments to %s", len(confirmed), output_file)
