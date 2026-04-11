"""Scene detection using PySceneDetect ContentDetector."""

import json
from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video


class SceneDetector:
    """Uses PySceneDetect ContentDetector to find scene changes in video."""

    DEFAULT_THRESHOLD: float = 27.0
    MIN_SCENE_DURATION: float = 2.0  # seconds

    def detect(
        self,
        video_path: str,
        output_dir: str | None = None,
        threshold: float | None = None,
    ) -> list[dict[str, float]]:
        """
        Detect scene changes in a video file.

        Args:
            video_path: Path to MP4 file.
            output_dir: Optional directory to save scenes.json.
            threshold: ContentDetector threshold (default 27.0).

        Returns:
            List of scene dicts: [{start_time: float, end_time: float}]

        Raises:
            FileNotFoundError: If video_path does not exist.
        """
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        thresh = threshold if threshold is not None else self.DEFAULT_THRESHOLD
        video = open_video(str(path))
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=thresh))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        # Convert to our format
        scenes: list[dict[str, float]] = []
        for scene in scene_list:
            start_time = scene[0].get_seconds()
            end_time = scene[1].get_seconds()
            scenes.append({"start_time": start_time, "end_time": end_time})

        # Edge case: no scene changes → single scene spanning entire video
        if not scenes:
            duration_timecode = getattr(video, "duration", None)
            if duration_timecode is None:
                raise ValueError(f"Could not determine video duration for {video_path}")
            scenes = [{"start_time": 0.0, "end_time": duration_timecode.get_seconds()}]

        # Merge very short scenes (< 2s) with adjacent
        scenes = self._merge_short_scenes(scenes)

        # Optionally save to file
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / "scenes.json").write_text(
                json.dumps(scenes, ensure_ascii=False, indent=2)
            )

        return scenes

    def _merge_short_scenes(
        self, scenes: list[dict[str, float]]
    ) -> list[dict[str, float]]:
        """Merge scenes shorter than MIN_SCENE_DURATION with adjacent scene."""
        if len(scenes) <= 1:
            return scenes

        merged = [scenes[0]]
        for scene in scenes[1:]:
            duration = scene["end_time"] - scene["start_time"]
            if duration < self.MIN_SCENE_DURATION:
                # Merge with previous scene
                merged[-1]["end_time"] = scene["end_time"]
            else:
                merged.append(scene)

        return merged
