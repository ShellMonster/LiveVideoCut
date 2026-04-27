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
    # api_key 等敏感字段已从 settings.json 移到 secrets.json
    assert "api_key" not in settings_snapshot
    secrets_snapshot = json.loads((task_dir / "secrets.json").read_text())
    assert secrets_snapshot["api_key"] == "glm-key"
    assert settings_snapshot["enable_vlm"] is True
    assert settings_snapshot["export_mode"] == "smart"
    assert settings_snapshot["vlm_provider"] == "glm"
    assert settings_snapshot["api_base"] == "https://open.bigmodel.cn/api/paas/v4"
    assert settings_snapshot["model"] == "glm-5v-turbo"
    assert settings_snapshot["frame_sample_fps"] == 0.5
    assert settings_snapshot["candidate_looseness"] == "loose"
    assert settings_snapshot["subtitle_mode"] == "basic"
    assert queued == [(task_id, str(task_dir / "original.mp4"))]


@pytest.mark.anyio
async def test_upload_uses_env_api_key_when_settings_payload_has_blank_key(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.api.upload.UPLOAD_DIR", tmp_path)
    monkeypatch.setenv("VLM_API_KEY", "env-fallback-key")

    metadata = {
        "duration": 88.0,
        "width": 1280,
        "height": 720,
        "fps": 25.0,
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
                        "api_key": "",
                        "vlm_provider": "qwen",
                    }
                ),
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    task_dir = tmp_path / payload["task_id"]
    settings_snapshot = json.loads((task_dir / "settings.json").read_text())
    # env-fallback-key 写入 secrets.json 而非 settings.json
    secrets_snapshot = json.loads((task_dir / "secrets.json").read_text())
    assert secrets_snapshot["api_key"] == "env-fallback-key"
    assert settings_snapshot["export_mode"] == "smart"
    assert queued == [(payload["task_id"], str(task_dir / "original.mp4"))]


@pytest.mark.anyio
async def test_upload_accepts_blank_api_key_when_vlm_disabled(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.api.upload.UPLOAD_DIR", tmp_path)

    metadata = {
        "duration": 88.0,
        "width": 1280,
        "height": 720,
        "fps": 25.0,
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
                        "enable_vlm": False,
                        "api_key": "",
                        "vlm_provider": "qwen",
                    }
                ),
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    task_dir = tmp_path / payload["task_id"]
    settings_snapshot = json.loads((task_dir / "settings.json").read_text())

    assert settings_snapshot["enable_vlm"] is False
    assert "api_key" not in settings_snapshot
    assert settings_snapshot["export_mode"] == "no_vlm"
    assert queued == [(payload["task_id"], str(task_dir / "original.mp4"))]
