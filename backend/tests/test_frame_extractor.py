"""Tests for FrameExtractor using test_30s.mp4."""

# pyright: reportImplicitRelativeImport=false

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

    def test_uses_configured_sample_fps_in_ffmpeg_filter(
        self, extractor, sample_scenes, tmp_path, monkeypatch
    ):
        captured_filters = []

        def fake_run(cmd, capture_output, timeout, check):
            captured_filters.append(cmd[cmd.index("-vf") + 1])
            output_pattern = Path(cmd[-1])
            output_pattern.parent.mkdir(parents=True, exist_ok=True)
            (output_pattern.parent / "frame_00001.jpg").write_bytes(b"jpg")

        monkeypatch.setattr("app.services.frame_extractor.subprocess.run", fake_run)

        extractor.extract(str(TEST_VIDEO), sample_scenes, str(tmp_path), sample_fps=3)

        assert captured_filters == ["fps=3", "fps=3"]
