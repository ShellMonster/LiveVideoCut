import json
import zipfile
from io import BytesIO

import pytest


@pytest.fixture(autouse=True)
def _setup_assets(tmp_path, monkeypatch):
    task_dir = tmp_path / "c3d4e5f6-a7b8-9012-cdef-234567890123"
    clips_dir = task_dir / "clips"
    covers_dir = task_dir / "covers"
    clips_dir.mkdir(parents=True)
    covers_dir.mkdir(parents=True)

    (task_dir / "state.json").write_text(json.dumps({"state": "COMPLETED"}))
    (task_dir / "meta.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:00"}))
    (task_dir / "settings.json").write_text(json.dumps({"subtitle_mode": "basic"}))
    (task_dir / "review.json").write_text(
        json.dumps({"segments": {"clip_000": {"status": "approved"}}})
    )
    (clips_dir / "clip_000.mp4").write_bytes(b"video-data")
    (covers_dir / "clip_000.jpg").write_bytes(b"cover-data")
    (clips_dir / "clip_000_meta.json").write_text(
        json.dumps(
            {
                "product_name": "资产片段",
                "duration": 12.5,
                "start_time": 1,
                "end_time": 13.5,
                "confidence": 0.8,
            },
            ensure_ascii=False,
        )
    )

    waiting_dir = tmp_path / "waiting-task"
    waiting_dir.mkdir()
    (waiting_dir / "state.json").write_text(json.dumps({"state": "UPLOADED"}))

    monkeypatch.setattr("app.api.assets.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.api.system.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.api.tasks.UPLOAD_DIR", tmp_path)


@pytest.mark.anyio
async def test_clip_assets_include_review_status_and_file_size(client):
    response = await client.get("/api/assets/clips")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["approved"] == 1
    assert data["summary"]["downloadable"] == 1
    assert data["items"][0]["review_status"] == "approved"
    assert data["items"][0]["file_size"] == len(b"video-data")


@pytest.mark.anyio
async def test_clip_assets_filter_by_status(client):
    response = await client.get("/api/assets/clips?status=pending")

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.anyio
async def test_clip_assets_create_sqlite_index(client, tmp_path):
    response = await client.get("/api/assets/clips")

    assert response.status_code == 200
    assert (tmp_path / "index.sqlite3").exists()


@pytest.mark.anyio
async def test_clip_assets_search_duration_and_pagination(client):
    response = await client.get("/api/assets/clips?q=资产&duration=short&offset=0&limit=1")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["offset"] == 0
    assert data["limit"] == 1
    assert data["items"][0]["product_name"] == "资产片段"


@pytest.mark.anyio
async def test_task_list_summary_search_and_processing_filter(client):
    response = await client.get("/api/tasks?q=waiting&status=processing&offset=0&limit=1")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["summary"]["total"] == 2
    assert data["summary"]["completed"] == 1
    assert data["summary"]["uploaded"] == 1


@pytest.mark.anyio
async def test_review_patch_refreshes_clip_asset_index(client):
    tid = "c3d4e5f6-a7b8-9012-cdef-234567890123"
    patch_response = await client.patch(
        f"/api/tasks/{tid}/review/segments/clip_000",
        json={"status": "skipped"},
    )
    assert patch_response.status_code == 200

    response = await client.get("/api/assets/clips?status=skipped")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["review_status"] == "skipped"


@pytest.mark.anyio
async def test_system_resources_counts_task_states(client):
    response = await client.get("/api/system/resources")

    assert response.status_code == 200
    data = response.json()
    assert data["queue"]["completed"] == 1
    assert data["queue"]["waiting"] == 1
    assert data["clip_workers"] >= 1


@pytest.mark.anyio
async def test_task_events_and_artifact_download(client):
    tid = "c3d4e5f6-a7b8-9012-cdef-234567890123"
    events_response = await client.get(f"/api/tasks/{tid}/events")
    assert events_response.status_code == 200
    assert any(event["file"] == "review.json" for event in events_response.json()["events"])

    diagnostics_response = await client.get(f"/api/tasks/{tid}/diagnostics/export")
    assert diagnostics_response.status_code == 200
    assert diagnostics_response.headers["content-type"] == "application/json"

    zip_response = await client.get(f"/api/tasks/{tid}/artifacts.zip")
    assert zip_response.status_code == 200
    with zipfile.ZipFile(BytesIO(zip_response.content)) as zf:
        names = zf.namelist()
        assert "meta.json" in names
        assert "settings.json" in names
        assert "review.json" in names
        assert "clips/clip_000_meta.json" in names
        assert "clips/clip_000.mp4" not in names


@pytest.mark.anyio
async def test_delete_legacy_safe_task_id(client, tmp_path):
    await client.get("/api/tasks")
    response = await client.delete("/api/tasks/waiting-task")

    assert response.status_code == 200
    assert response.json()["task_id"] == "waiting-task"
    assert not (tmp_path / "waiting-task").exists()
    list_response = await client.get("/api/tasks?q=waiting")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0


@pytest.mark.anyio
async def test_delete_rejects_unsafe_task_id(client, tmp_path):
    response = await client.delete("/api/tasks/.waiting-task")

    assert response.status_code == 400
    assert (tmp_path / "waiting-task").exists()
