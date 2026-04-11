"""Tests for FFmpegBuilder."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.ffmpeg_builder import FFmpegBuilder

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_VIDEO = FIXTURES_DIR / "test_30s.mp4"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_BGM = ASSETS_DIR / "default_bgm.mp3"
DEFAULT_WATERMARK = ASSETS_DIR / "watermark.png"

ffmpeg_available = shutil.which("ffmpeg") is not None


@pytest.fixture
def builder():
    return FFmpegBuilder()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestBuildCutCommand:
    def test_contains_ss_flag(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 10.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-ss" in cmd
        idx = cmd.index("-ss")
        assert cmd[idx + 1] == "10.0"

    def test_contains_duration_flag(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 5.0, 60.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-t" in cmd
        idx = cmd.index("-t")
        assert cmd[idx + 1] == "60.0"

    def test_contains_subtitles_filter(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "subtitles=" in cmd_str

    def test_does_not_embed_force_style_in_filter(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "force_style=" not in cmd_str

    def test_contains_overlay_filter(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "overlay=W-w-15:15" in cmd_str

    def test_contains_amix_filter(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "amix=inputs=2" in cmd_str

    def test_uses_libx264(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "libx264" in cmd

    def test_uses_preset_fast(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-preset" in cmd
        idx = cmd.index("-preset")
        assert cmd[idx + 1] == "fast"

    def test_does_not_contain_c_copy(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "-c copy" not in cmd_str
        assert "-c:v" in cmd
        assert "copy" not in [
            cmd[i + 1] for i in range(len(cmd) - 1) if cmd[i] == "-c:v"
        ]

    def test_contains_crf_23(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-crf" in cmd
        idx = cmd.index("-crf")
        assert cmd[idx + 1] == "23"

    def test_contains_aac_audio(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-c:a" in cmd
        idx = cmd.index("-c:a")
        assert cmd[idx + 1] == "aac"

    def test_contains_overwrite_flag(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-y" in cmd

    def test_output_path_at_end(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert cmd[-1] == "out.mp4"

    def test_subtitles_filter_uses_absolute_srt_path(self, builder, tmp_dir):
        srt_path = str((tmp_dir / "sub.srt").resolve())
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, srt_path, "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert f"subtitles=filename={srt_path}" in cmd_str

    def test_bgm_volume_025(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "volume=0.25" in cmd_str

    def test_filter_complex_present(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, "sub.srt", "bgm.mp3", "wm.png", "out.mp4"
        )
        assert "-filter_complex" in cmd

    def test_can_build_command_without_subtitles(self, builder):
        cmd = builder.build_cut_command(
            "input.mp4", 0.0, 30.0, None, "bgm.mp3", "wm.png", "out.mp4"
        )
        cmd_str = " ".join(cmd)
        assert "subtitles=" not in cmd_str
        assert "overlay=W-w-15:15" in cmd_str


class TestBuildThumbnailCommand:
    def test_contains_ss(self, builder):
        cmd = builder.build_thumbnail_command("input.mp4", 5.0, "thumb.jpg")
        assert "-ss" in cmd
        idx = cmd.index("-ss")
        assert cmd[idx + 1] == "5.0"

    def test_output_is_jpg(self, builder):
        cmd = builder.build_thumbnail_command("input.mp4", 5.0, "thumb.jpg")
        assert cmd[-1] == "thumb.jpg"

    def test_single_frame(self, builder):
        cmd = builder.build_thumbnail_command("input.mp4", 5.0, "thumb.jpg")
        assert "-vframes" in cmd
        idx = cmd.index("-vframes")
        assert cmd[idx + 1] == "1"


class TestFallbackBehavior:
    def test_retries_without_subtitles_when_first_export_fails(self, builder, tmp_dir):
        output_path = str(tmp_dir / "clip.mp4")
        thumb_path = str(tmp_dir / "thumb.jpg")
        srt_path = str(tmp_dir / "clip.srt")
        Path(srt_path).write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
        )

        segment = {"start_time": 0.0, "end_time": 5.0}

        fail = MagicMock(returncode=183, stderr="subtitle failed")
        ok = MagicMock(returncode=0, stderr="")
        thumb_ok = MagicMock(returncode=0, stderr="")

        with patch(
            "app.services.ffmpeg_builder.subprocess.run",
            side_effect=[fail, ok, thumb_ok],
        ) as mock_run:
            builder.process_clip(
                input_path="input.mp4",
                segment=segment,
                srt_path=srt_path,
                bgm_path="bgm.mp3",
                watermark_path="wm.png",
                output_path=output_path,
                thumbnail_path=thumb_path,
            )

        first_cmd = mock_run.call_args_list[0].args[0]
        second_cmd = mock_run.call_args_list[1].args[0]
        assert "subtitles=" in " ".join(first_cmd)
        assert "subtitles=" not in " ".join(second_cmd)


@pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg not installed")
class TestProcessClip:
    def test_process_clip_with_test_video(self, builder, tmp_dir):
        if not TEST_VIDEO.exists():
            pytest.skip("test_30s.mp4 not found")

        srt_path = tmp_dir / "test.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:05,000\nTest subtitle\n\n",
            encoding="utf-8",
        )

        output_path = str(tmp_dir / "clip.mp4")
        thumb_path = str(tmp_dir / "thumb.jpg")

        segment = {"start_time": 0.0, "end_time": 5.0, "text": "Test"}

        result = builder.process_clip(
            input_path=str(TEST_VIDEO),
            segment=segment,
            srt_path=str(srt_path),
            bgm_path=str(DEFAULT_BGM),
            watermark_path=str(DEFAULT_WATERMARK),
            output_path=output_path,
            thumbnail_path=thumb_path,
        )

        assert Path(result["output_path"]).exists()
        assert result["duration"] == 5.0
