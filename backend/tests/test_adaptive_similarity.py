"""Tests for AdaptiveSimilarityAnalyzer — pure logic, no external deps."""

import numpy as np
import pytest

from app.services.adaptive_similarity import AdaptiveSimilarityAnalyzer


@pytest.fixture
def analyzer():
    return AdaptiveSimilarityAnalyzer()


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self, analyzer):
        embeddings = np.array([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        sims = analyzer.compute_cosine_similarity(embeddings)
        assert len(sims) == 1
        assert abs(sims[0] - 1.0) < 1e-6

    def test_orthogonal_vectors_return_zero(self, analyzer):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
        sims = analyzer.compute_cosine_similarity(embeddings)
        assert len(sims) == 1
        assert abs(sims[0]) < 1e-6

    def test_multiple_frames(self, analyzer):
        rng = np.random.RandomState(42)
        embeddings = rng.randn(10, 768).astype(np.float32)
        sims = analyzer.compute_cosine_similarity(embeddings)
        assert sims.shape == (9,)
        assert np.all(sims >= -1.0) and np.all(sims <= 1.0)

    def test_empty_embeddings(self, analyzer):
        sims = analyzer.compute_cosine_similarity(np.empty((0, 768)))
        assert len(sims) == 0

    def test_single_embedding(self, analyzer):
        sims = analyzer.compute_cosine_similarity(np.array([[1.0, 2.0]]))
        assert len(sims) == 0


class TestAdaptiveThreshold:
    def test_threshold_in_range(self, analyzer):
        rng = np.random.RandomState(42)
        sims = rng.normal(0.9, 0.05, size=100).astype(np.float64)
        threshold = analyzer.compute_adaptive_threshold(sims)
        assert 0.78 <= threshold <= 0.82

    def test_high_similarities_clamp_to_high(self, analyzer):
        sims = np.full(50, 0.99)
        threshold = analyzer.compute_adaptive_threshold(sims)
        assert threshold == 0.82

    def test_low_similarities_clamp_to_low(self, analyzer):
        sims = np.full(50, 0.5)
        threshold = analyzer.compute_adaptive_threshold(sims)
        assert threshold == 0.78

    def test_empty_similarities_returns_low(self, analyzer):
        threshold = analyzer.compute_adaptive_threshold(np.array([]))
        assert threshold == 0.78


class TestSlidingWindow:
    def test_smooths_noise(self, analyzer):
        # 10 frames: all similar except frame 5 which drops
        sims = np.array([0.9, 0.9, 0.9, 0.9, 0.5, 0.9, 0.9, 0.9, 0.9, 0.9])
        smoothed = analyzer.apply_sliding_window(sims, window_size=5)
        # The dip at index 4 should be smoothed — smoothed values should be closer to 0.9
        assert smoothed[0] > 0.7  # window covers [0.9, 0.9, 0.9, 0.9, 0.5]
        assert smoothed[1] > 0.8  # window covers [0.9, 0.9, 0.9, 0.5, 0.9]

    def test_output_length(self, analyzer):
        sims = np.ones(10)
        smoothed = analyzer.apply_sliding_window(sims, window_size=5)
        assert len(smoothed) == 10 - 5 + 1  # mode='valid'

    def test_short_array_returns_copy(self, analyzer):
        sims = np.array([0.5, 0.6, 0.7])
        smoothed = analyzer.apply_sliding_window(sims, window_size=5)
        np.testing.assert_array_equal(smoothed, sims)


class TestCooldown:
    def test_filters_close_candidates(self, analyzer):
        # 3 candidates at 0s, 20s, 90s → keeps 0s and 90s (20s within 60s cooldown)
        candidates = [
            {"timestamp": 0.0, "similarity": 0.7, "frame_idx": 0},
            {"timestamp": 20.0, "similarity": 0.7, "frame_idx": 5},
            {"timestamp": 90.0, "similarity": 0.7, "frame_idx": 15},
        ]
        filtered = analyzer.apply_cooldown(candidates, cooldown_seconds=60.0)
        assert len(filtered) == 2
        assert filtered[0]["timestamp"] == 0.0
        assert filtered[1]["timestamp"] == 90.0

    def test_all_spaced_out_keeps_all(self, analyzer):
        candidates = [
            {"timestamp": 0.0, "similarity": 0.7, "frame_idx": 0},
            {"timestamp": 70.0, "similarity": 0.7, "frame_idx": 10},
            {"timestamp": 150.0, "similarity": 0.7, "frame_idx": 20},
        ]
        filtered = analyzer.apply_cooldown(candidates, cooldown_seconds=60.0)
        assert len(filtered) == 3

    def test_empty_candidates(self, analyzer):
        filtered = analyzer.apply_cooldown([], cooldown_seconds=60.0)
        assert filtered == []

    def test_single_candidate(self, analyzer):
        candidates = [{"timestamp": 5.0, "similarity": 0.7, "frame_idx": 0}]
        filtered = analyzer.apply_cooldown(candidates, cooldown_seconds=60.0)
        assert len(filtered) == 1


class TestAnalyze:
    def test_empty_embeddings_returns_empty(self, analyzer):
        result = analyzer.analyze(np.empty((0, 768)), [])
        assert result == []

    def test_single_embedding_returns_empty(self, analyzer):
        result = analyzer.analyze(np.array([[1.0, 2.0]]), [0.0])
        assert result == []

    def test_full_pipeline_with_switch(self, analyzer):
        # Create embeddings where frame 5 is very different
        rng = np.random.RandomState(42)
        base = rng.randn(1, 768).astype(np.float32)
        base = base / np.linalg.norm(base)

        embeddings = np.tile(base, (15, 1))
        # Make frame 5 very different
        different = rng.randn(1, 768).astype(np.float32)
        different = different / np.linalg.norm(different)
        embeddings[5] = different[0]

        timestamps = [float(i) for i in range(15)]
        candidates = analyzer.analyze(embeddings, timestamps)

        # Should detect the switch around frame 5
        assert len(candidates) >= 1
        # The candidate should be near frame 5 (accounting for window offset)
        candidate_timestamps = [c["timestamp"] for c in candidates]
        assert any(3.0 <= t <= 7.0 for t in candidate_timestamps)

    def test_uniform_embeddings_no_candidates(self, analyzer):
        # All identical embeddings → similarity = 1.0 everywhere → no candidates
        vec = np.random.RandomState(42).randn(1, 768).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        embeddings = np.tile(vec, (20, 1))
        timestamps = [float(i) for i in range(20)]
        candidates = analyzer.analyze(embeddings, timestamps)
        assert len(candidates) == 0
