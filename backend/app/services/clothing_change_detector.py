"""Clothing change detector — five-signal fusion with multi-signal EMA and hysteresis.

Detects "clothing change" moments in livestream videos using five signals:
1. YOLO fashionpedia category change (different garment types detected)
2. MediaPipe clothes-mask HSV histogram correlation drop
3. Whole-frame HSV histogram correlation drop
4. Per-region HSV (upper/lower body) correlation drop
5. ORB texture similarity drop

Anti-false-positive improvements:
- Independent EMA smoothing on ALL signals (global HSV, upper HSV, lower HSV, texture)
- ANY smoothed signal crossing the enter threshold triggers the "changing" state
- ALL smoothed signals must recover above the exit threshold to return to "stable"
- Hysteresis threshold: enter at hist_threshold (0.85), exit at exit_threshold (0.90)
- Consecutive frame confirmation: a change must persist for confirm_frames frames
- Person presence tracking: writes person_presence.json for downstream use

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

    DEFAULT_HIST_THRESHOLD: float = 0.85
    DEFAULT_MIN_SCENE_GAP: float = 20.0
    DEFAULT_MERGE_WINDOW: float = 25.0

    def __init__(
        self,
        hist_threshold: float | None = None,
        min_scene_gap: float | None = None,
        merge_window: float | None = None,
        ema_alpha: float | None = None,
        exit_threshold: float | None = None,
        confirm_frames: int = 2,
    ) -> None:
        self.hist_threshold = hist_threshold or self.DEFAULT_HIST_THRESHOLD
        self.min_scene_gap = min_scene_gap or self.DEFAULT_MIN_SCENE_GAP
        self.merge_window = merge_window or self.DEFAULT_MERGE_WINDOW
        self.ema_alpha = ema_alpha if ema_alpha is not None else 0.3
        self.exit_threshold = exit_threshold if exit_threshold is not None else 0.90
        self.confirm_frames = confirm_frames
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
        person_present_flags: list[bool] = []

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
                person_present_flags.append(len(analysis["items"]) > 0)
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
                person_present_flags.append(False)

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

        # --- Multi-signal independent EMA smoothing ---
        TEX_ENTER_THRESHOLD = 0.6   # inverted texture: 1.0 - 0.4
        TEX_EXIT_THRESHOLD = 0.7    # inverted texture: 1.0 - 0.3

        def _ema(prev: float | None, raw: float | None) -> float | None:
            if raw is None:
                return prev
            if prev is None:
                return raw
            return self.ema_alpha * raw + (1 - self.ema_alpha) * prev

        global_ema: list[float] = [correlations[0]]
        upper_ema: list[float | None] = [upper_correlations[0]]
        lower_ema: list[float | None] = [lower_correlations[0]]
        tex_ema: list[float | None] = [
            (1.0 - texture_similarities[0]) if texture_similarities[0] is not None else None
        ]

        for i in range(1, len(correlations)):
            global_ema.append(
                self.ema_alpha * correlations[i]
                + (1 - self.ema_alpha) * global_ema[-1]
            )
            upper_ema.append(_ema(upper_ema[-1], upper_correlations[i]))
            lower_ema.append(_ema(lower_ema[-1], lower_correlations[i]))
            raw_tex = texture_similarities[i]
            inverted_tex: float | None = (1.0 - raw_tex) if raw_tex is not None else None
            tex_ema.append(_ema(tex_ema[-1], inverted_tex))

        # --- State machine: ANY triggers enter, ALL must recover for exit ---
        raw_points: list[dict] = []
        state = "stable"
        change_start: int | None = None
        change_candidates: list[dict] = []

        global_trigger_count = 0
        upper_trigger_count = 0
        lower_trigger_count = 0
        tex_trigger_count = 0

        for i in range(len(global_ema)):
            g_ema = global_ema[i]
            u_ema = upper_ema[i]
            l_ema = lower_ema[i]
            t_ema = tex_ema[i]

            any_triggered = (
                g_ema < self.hist_threshold
                or (u_ema is not None and u_ema < self.hist_threshold)
                or (l_ema is not None and l_ema < self.hist_threshold)
                or (t_ema is not None and t_ema < TEX_ENTER_THRESHOLD)
            )

            all_recovered = (
                g_ema >= self.exit_threshold
                and (u_ema is None or u_ema >= self.exit_threshold)
                and (l_ema is None or l_ema >= self.exit_threshold)
                and (t_ema is None or t_ema >= TEX_EXIT_THRESHOLD)
            )

            cat_change = category_changes[i]

            # Per-signal trigger bookkeeping for the log
            if g_ema < self.hist_threshold:
                global_trigger_count += 1
            if u_ema is not None and u_ema < self.hist_threshold:
                upper_trigger_count += 1
            if l_ema is not None and l_ema < self.hist_threshold:
                lower_trigger_count += 1
            if t_ema is not None and t_ema < TEX_ENTER_THRESHOLD:
                tex_trigger_count += 1

            # Compute best (lowest) EMA across available signals for ranking
            ema_values = [g_ema]
            if u_ema is not None:
                ema_values.append(u_ema)
            if l_ema is not None:
                ema_values.append(l_ema)
            if t_ema is not None:
                ema_values.append(t_ema)
            best_ema = min(ema_values)

            if state == "stable":
                if any_triggered:
                    state = "changing"
                    change_start = i
                    change_candidates = [
                        {
                            "frame_idx": i + 1,
                            "timestamp": float(frame_records[i + 1]["timestamp"]),
                            "correlation": correlations[i],
                            "best_ema": best_ema,
                            "category_change": cat_change,
                        }
                    ]
            elif state == "changing":
                if all_recovered:
                    assert change_start is not None
                    duration_frames = i - change_start
                    if (
                        duration_frames >= self.confirm_frames
                        and change_candidates
                    ):
                        best = min(
                            change_candidates, key=lambda p: p["best_ema"]
                        )
                        # Recompute region signals at the winning index for scoring
                        wi = change_candidates.index(best)
                        bi = change_start + wi
                        region_change = False
                        region_min_corr = correlations[bi]
                        uc = upper_correlations[bi]
                        if uc is not None and uc < self.hist_threshold:
                            region_change = True
                            region_min_corr = min(region_min_corr, uc)
                        lc = lower_correlations[bi]
                        if lc is not None and lc < self.hist_threshold:
                            region_change = True
                            region_min_corr = min(region_min_corr, lc)
                        ts = texture_similarities[bi]
                        tex_change = ts is not None and ts < 0.4

                        best["combined_score"] = self._combined_score_v2(
                            correlations[bi],
                            category_changes[bi],
                            region_change,
                            region_min_corr,
                            tex_change,
                            ts,
                            True,
                        )
                        raw_points.append(best)
                    state = "stable"
                    change_start = None
                    change_candidates = []
                else:
                    change_candidates.append(
                        {
                            "frame_idx": i + 1,
                            "timestamp": float(frame_records[i + 1]["timestamp"]),
                            "correlation": correlations[i],
                            "best_ema": best_ema,
                            "category_change": cat_change,
                        }
                    )

        if (
            state == "changing"
            and change_candidates
            and len(change_candidates) >= self.confirm_frames
        ):
            best = min(change_candidates, key=lambda p: p["best_ema"])
            # Recompute region signals at the winning index for scoring
            wi = change_candidates.index(best)
            bi = (change_start or 0) + wi
            region_change = False
            region_min_corr = correlations[bi]
            uc = upper_correlations[bi]
            if uc is not None and uc < self.hist_threshold:
                region_change = True
                region_min_corr = min(region_min_corr, uc)
            lc = lower_correlations[bi]
            if lc is not None and lc < self.hist_threshold:
                region_change = True
                region_min_corr = min(region_min_corr, lc)
            ts = texture_similarities[bi]
            tex_change = ts is not None and ts < 0.4

            best["combined_score"] = self._combined_score_v2(
                correlations[bi],
                category_changes[bi],
                region_change,
                region_min_corr,
                tex_change,
                ts,
                True,
            )
            raw_points.append(best)

        logger.info(
            "Multi-signal EMA analysis: %d frames, %d raw signals "
            "(EMA triggers: global=%d, upper=%d, lower=%d, tex=%d)",
            len(frame_records),
            len(raw_points),
            global_trigger_count,
            upper_trigger_count,
            lower_trigger_count,
            tex_trigger_count,
        )
        isolated_count = 0
        for i in range(len(category_changes)):
            if not category_changes[i]:
                continue
            u = upper_ema[i]
            l = lower_ema[i]
            t = tex_ema[i]
            if (
                global_ema[i] >= self.hist_threshold
                and (u is None or u >= self.hist_threshold)
                and (l is None or l >= self.hist_threshold)
                and (t is None or t >= TEX_ENTER_THRESHOLD)
            ):
                isolated_count += 1
        logger.info(
            "Category change filter: %d total, %d isolated (no EMA signal) → suppressed",
            sum(category_changes),
            isolated_count,
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
                "ema_global": global_ema,
                "ema_upper": [v if v is not None else None for v in upper_ema],
                "ema_lower": [v if v is not None else None for v in lower_ema],
                "ema_texture": [v if v is not None else None for v in tex_ema],
                "raw_points": [
                    {k: v for k, v in p.items() if k not in ("combined_score", "best_ema")}
                    for p in raw_points
                ],
                "merged": [
                    {k: v for k, v in m.items() if k not in ("combined_score", "best_ema")}
                    for m in merged
                ],
                "candidates": result,
                "params": {
                    "hist_threshold": self.hist_threshold,
                    "exit_threshold": self.exit_threshold,
                    "ema_alpha": self.ema_alpha,
                    "confirm_frames": self.confirm_frames,
                    "min_scene_gap": self.min_scene_gap,
                    "merge_window": self.merge_window,
                    "orb_texture_threshold": 0.4,
                    "tex_enter_threshold": TEX_ENTER_THRESHOLD,
                    "tex_exit_threshold": TEX_EXIT_THRESHOLD,
                },
                "models": {
                    "mediapipe_available": segmenter.mediapipe_available,
                    "yolo_available": segmenter.yolo_available,
                },
            }
            (out / "hist_debug.json").write_text(
                json.dumps(debug_data, ensure_ascii=False, indent=2, default=str),
            )

            person_presence = [
                {
                    "timestamp": rec["timestamp"],
                    "person_present": (
                        person_present_flags[i]
                        if i < len(person_present_flags)
                        else False
                    ),
                }
                for i, rec in enumerate(frame_records)
            ]
            (out / "person_presence.json").write_text(
                json.dumps(person_presence, ensure_ascii=False, indent=2),
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
