from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.faster_whisper_client import FasterWhisperClient


class TestFasterWhisperClient:
    def test_transcribe_returns_normalized_segments(self):
        client = FasterWhisperClient(
            model_size="small", device="cpu", compute_type="int8"
        )

        fake_segments = [
            SimpleNamespace(start=0.0, end=1.2, text="  第一段  "),
            SimpleNamespace(start=1.2, end=2.8, text=""),
            SimpleNamespace(start=2.8, end=4.5, text="第二段"),
        ]
        fake_info = SimpleNamespace(language="zh", duration=4.5)
        fake_chunks = [
            {"path": "/tmp/chunk_0000.wav", "start_offset": 0.0, "duration": 4.5}
        ]
        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = (fake_segments, fake_info)

        with (
            patch.object(client, "_split_audio", return_value=fake_chunks),
            patch.object(client, "_get_model", return_value=mock_instance),
            patch(
                "app.services.faster_whisper_client.tempfile.TemporaryDirectory"
            ) as mock_td,
        ):
            mock_td.return_value.__enter__ = MagicMock(return_value="/tmp")
            mock_td.return_value.__exit__ = MagicMock(return_value=False)

            result = client.transcribe("/tmp/test.wav")

        assert result == [
            {"text": "第一段", "start_time": 0.0, "end_time": 1.2},
            {"text": "第二段", "start_time": 2.8, "end_time": 4.5},
        ]

    def test_health_check_returns_true_when_model_loads(self):
        with patch.object(FasterWhisperClient, "_get_model", return_value=MagicMock()):
            client = FasterWhisperClient()
            assert client.health_check() is True
