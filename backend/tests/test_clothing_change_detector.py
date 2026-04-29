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
