"""Adaptive similarity analysis with sliding window and cooldown."""

import numpy as np


class AdaptiveSimilarityAnalyzer:
    """Analyzes frame similarities with sliding window + adaptive threshold + cooldown.

    Pipeline: cosine similarity → sliding window smoothing → adaptive threshold
    → cooldown filtering → candidate list.
    """

    DEFAULT_WINDOW_SIZE = 5
    DEFAULT_COOLDOWN = 60.0
    THRESHOLD_LOW = 0.78
    THRESHOLD_HIGH = 0.82
    PERCENTILE = 90
    THRESHOLD_SCALE = 0.9

    def compute_cosine_similarity(self, embeddings: np.ndarray) -> np.ndarray:
        """Pairwise cosine similarity between consecutive frames.

        Args:
            embeddings: Shape (N, D) array of frame embeddings.

        Returns:
            Shape (N-1,) array of cosine similarities.
        """
        if len(embeddings) < 2:
            return np.array([], dtype=np.float64)

        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = embeddings / norms

        similarities = np.sum(normalized[:-1] * normalized[1:], axis=1)
        return similarities.astype(np.float64)

    def compute_adaptive_threshold(self, similarities: np.ndarray) -> float:
        """Compute adaptive threshold: 90th percentile * 0.9, clamped to [0.78, 0.82]."""
        if len(similarities) == 0:
            return self.THRESHOLD_LOW

        raw = np.percentile(similarities, self.PERCENTILE) * self.THRESHOLD_SCALE
        return float(np.clip(raw, self.THRESHOLD_LOW, self.THRESHOLD_HIGH))

    def apply_sliding_window(
        self, similarities: np.ndarray, window_size: int = 5
    ) -> np.ndarray:
        """Smooth similarities with uniform sliding window."""
        if len(similarities) < window_size:
            return similarities.copy()

        kernel = np.ones(window_size) / window_size
        smoothed = np.convolve(similarities, kernel, mode="valid")
        return smoothed

    def apply_cooldown(
        self, candidates: list[dict], cooldown_seconds: float = 60.0
    ) -> list[dict]:
        """After confirming a switch, ignore new candidates within cooldown period."""
        if not candidates:
            return []

        filtered = [candidates[0]]
        for cand in candidates[1:]:
            last_time = filtered[-1]["timestamp"]
            if cand["timestamp"] - last_time >= cooldown_seconds:
                filtered.append(cand)
        return filtered

    def analyze(
        self,
        embeddings: np.ndarray,
        frame_timestamps: list[float],
        window_size: int | None = None,
        cooldown_seconds: float | None = None,
    ) -> list[dict]:
        """Full pipeline: similarity → window → threshold → cooldown → candidates.

        Args:
            embeddings: Shape (N, D) array of frame embeddings.
            frame_timestamps: List of N timestamps corresponding to embeddings.
            window_size: Sliding window size (default 5).
            cooldown_seconds: Cooldown period in seconds (default 60).

        Returns:
            List of candidate dicts: [{timestamp, similarity, frame_idx}]
        """
        if len(embeddings) < 2 or len(frame_timestamps) < 2:
            return []

        win = window_size or self.DEFAULT_WINDOW_SIZE
        cooldown = (
            cooldown_seconds if cooldown_seconds is not None else self.DEFAULT_COOLDOWN
        )

        similarities = self.compute_cosine_similarity(embeddings)
        smoothed = self.apply_sliding_window(similarities, window_size=win)
        threshold = self.compute_adaptive_threshold(similarities)

        # Find frames below threshold (low similarity = potential scene switch)
        candidates = []
        # Smoothed array is shorter by (window_size - 1), offset maps back to original indices
        offset = win - 1
        for i, sim in enumerate(smoothed):
            if sim < threshold:
                orig_idx = i + offset
                if orig_idx < len(frame_timestamps):
                    candidates.append(
                        {
                            "timestamp": frame_timestamps[orig_idx],
                            "similarity": float(sim),
                            "frame_idx": orig_idx,
                        }
                    )

        return self.apply_cooldown(candidates, cooldown_seconds=cooldown)
