"""Tests for SceneDetector using test_30s.mp4."""

# pyright: reportImplicitRelativeImport=false

import json
from pathlib import Path

import pytest

from app.services.scene_detector import SceneDetector

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_VIDEO = FIXTURES_DIR / "test_30s.mp4"


@pytest.fixture
def detector():
    return SceneDetector()


class TestDetect:
    def test_returns_scene_list(self, detector):
        scenes = detector.detect(str(TEST_VIDEO))
        assert isinstance(scenes, list)
        assert len(scenes) >= 1
        for scene in scenes:
            assert "start_time" in scene
            assert "end_time" in scene
            assert isinstance(scene["start_time"], float)
            assert isinstance(scene["end_time"], float)
            assert scene["end_time"] > scene["start_time"]

    def test_scenes_cover_full_video(self, detector):
        scenes = detector.detect(str(TEST_VIDEO))
        assert scenes[0]["start_time"] == 0.0
        # Last scene should end near 30s
        assert scenes[-1]["end_time"] >= 28.0

    def test_nonexistent_file_raises(self, detector):
        with pytest.raises(FileNotFoundError):
            detector.detect("/nonexistent/video.mp4")

    def test_saves_scenes_json(self, detector, tmp_path):
        scenes = detector.detect(str(TEST_VIDEO), output_dir=str(tmp_path))
        scenes_file = tmp_path / "scenes.json"
        assert scenes_file.exists()
        saved = json.loads(scenes_file.read_text())
        assert saved == scenes

    def test_no_short_scenes(self, detector):
        scenes = detector.detect(str(TEST_VIDEO))
        for scene in scenes:
            duration = scene["end_time"] - scene["start_time"]
            assert duration >= SceneDetector.MIN_SCENE_DURATION

    def test_explicit_threshold_is_not_replaced_by_default(self, detector, monkeypatch):
        captured = {}

        class _FakeTimecode:
            def __init__(self, seconds: float):
                self._seconds = seconds

            def get_seconds(self) -> float:
                return self._seconds

        class _FakeVideo:
            def __init__(self):
                self.duration = _FakeTimecode(12.0)

        class _FakeSceneManager:
            def add_detector(self, detector):
                captured["detector"] = detector

            def detect_scenes(self, video):
                captured["video"] = video

            def get_scene_list(self):
                return []

        monkeypatch.setattr(
            "app.services.scene_detector.open_video", lambda _: _FakeVideo()
        )
        monkeypatch.setattr(
            "app.services.scene_detector.SceneManager", _FakeSceneManager
        )
        monkeypatch.setattr(
            "app.services.scene_detector.ContentDetector",
            lambda threshold: {"threshold": threshold},
        )

        scenes = detector.detect(str(TEST_VIDEO), threshold=0.0)

        assert captured["detector"] == {"threshold": 0.0}
        assert scenes == [{"start_time": 0.0, "end_time": 12.0}]
