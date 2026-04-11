"""Tests for FunASRClient — all HTTP calls mocked."""

import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from app.services.funasr_client import FunASRClient


class TestHealthCheck:
    def test_returns_true_when_service_reachable(self):
        client = FunASRClient(funasr_url="http://localhost:10095")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.services.funasr_client.httpx.get", return_value=mock_response):
            assert client.health_check() is True

    def test_returns_false_when_service_unreachable(self):
        client = FunASRClient(funasr_url="http://localhost:10095")

        with patch(
            "app.services.funasr_client.httpx.get",
            side_effect=ConnectionError("Connection refused"),
        ):
            assert client.health_check() is False


class TestSplitAudio:
    def test_creates_correct_chunk_count(self, tmp_path):
        client = FunASRClient()

        mock_probe = MagicMock()
        mock_probe.stdout = "5400.0\n"

        call_count = [0]

        def fake_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_probe
            cmd = args[0]
            output_path = cmd[-1]
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "w") as f:
                f.write("fake audio")
            return MagicMock(returncode=0)

        with patch("app.services.funasr_client.subprocess.run", side_effect=fake_run):
            chunks = client._split_audio(
                str(tmp_path / "test.wav"),
                chunk_duration=1800,
                overlap=3.0,
                output_dir=str(tmp_path / "chunks"),
            )

            assert len(chunks) == 3
            assert chunks[0]["start_offset"] == 0.0
            assert chunks[1]["start_offset"] == 1800.0
            assert chunks[2]["start_offset"] == 3600.0

    def test_returns_empty_on_probe_failure(self, tmp_path):
        client = FunASRClient()

        with patch(
            "app.services.funasr_client.subprocess.run",
            side_effect=FileNotFoundError("ffprobe not found"),
        ):
            chunks = client._split_audio(
                str(tmp_path / "test.wav"),
                chunk_duration=1800,
                overlap=3.0,
                output_dir=str(tmp_path / "chunks"),
            )
            assert chunks == []


class TestTranscribeChunk:
    def test_calls_official_recognition_endpoint(self):
        client = FunASRClient(funasr_url="http://funasr:10095")

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "", "sentences": [], "code": 0}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("builtins.open", mock_open(read_data=b"fake audio")),
            patch(
                "app.services.funasr_client.httpx.post", return_value=mock_response
            ) as mock_post,
        ):
            client._transcribe_chunk("/fake/path.wav")

        assert mock_post.call_args.args[0] == "http://funasr:10095/recognition"

    def test_returns_segments_from_dict_response(self):
        client = FunASRClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "大家好欢迎来到直播间",
            "start": 0.0,
            "end": 5.0,
            "segments": [
                {"text": "这款连衣裙", "start": 5.0, "end": 8.0},
                {"text": "非常好看", "start": 8.0, "end": 10.0},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch("builtins.open", mock_open(read_data=b"fake audio")),
            patch("app.services.funasr_client.httpx.post", return_value=mock_response),
        ):
            segments = client._transcribe_chunk("/fake/path.wav")

            assert len(segments) == 3
            assert segments[0]["text"] == "大家好欢迎来到直播间"
            assert segments[1]["text"] == "这款连衣裙"
            assert segments[1]["start_time"] == 5.0
            assert segments[2]["start_time"] == 8.0

    def test_returns_segments_from_sentences_response(self):
        client = FunASRClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "大家好 这款连衣裙 非常好看",
            "sentences": [
                {"text": "大家好", "start": 0.0, "end": 1.2},
                {"text": "这款连衣裙", "start": 1.2, "end": 3.4},
            ],
            "code": 0,
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch("builtins.open", mock_open(read_data=b"fake audio")),
            patch("app.services.funasr_client.httpx.post", return_value=mock_response),
        ):
            segments = client._transcribe_chunk("/fake/path.wav")

        assert len(segments) == 3
        assert segments[0]["text"] == "大家好 这款连衣裙 非常好看"
        assert segments[1]["text"] == "大家好"
        assert segments[1]["start_time"] == 0.0
        assert segments[2]["text"] == "这款连衣裙"
        assert segments[2]["end_time"] == 3.4

    def test_returns_empty_on_api_failure(self):
        client = FunASRClient()

        with (
            patch("builtins.open", mock_open(read_data=b"fake audio")),
            patch(
                "app.services.funasr_client.httpx.post",
                side_effect=ConnectionError("API error"),
            ),
        ):
            segments = client._transcribe_chunk("/fake/path.wav")
            assert segments == []


class TestTranscribe:
    def test_with_mocked_api_returns_merged_transcript(self, tmp_path):
        client = FunASRClient()

        fake_chunks = [
            {"path": "/fake/chunk_0.wav", "start_offset": 0.0, "duration": 1800.0},
            {"path": "/fake/chunk_1.wav", "start_offset": 1800.0, "duration": 1800.0},
        ]

        chunk1_transcript = [
            {"text": "第一段话", "start_time": 0.0, "end_time": 5.0},
            {"text": "重叠区域前", "start_time": 1795.0, "end_time": 1798.0},
        ]
        chunk2_transcript = [
            {"text": "重叠区域后", "start_time": 0.0, "end_time": 3.0},
            {"text": "第二段话", "start_time": 5.0, "end_time": 10.0},
        ]

        real_tmp = str(tmp_path / "chunks")
        os.makedirs(real_tmp, exist_ok=True)

        with (
            patch.object(client, "_split_audio", return_value=fake_chunks),
            patch.object(
                client,
                "_transcribe_chunk",
                side_effect=[chunk1_transcript, chunk2_transcript],
            ),
            patch("app.services.funasr_client.tempfile.TemporaryDirectory") as mock_td,
        ):
            mock_td.return_value.__enter__ = MagicMock(return_value=real_tmp)
            mock_td.return_value.__exit__ = MagicMock(return_value=False)

            result = client.transcribe(str(tmp_path / "test.wav"))

            assert isinstance(result, list)
            assert len(result) > 0
            texts = [r["text"] for r in result]
            assert "第一段话" in texts
            assert "第二段话" in texts
