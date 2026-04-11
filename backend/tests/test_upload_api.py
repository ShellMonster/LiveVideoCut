# pyright: reportArgumentType=false

import json

import pytest


@pytest.mark.anyio
async def test_upload_persists_resolved_settings_snapshot(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.api.upload.UPLOAD_DIR", tmp_path)

    metadata = {
        "duration": 123.4,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "codec": "h264",
        "audio_codec": "aac",
    }
    queued: list[tuple[str, str]] = []

    class FakeValidator:
        def validate_format(self, filename: str) -> None:
            assert filename == "demo.mp4"

        def validate_size(self, file_size: int) -> None:
            assert file_size > 0

        def validate_codec(self, file_path: str) -> None:
            assert file_path.endswith("original.mp4")

        def validate_audio(self, file_path: str) -> None:
            assert file_path.endswith("original.mp4")

        def get_metadata(self, file_path: str) -> dict[str, float | int | str]:
            assert file_path.endswith("original.mp4")
            return metadata

    class FakeStartPipeline:
        def delay(self, task_id: str, file_path: str) -> None:
            queued.append((task_id, file_path))

    monkeypatch.setattr("app.api.upload.validator", FakeValidator())
    monkeypatch.setattr("app.api.upload.start_pipeline", FakeStartPipeline())

    response = await client.post(
        "/api/upload",
        files={
            "file": ("demo.mp4", b"fake video bytes", "video/mp4"),
            "settings_json": (
                None,
                json.dumps(
                    {
                        "api_key": "glm-key",
                        "vlm_provider": "glm",
                        "candidate_looseness": "loose",
                        "subtitle_mode": "basic",
                        "ignored_frontend_key": "keep-tolerant",
                    }
                ),
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    task_id = payload["task_id"]
    task_dir = tmp_path / task_id

    assert payload["metadata"] == metadata
    assert (task_dir / "original.mp4").read_bytes() == b"fake video bytes"
    assert json.loads((task_dir / "meta.json").read_text()) == metadata

    settings_snapshot = json.loads((task_dir / "settings.json").read_text())
    assert settings_snapshot == {
        "api_key": "glm-key",
        "vlm_provider": "glm",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-5v-turbo",
        "scene_threshold": 27.0,
        "frame_sample_fps": 2,
        "recall_cooldown_seconds": 15,
        "candidate_looseness": "loose",
        "min_segment_duration_seconds": 25,
        "dedupe_window_seconds": 90,
        "allow_returned_product": True,
        "review_strictness": "standard",
        "review_mode": "segment_multiframe",
        "max_candidate_count": 20,
        "subtitle_mode": "basic",
        "subtitle_position": "bottom",
        "subtitle_template": "clean",
        "custom_position_y": None,
    }
    assert queued == [(task_id, str(task_dir / "original.mp4"))]
