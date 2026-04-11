"""Tests for SRTGenerator."""

import tempfile
from pathlib import Path

import pytest

from app.services.srt_generator import SRTGenerator


@pytest.fixture
def generator():
    return SRTGenerator()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestFormatTimestamp:
    def test_zero(self, generator):
        assert generator._format_timestamp(0.0) == "00:00:00,000"

    def test_simple_seconds(self, generator):
        assert generator._format_timestamp(5.0) == "00:00:05,000"

    def test_milliseconds(self, generator):
        assert generator._format_timestamp(1.5) == "00:00:01,500"

    def test_over_one_hour(self, generator):
        assert generator._format_timestamp(3661.5) == "01:01:01,500"

    def test_minutes_and_seconds(self, generator):
        assert generator._format_timestamp(125.123) == "00:02:05,123"

    def test_negative_clamped_to_zero(self, generator):
        assert generator._format_timestamp(-5.0) == "00:00:00,000"

    def test_large_value(self, generator):
        assert generator._format_timestamp(36000.0) == "10:00:00,000"

    def test_rounding(self, generator):
        assert generator._format_timestamp(1.9995) == "00:00:02,000"


class TestGenerate:
    def test_single_segment(self, generator, tmp_dir):
        segments = [{"text": "Hello world", "start_time": 1.0, "end_time": 5.0}]
        output = str(tmp_dir / "test.srt")
        result = generator.generate(segments, output)

        content = Path(result).read_text(encoding="utf-8")
        assert "1\n" in content
        assert "00:00:01,000 --> 00:00:05,000" in content
        assert "Hello world" in content

    def test_multiple_segments_correct_indices(self, generator, tmp_dir):
        segments = [
            {"text": "First", "start_time": 0.0, "end_time": 3.0},
            {"text": "Second", "start_time": 4.0, "end_time": 7.0},
            {"text": "Third", "start_time": 8.0, "end_time": 12.0},
        ]
        output = str(tmp_dir / "multi.srt")
        generator.generate(segments, output)

        content = Path(output).read_text(encoding="utf-8")
        assert "1\n" in content
        assert "2\n" in content
        assert "3\n" in content
        assert "First" in content
        assert "Second" in content
        assert "Third" in content

    def test_empty_segments_produces_empty_file(self, generator, tmp_dir):
        output = str(tmp_dir / "empty.srt")
        result = generator.generate([], output)

        content = Path(result).read_text(encoding="utf-8")
        assert content == ""

    def test_segment_with_empty_text_skipped(self, generator, tmp_dir):
        segments = [
            {"text": "Visible", "start_time": 0.0, "end_time": 3.0},
            {"text": "", "start_time": 4.0, "end_time": 7.0},
            {"text": "Also visible", "start_time": 8.0, "end_time": 12.0},
        ]
        output = str(tmp_dir / "skip.srt")
        generator.generate(segments, output)

        content = Path(output).read_text(encoding="utf-8")
        assert "Visible" in content
        assert "Also visible" in content
        assert "1\n" in content
        assert "2\n" in content
        assert "3\n" not in content

    def test_srt_format_structure(self, generator, tmp_dir):
        segments = [{"text": "Test line", "start_time": 1.0, "end_time": 5.0}]
        output = str(tmp_dir / "format.srt")
        generator.generate(segments, output)

        content = Path(output).read_text(encoding="utf-8")
        blocks = content.strip().split("\n\n")
        assert len(blocks) == 1
        lines = blocks[0].split("\n")
        assert lines[0] == "1"
        assert "-->" in lines[1]
        assert lines[2] == "Test line"

    def test_creates_parent_directories(self, generator, tmp_dir):
        output = str(tmp_dir / "nested" / "deep" / "test.srt")
        segments = [{"text": "Deep", "start_time": 0.0, "end_time": 1.0}]
        result = generator.generate(segments, output)
        assert Path(result).exists()

    def test_returns_absolute_path(self, generator, tmp_dir):
        output = str(tmp_dir / "abs.srt")
        result = generator.generate([], output)
        assert Path(result).is_absolute()
