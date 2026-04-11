"""Frame extraction within candidate scene regions using ffmpeg."""

import json
import subprocess
from pathlib import Path


class FrameExtractor:
    """Extracts frames at 1fps ONLY within candidate scene regions."""

    def extract(
        self,
        video_path: str,
        scenes: list[dict[str, float]],
        output_dir: str,
        sample_fps: int = 1,
    ) -> list[dict[str, str | float | int]]:
        """
        Extract frames at 1fps within each scene region.

        Args:
            video_path: Path to MP4 file.
            scenes: List of scene dicts with start_time/end_time.
            output_dir: Directory to save extracted frames.

        Returns:
            List of frame info dicts: [{path, timestamp, scene_idx}]
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        all_frames: list[dict[str, str | float | int]] = []

        for scene_idx, scene in enumerate(scenes):
            start = scene["start_time"]
            end = scene["end_time"]
            prefix = f"scene{scene_idx:03d}"

            scene_out = out / prefix
            scene_out.mkdir(parents=True, exist_ok=True)

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-to",
                str(end),
                "-i",
                video_path,
                "-vf",
                f"fps={sample_fps}",
                "-q:v",
                "2",
                str(scene_out / "frame_%05d.jpg"),
            ]

            subprocess.run(cmd, capture_output=True, timeout=300, check=True)

            for jpg in sorted(scene_out.glob("frame_*.jpg")):
                # Parse timestamp from frame number (fps=N → frame K = start + (K-1)/N seconds)
                frame_num = int(jpg.stem.split("_")[1])
                timestamp = start + ((frame_num - 1) / sample_fps)
                all_frames.append(
                    {
                        "path": str(jpg),
                        "timestamp": round(timestamp, 3),
                        "scene_idx": scene_idx,
                    }
                )

        (out / "frames.json").write_text(
            json.dumps(all_frames, ensure_ascii=False, indent=2)
        )

        return all_frames
