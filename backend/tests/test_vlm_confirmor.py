"""Tests for VLMConfirmor — mocked VLM client, no real API calls."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.vlm_confirmor import VLMConfirmor


def _make_vlm_response(
    is_different=True, confidence=0.85, product_type="裙子", color="蓝色"
):
    return json.dumps(
        {
            "is_different": is_different,
            "confidence": confidence,
            "dimensions": {
                "type": {
                    "same": not is_different,
                    "value_1": "上衣",
                    "value_2": product_type,
                },
                "color": {
                    "same": not is_different,
                    "value_1": "红色",
                    "value_2": color,
                },
            },
            "product_1": {"type": "上衣", "color": "红色", "style": "修身上衣"},
            "product_2": {
                "type": product_type,
                "color": color,
                "style": f"{product_type}",
            },
        }
    )


@pytest.fixture
def mock_client():
    client = MagicMock()
    return client


@pytest.fixture
def confirmor(mock_client):
    return VLMConfirmor(vlm_client=mock_client)


@pytest.fixture
def frames_dir(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    scene1 = frames / "scene0"
    scene1.mkdir()
    (scene1 / "frame_000.jpg").write_bytes(b"\xff\xd8fake1")
    (scene1 / "frame_001.jpg").write_bytes(b"\xff\xd8fake2")
    (scene1 / "frame_002.jpg").write_bytes(b"\xff\xd8fake3")
    return str(frames)


@pytest.fixture
def candidates():
    return [
        {"timestamp": 10.0, "similarity": 0.7, "frame_idx": 1},
        {"timestamp": 30.0, "similarity": 0.65, "frame_idx": 2},
    ]


class TestFilterIsDifferentFalse:
    def test_filters_out_not_different(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(is_different=False)
        result = confirmor.confirm_candidates(candidates, frames_dir)
        assert result == []


class TestKeepIsDifferentTrue:
    def test_keeps_different_segments(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(is_different=True)
        result = confirmor.confirm_candidates(candidates, frames_dir)
        assert len(result) == 2

    def test_mixed_responses_filters_correctly(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.side_effect = [
            _make_vlm_response(is_different=True),
            _make_vlm_response(is_different=False),
        ]
        result = confirmor.confirm_candidates(candidates, frames_dir)
        assert len(result) == 1
        assert result[0]["start_time"] == 10.0


class TestConfirmedSegmentFormat:
    def test_has_required_fields(self, confirmor, mock_client, frames_dir, candidates):
        mock_client.compare_frames.return_value = _make_vlm_response(
            is_different=True, confidence=0.9
        )
        result = confirmor.confirm_candidates(candidates, frames_dir)
        segment = result[0]

        assert "start_time" in segment
        assert "end_time" in segment
        assert "confidence" in segment
        assert "product_info" in segment
        assert "low_confidence" in segment

    def test_product_info_structure(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(
            is_different=True, product_type="外套", color="黑色"
        )
        result = confirmor.confirm_candidates(candidates, frames_dir)
        product = result[0]["product_info"]

        assert product["type"] == "外套"
        assert product["color"] == "黑色"
        assert "style" in product
        assert "description" in product

    def test_confidence_value_preserved(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(confidence=0.75)
        result = confirmor.confirm_candidates(candidates, frames_dir)
        assert result[0]["confidence"] == 0.75


class TestLowConfidenceFlag:
    def test_low_confidence_flagged(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(confidence=0.55)
        result = confirmor.confirm_candidates(
            candidates, frames_dir, review_strictness="loose"
        )
        assert result[0]["low_confidence"] is True

    def test_high_confidence_not_flagged(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(confidence=0.9)
        result = confirmor.confirm_candidates(candidates, frames_dir)
        assert result[0]["low_confidence"] is False


class TestReviewStrictnessThresholds:
    def test_strict_filters_mid_confidence_matches(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(
            is_different=True, confidence=0.65
        )

        result = confirmor.confirm_candidates(
            candidates, frames_dir, review_strictness="strict"
        )

        assert result == []

    def test_standard_keeps_threshold_match(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(
            is_different=True, confidence=0.6
        )

        result = confirmor.confirm_candidates(
            candidates, frames_dir, review_strictness="standard"
        )

        assert len(result) == 2

    def test_loose_keeps_lower_confidence_matches(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(
            is_different=True, confidence=0.55
        )

        result = confirmor.confirm_candidates(
            candidates, frames_dir, review_strictness="loose"
        )

        assert len(result) == 2


class TestEmptyCandidates:
    def test_empty_candidates_returns_empty(self, confirmor, mock_client, frames_dir):
        result = confirmor.confirm_candidates([], frames_dir)
        assert result == []
        mock_client.compare_frames.assert_not_called()


class TestVLMCallFailure:
    def test_skips_candidate_on_api_error(
        self, confirmor, mock_client, frames_dir, candidates
    ):
        mock_client.compare_frames.side_effect = RuntimeError("API failed")
        result = confirmor.confirm_candidates(candidates, frames_dir)
        assert result == []


class TestSaveResults:
    def test_saves_confirmed_to_file(
        self, confirmor, mock_client, frames_dir, candidates, tmp_path
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(is_different=True)

        with patch.object(confirmor, "_save_results"):
            result = confirmor.confirm_candidates(
                candidates, frames_dir, task_id="test-task-123"
            )

        assert len(result) == 2

    def test_saves_empty_confirmed_file_when_no_segments_match(
        self, confirmor, mock_client, frames_dir, candidates, tmp_path, monkeypatch
    ):
        mock_client.compare_frames.return_value = _make_vlm_response(is_different=False)
        monkeypatch.chdir(tmp_path)

        result = confirmor.confirm_candidates(
            candidates, frames_dir, task_id="test-task-empty"
        )

        output_file = (
            tmp_path / "uploads" / "test-task-empty" / "vlm" / "confirmed_segments.json"
        )
        assert result == []
        assert output_file.exists()
        assert json.loads(output_file.read_text()) == []
