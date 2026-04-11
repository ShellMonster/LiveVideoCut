"""Tests for VideoValidator — validates MP4/H.264/audio/size."""

from pathlib import Path

import pytest

from app.services.validator import MAX_FILE_SIZE, ValidationError, VideoValidator

FIXTURES = Path(__file__).parent / "fixtures"
TEST_MP4 = str(FIXTURES / "test_30s.mp4")


@pytest.fixture
def validator():
    return VideoValidator()


# --- validate_format ---


class TestValidateFormat:
    def test_accepts_mp4(self, validator):
        validator.validate_format("video.mp4")

    def test_accepts_uppercase_extension(self, validator):
        validator.validate_format("video.MP4")

    def test_rejects_non_mp4(self, validator):
        with pytest.raises(ValidationError, match="Unsupported format"):
            validator.validate_format("video.avi")

    def test_rejects_no_extension(self, validator):
        with pytest.raises(ValidationError, match="Unsupported format"):
            validator.validate_format("video")


# --- validate_size ---


class TestValidateSize:
    def test_accepts_small_file(self, validator):
        validator.validate_size(1024)

    def test_accepts_exactly_20gb(self, validator):
        validator.validate_size(MAX_FILE_SIZE)

    def test_rejects_over_20gb(self, validator):
        with pytest.raises(ValidationError, match="too large"):
            validator.validate_size(MAX_FILE_SIZE + 1)


# --- validate_codec (requires ffprobe + real MP4) ---


class TestValidateCodec:
    def test_accepts_h264(self, validator):
        validator.validate_codec(TEST_MP4)

    def test_rejects_non_h264(self, validator, tmp_path):
        # Create a tiny file that ffprobe can read but isn't H.264
        fake = tmp_path / "fake.mp4"
        fake.write_bytes(b"\x00" * 1024)
        with pytest.raises(ValidationError):
            validator.validate_codec(str(fake))


# --- validate_audio ---


class TestValidateAudio:
    def test_accepts_with_audio(self, validator):
        validator.validate_audio(TEST_MP4)

    def test_rejects_no_audio(self, validator, tmp_path):
        fake = tmp_path / "noaudio.mp4"
        fake.write_bytes(b"\x00" * 1024)
        with pytest.raises(ValidationError):
            validator.validate_audio(str(fake))


# --- get_metadata ---


class TestGetMetadata:
    def test_extracts_metadata(self, validator):
        meta = validator.get_metadata(TEST_MP4)
        assert meta["codec"] == "h264"
        assert meta["duration"] > 0
        assert meta["width"] > 0
        assert meta["height"] > 0
        assert meta["fps"] > 0
        assert meta["audio_codec"] != "none"

    def test_rejects_no_video_stream(self, validator, tmp_path):
        fake = tmp_path / "novideo.mp4"
        fake.write_bytes(b"\x00" * 1024)
        with pytest.raises(ValidationError):
            validator.get_metadata(str(fake))
