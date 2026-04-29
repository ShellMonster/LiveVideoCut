import json

import numpy as np

from app.services.clothing_change_detector import ClothingChangeDetector


def test_weighted_vote_score_combines_available_signals():
    score = ClothingChangeDetector._weighted_vote_score(
        global_ema=0.8,
        upper_ema=0.7,
        lower_ema=0.91,
        texture_ema=0.5,
        category_change=True,
        hist_threshold=0.85,
        texture_threshold=0.6,
    )

    assert score == 0.85


def test_category_change_ignores_missing_frame_features():
    assert ClothingChangeDetector._detect_category_change({1, 2}, None) is False
    assert ClothingChangeDetector._detect_category_change(None, {1, 2}) is False


def test_missing_frame_analysis_is_marked_invalid_and_skipped(tmp_path):
    detector = ClothingChangeDetector(confirm_frames=1)
    hist = (
        np.ones(180, dtype=np.float32),
        np.ones(256, dtype=np.float32),
        np.ones(256, dtype=np.float32),
    )
    valid_analysis = {
        "items": [],
        "hsv_hist": hist,
        "upper_hsv_hist": None,
        "lower_hsv_hist": None,
        "orb_descriptors": None,
    }
    detector._analyze_frames = lambda _records: [valid_analysis, None, valid_analysis]  # type: ignore[method-assign]

    candidates = detector.detect_from_frames(
        [
            {"path": "frame_000.jpg", "timestamp": 0.0},
            {"path": "frame_001.jpg", "timestamp": 1.0},
            {"path": "frame_002.jpg", "timestamp": 2.0},
        ],
        output_dir=str(tmp_path),
    )

    assert candidates == []

    debug = json.loads((tmp_path / "hist_debug.json").read_text())
    assert debug["invalid_frame_indices"] == [1]
    assert debug["invalid_frame_count"] == 1
    assert debug["valid_pairs"] == [False, False]
    assert debug["weighted_vote_scores"] == [None, None]

    person_presence = json.loads((tmp_path / "person_presence.json").read_text())
    assert person_presence[1]["analysis_valid"] is False
