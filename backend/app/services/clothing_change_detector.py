"""Clothing change detector — MediaPipe mask + YOLO categories + HSV histogram.

Detects "clothing change" moments in livestream videos using three signals:
1. YOLO fashionpedia category change (different garment types detected)
2. MediaPipe clothes-mask HSV histogram correlation drop
3. Fallback to whole-frame HSV if models unavailable

The public interface is unchanged: detect_from_frames() and
detect_scenes_from_candidates() have the same signatures and return formats.
"""

import json
import logging
from pathlib import Path

import cv2
import numpy as np

from .clothing_segmenter import ClothingSegmenter

logger = logging.getLogger(__name__)


class ClothingChangeDetector:
    """Detects clothing changes via combined MediaPipe mask + YOLO + HSV."""

    DEFAULT_HIST_THRESHOLD: float = 0.90
    DEFAULT_MIN_SCENE_GAP: float = 15.0
    DEFAULT_MERGE_WINDOW: float = 16.0

    def __init__(
        self,
        hist_threshold: float | None = None,
        min_scene_gap: float | None = None,
        merge_window: float | None = None,
    ) -> None:
        self.hist_threshold = hist_threshold or self.DEFAULT_HIST_THRESHOLD
        self.min_scene_gap = min_scene_gap or self.DEFAULT_MIN_SCENE_GAP
        self.merge_window = merge_window or self.DEFAULT_MERGE_WINDOW
        self._segmenter: ClothingSegmenter | None = None

    def _get_segmenter(self) -> ClothingSegmenter:
        if self._segmenter is None:
            self._segmenter = ClothingSegmenter()
        return self._segmenter

    def detect_from_frames(
        self,
        frame_records: list[dict],
        output_dir: str | None = None,
    ) -> list[dict]:
        """Analyze pre-extracted frames for clothing change points.

        Args:
            frame_records: List of {path, timestamp, ...} from FrameExtractor.
            output_dir: Optional dir to write intermediate debug data.

        Returns:
            List of candidate dicts: [{timestamp, similarity, frame_idx}]
        """
        if len(frame_records) < 2:
            return []

        segmenter = self._get_segmenter()

        hsv_hists: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        upper_hists: list[tuple[np.ndarray, np.ndarray, np.ndarray] | None] = []
        lower_hists: list[tuple[np.ndarray, np.ndarray, np.ndarray] | None] = []
        orb_descs: list[np.ndarray | None] = []
        garment_sets: list[set[int]] = []

        for rec in frame_records:
            try:
                analysis = segmenter.analyze_frame(rec["path"])
                hsv_hists.append(analysis["hsv_hist"])
                upper_hists.append(analysis.get("upper_hsv_hist"))
                lower_hists.append(analysis.get("lower_hsv_hist"))
                orb_descs.append(analysis.get("orb_descriptors"))
                garment_sets.append(
                    ClothingSegmenter.get_main_garment_set(analysis["items"])
                )
                del analysis
            except Exception as exc:
                logger.warning("Frame analysis failed for %s: %s", rec["path"], exc)
                hsv_hists.append(
                    (
                        np.ones(180, dtype=np.float32) / 180,
                        np.ones(256, dtype=np.float32) / 256,
                        np.ones(256, dtype=np.float32) / 256,
                    )
                )
                upper_hists.append(None)
                lower_hists.append(None)
                orb_descs.append(None)
                garment_sets.append(set())

        # Compare consecutive frames
        correlations: list[float] = []
        upper_correlations: list[float | None] = []
        lower_correlations: list[float | None] = []
        category_changes: list[bool] = []
        texture_similarities: list[float | None] = []

        for i in range(len(hsv_hists) - 1):
            hsv_corr = self._compare_hists(hsv_hists[i], hsv_hists[i + 1])
            correlations.append(hsv_corr)

            upper_corr = self._compare_optional_hists(upper_hists[i], upper_hists[i + 1])
            upper_correlations.append(upper_corr)

            lower_corr = self._compare_optional_hists(lower_hists[i], lower_hists[i + 1])
            lower_correlations.append(lower_corr)

            cat_changed = self._detect_category_change(garment_sets[i], garment_sets[i + 1])
            category_changes.append(cat_changed)

            tex_sim = self._compare_orb(orb_descs[i], orb_descs[i + 1])
            texture_similarities.append(tex_sim)

        if not correlations:
            return []

        # Build raw candidate points from combined signal
        raw_points = []
        for i in range(len(correlations)):
            corr = correlations[i]
            cat_change = category_changes[i]
            upper_corr = upper_correlations[i]
            lower_corr = lower_correlations[i]
            tex_sim = texture_similarities[i]

            # Per-region HSV: if either region changed significantly
            region_change = False
            region_min_corr = corr
            if upper_corr is not None and upper_corr < self.hist_threshold:
                region_change = True
                region_min_corr = min(region_min_corr, upper_corr)
            if lower_corr is not None and lower_corr < self.hist_threshold:
                region_change = True
                region_min_corr = min(region_min_corr, lower_corr)

            # ORB texture change
            texture_change = tex_sim is not None and tex_sim < 0.4

            # 是否有视觉佐证（HSV / 分区域HSV / 纹理）
            has_visual_evidence = (
                corr < self.hist_threshold or region_change or texture_change
            )

            combined_score = self._combined_score_v2(
                corr, cat_change, region_change, region_min_corr,
                texture_change, tex_sim, has_visual_evidence,
            )

            # 触发条件：非品类变化信号直接触发；品类变化需视觉佐证
            # （孤立品类变化通常是主播拿放物品，不应触发候选）
            if has_visual_evidence or (cat_change and has_visual_evidence):
                raw_points.append(
                    {
                        "frame_idx": i + 1,
                        "timestamp": float(frame_records[i + 1]["timestamp"]),
                        "correlation": corr,
                        "category_change": cat_change,
                        "combined_score": combined_score,
                    }
                )

        logger.info(
            "Combined analysis: %d frames, %d raw signals "
            "(global HSV=%.2f, upper=%d, lower=%d, ORB=%d, YOLO=%s, MP=%s)",
            len(frame_records),
            len(raw_points),
            self.hist_threshold,
            sum(1 for c in upper_correlations if c is not None),
            sum(1 for c in lower_correlations if c is not None),
            sum(1 for s in texture_similarities if s is not None),
            segmenter.yolo_available,
            segmenter.mediapipe_available,
        )
        logger.info(
            "Category change filter: %d total, %d isolated (no visual evidence) → suppressed",
            sum(category_changes),
            sum(
                1 for i in range(len(category_changes))
                if category_changes[i]
                and correlations[i] >= self.hist_threshold
                and not (
                    (upper_correlations[i] is not None and upper_correlations[i] < self.hist_threshold)
                    or (lower_correlations[i] is not None and lower_correlations[i] < self.hist_threshold)
                    or (texture_similarities[i] is not None and texture_similarities[i] < 0.4)
                )
            ),
        )

        merged = self._merge_events(raw_points)
        candidates = self._apply_min_gap(merged)

        logger.info(
            "After merge+cooldown: %d clothing-change candidates",
            len(candidates),
        )

        result = []
        for cand in candidates:
            result.append(
                {
                    "timestamp": cand["timestamp"],
                    "similarity": 1.0 - cand["correlation"],
                    "frame_idx": cand["frame_idx"],
                }
            )

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            debug_data = {
                "correlations": correlations,
                "upper_correlations": [c if c is not None else "N/A" for c in upper_correlations],
                "lower_correlations": [c if c is not None else "N/A" for c in lower_correlations],
                "texture_similarities": [s if s is not None else "N/A" for s in texture_similarities],
                "category_changes": category_changes,
                "raw_points": [
                    {k: v for k, v in p.items() if k != "combined_score"}
                    for p in raw_points
                ],
                "merged": [
                    {k: v for k, v in m.items() if k != "combined_score"}
                    for m in merged
                ],
                "candidates": result,
                "params": {
                    "hist_threshold": self.hist_threshold,
                    "min_scene_gap": self.min_scene_gap,
                    "merge_window": self.merge_window,
                    "orb_texture_threshold": 0.4,
                },
                "models": {
                    "mediapipe_available": segmenter.mediapipe_available,
                    "yolo_available": segmenter.yolo_available,
                },
            }
            (out / "hist_debug.json").write_text(
                json.dumps(debug_data, ensure_ascii=False, indent=2, default=str),
            )

        return result

    @staticmethod
    def _compare_hists(
        pair1: tuple[np.ndarray, np.ndarray, np.ndarray],
        pair2: tuple[np.ndarray, np.ndarray, np.ndarray],
    ) -> float:
        h_corr = cv2.compareHist(pair1[0], pair2[0], cv2.HISTCMP_CORREL)
        s_corr = cv2.compareHist(pair1[1], pair2[1], cv2.HISTCMP_CORREL)
        v_corr = cv2.compareHist(pair1[2], pair2[2], cv2.HISTCMP_CORREL)
        return float(0.3 * h_corr + 0.35 * s_corr + 0.35 * v_corr)

    @staticmethod
    def _compare_optional_hists(
        pair1: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
        pair2: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
    ) -> float | None:
        if pair1 is None or pair2 is None:
            return None
        return ClothingChangeDetector._compare_hists(pair1, pair2)

    @staticmethod
    def _compare_orb(
        desc1: np.ndarray | None,
        desc2: np.ndarray | None,
    ) -> float | None:
        if desc1 is None or desc2 is None or len(desc1) < 5 or len(desc2) < 5:
            return None
        try:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(desc1, desc2)
            good = [m for m in matches if m.distance < 50]
            return len(good) / max(len(desc1), len(desc2))
        except Exception:
            return None

    @staticmethod
    def _combined_score_v2(
        global_corr: float,
        category_change: bool,
        region_change: bool,
        region_min_corr: float,
        texture_change: bool,
        texture_sim: float | None,
        has_visual_evidence: bool = True,
    ) -> float:
        base = max(1.0 - global_corr, 0.0)
        if category_change and has_visual_evidence:
            base = max(base, 0.3)
        if region_change:
            base = max(base, 1.0 - region_min_corr) * 1.2
        if texture_change and texture_sim is not None:
            base = max(base, (1.0 - texture_sim) * 0.8)
        return min(base, 1.0)

    @staticmethod
    def _detect_category_change(
        prev_garments: set[int],
        curr_garments: set[int],
    ) -> bool:
        """Detect if main garment categories changed between frames."""
        if not prev_garments and not curr_garments:
            return False

        # Symmetric difference: items that appeared or disappeared
        changed = prev_garments.symmetric_difference(curr_garments)

        if not changed:
            return False

        # At least one changed category must be a main garment
        # (already guaranteed since inputs are pre-filtered to main garments)
        return True

    @staticmethod
    def _combined_score(hsv_corr: float, category_change: bool) -> float:
        """Compute combined change score from HSV correlation and category signal."""
        if category_change:
            return max(1.0 - hsv_corr, 0.3)
        return 1.0 - hsv_corr

    @staticmethod
    def _fallback_analysis() -> dict:
        """Return a neutral analysis when frame processing fails."""
        return {
            "mask": np.ones((360, 640), dtype=bool),
            "items": [],
            "hsv_hist": (
                np.ones(180, dtype=np.float32),
                np.ones(256, dtype=np.float32),
                np.ones(256, dtype=np.float32),
            ),
        }

    def _merge_events(
        self,
        raw_points: list[dict],
    ) -> list[dict]:
        """Merge consecutive raw drops within merge_window into single events."""
        if not raw_points:
            return []

        merged = []
        cluster = [raw_points[0]]

        for pt in raw_points[1:]:
            if pt["timestamp"] - cluster[0]["timestamp"] <= self.merge_window:
                cluster.append(pt)
            else:
                best = min(cluster, key=lambda p: p["correlation"])
                merged.append(best)
                cluster = [pt]

        if cluster:
            best = min(cluster, key=lambda p: p["correlation"])
            merged.append(best)

        return merged

    def _apply_min_gap(self, events: list[dict]) -> list[dict]:
        """Ensure minimum gap between consecutive candidates (cooldown)."""
        if not events:
            return []

        filtered = [events[0]]
        for ev in events[1:]:
            if ev["timestamp"] - filtered[-1]["timestamp"] >= self.min_scene_gap:
                filtered.append(ev)
        return filtered

    @staticmethod
    def detect_scenes_from_candidates(
        candidates: list[dict],
        video_duration: float,
    ) -> list[dict]:
        """Convert change-point candidates into scene segments.

        Each candidate marks the START of a new clothing segment.
        Segments span from one change point to the next (or video end).

        Returns:
            List of {start_time, end_time} scene dicts.
        """
        if not candidates:
            return [{"start_time": 0.0, "end_time": video_duration}]

        scenes = []
        sorted_cands = sorted(candidates, key=lambda c: c["timestamp"])

        first_ts = sorted_cands[0]["timestamp"]
        if first_ts > 1.0:
            scenes.append({"start_time": 0.0, "end_time": first_ts})

        for i in range(len(sorted_cands) - 1):
            scenes.append(
                {
                    "start_time": sorted_cands[i]["timestamp"],
                    "end_time": sorted_cands[i + 1]["timestamp"],
                }
            )

        scenes.append(
            {
                "start_time": sorted_cands[-1]["timestamp"],
                "end_time": video_duration,
            }
        )

        return scenes
