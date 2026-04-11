"""Tests for FrameExtractor using test_30s.mp4."""

import json
from pathlib import Path

import pytest

from app.services.frame_extractor import FrameExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_VIDEO = FIXTURES_DIR / "test_30s.mp4"


@pytest.fixture
def extractor():
    return FrameExtractor()


@pytest.fixture
def sample_scenes():
    return [
        {"start_time": 0.0, "end_time": 10.0},
        {"start_time": 10.0, "end_time": 20.0},
    ]


class TestExtract:
    def test_extracts_frames_within_scenes(self, extractor, sample_scenes, tmp_path):
        frames = extractor.extract(str(TEST_VIDEO), sample_scenes, str(tmp_path))
        assert len(frames) > 0
        for f in frames:
            assert "path" in f
            assert "timestamp" in f
            assert "scene_idx" in f

    def test_output_frames_are_jpeg(self, extractor, sample_scenes, tmp_path):
        frames = extractor.extract(str(TEST_VIDEO), sample_scenes, str(tmp_path))
        for f in frames:
            assert f["path"].endswith(".jpg")
            assert Path(f["path"]).exists()

    def test_frames_json_written(self, extractor, sample_scenes, tmp_path):
        frames = extractor.extract(str(TEST_VIDEO), sample_scenes, str(tmp_path))
        frames_file = tmp_path / "frames.json"
        assert frames_file.exists()
        saved = json.loads(frames_file.read_text())
        assert len(saved) == len(frames)

    def test_scene_idx_assigned(self, extractor, sample_scenes, tmp_path):
        frames = extractor.extract(str(TEST_VIDEO), sample_scenes, str(tmp_path))
        scene_indices = {f["scene_idx"] for f in frames}
        assert 0 in scene_indices
        assert 1 in scene_indices

    def test_single_scene(self, extractor, tmp_path):
        scenes = [{"start_time": 0.0, "end_time": 5.0}]
        frames = extractor.extract(str(TEST_VIDEO), scenes, str(tmp_path))
        assert len(frames) >= 4  # 5 seconds at 1fps → ~5 frames
        assert all(f["scene_idx"] == 0 for f in frames)
