from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from app.services.cover_selector import _sample_frames, select_cover_frame


def test_sample_frames_uses_single_ffmpeg_process_for_multiple_candidates(tmp_path):
    created_paths: list[Path] = []

    def fake_run(cmd, capture_output, timeout, check):
        output_pattern = cmd[-1]
        output_dir = Path(output_pattern).parent
        for idx in range(1, 4):
            frame_path = output_dir / f"frame_{idx:05d}.jpg"
            frame_path.write_bytes(b"frame")
            created_paths.append(frame_path)
        return MagicMock(returncode=0)

    fake_img = np.zeros((10, 10, 3), dtype=np.uint8)

    with patch("app.services.cover_selector.subprocess.run", side_effect=fake_run) as mock_run:
        with patch("app.services.cover_selector.cv2.imread", return_value=fake_img):
            frames = _sample_frames("input.mp4", 10.0, 40.0, max_frames=3)

    assert len(mock_run.call_args_list) == 1
    assert [ts for ts, _ in frames] == [10.0, 20.0, 30.0]
    assert len(created_paths) == 3


def test_sample_frames_falls_back_to_per_timestamp_extraction_when_batch_fails(tmp_path):
    run_calls = 0

    def fake_run(cmd, capture_output, timeout, check):
        nonlocal run_calls
        run_calls += 1
        if run_calls == 1:
            raise RuntimeError("batch failed")
        Path(cmd[-1]).write_bytes(b"frame")
        return MagicMock(returncode=0)

    fake_img = np.zeros((10, 10, 3), dtype=np.uint8)

    with patch("app.services.cover_selector.subprocess.run", side_effect=fake_run) as mock_run:
        with patch("app.services.cover_selector.cv2.imread", return_value=fake_img):
            frames = _sample_frames("input.mp4", 10.0, 40.0, max_frames=3)

    assert len(mock_run.call_args_list) == 4
    assert [ts for ts, _ in frames] == [10.0, 20.0, 30.0]


def test_select_cover_frame_uses_pre_sampled_frames_without_ffmpeg(tmp_path):
    frame_paths = []
    for idx, ts in enumerate([8.0, 10.0, 20.0, 30.0, 42.0]):
        frame_path = tmp_path / f"frame_{idx:05d}.jpg"
        frame_path.write_bytes(f"frame-{ts}".encode())
        frame_paths.append(frame_path)

    frame_records = [
        {"timestamp": ts, "path": str(path), "scene_idx": 0}
        for ts, path in zip([8.0, 10.0, 20.0, 30.0, 42.0], frame_paths)
    ]
    output_path = tmp_path / "cover.jpg"
    fake_img = np.zeros((10, 10, 3), dtype=np.uint8)

    with patch("app.services.cover_selector.subprocess.run") as mock_run:
        with patch("app.services.cover_selector.cv2.imread", return_value=fake_img):
            with patch("app.services.cover_selector._score_quality", side_effect=[0.2, 0.9, 0.3]):
                with patch("app.services.cover_selector._score_content_first", return_value=(1.0, [])):
                    with patch("app.services.cover_selector._detect_occluders", return_value=False):
                        best_ts = select_cover_frame(
                            "input.mp4",
                            10.0,
                            40.0,
                            max_frames=3,
                            output_path=str(output_path),
                            pre_sampled_frames=frame_records,
                        )

    assert best_ts == 20.0
    assert output_path.read_bytes() == frame_paths[2].read_bytes()
    assert len(mock_run.call_args_list) == 0


def test_select_cover_frame_tops_up_when_pre_sampled_frames_are_sparse(tmp_path):
    pre_sampled_path = tmp_path / "pre_sampled.jpg"
    pre_sampled_path.write_bytes(b"pre-sampled")
    output_path = tmp_path / "cover.jpg"
    fake_img = np.zeros((10, 10, 3), dtype=np.uint8)

    def fake_run(cmd, capture_output, timeout, check):
        output_pattern = cmd[-1]
        output_dir = Path(output_pattern).parent
        for idx in range(1, 4):
            (output_dir / f"frame_{idx:05d}.jpg").write_bytes(f"top-up-{idx}".encode())
        return MagicMock(returncode=0)

    def fake_imread(path):
        return fake_img if Path(path).exists() else None

    frame_records = [{"timestamp": 12.0, "path": str(pre_sampled_path), "scene_idx": 0}]

    with patch("app.services.cover_selector.subprocess.run", side_effect=fake_run) as mock_run:
        with patch("app.services.cover_selector.cv2.imread", side_effect=fake_imread):
            with patch("app.services.cover_selector._score_quality", side_effect=[0.2, 0.9, 0.3, 0.1]):
                with patch("app.services.cover_selector._score_content_first", return_value=(1.0, [])):
                    with patch("app.services.cover_selector._detect_occluders", return_value=False):
                        best_ts = select_cover_frame(
                            "input.mp4",
                            10.0,
                            40.0,
                            max_frames=4,
                            output_path=str(output_path),
                            pre_sampled_frames=frame_records,
                        )

    assert best_ts == 10.0
    assert output_path.read_bytes() == b"top-up-1"
    assert len(mock_run.call_args_list) == 1
