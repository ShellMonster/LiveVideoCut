import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

UPLOAD_DIR = Path("uploads")
FIXTURE_TASK = "test-task-clips"
CLIPS_DIR = UPLOAD_DIR / FIXTURE_TASK / "clips"


@pytest.fixture(autouse=True)
def _setup_clips(tmp_path, monkeypatch):
    task_dir = tmp_path / FIXTURE_TASK
    clips_dir = task_dir / "clips"
    clips_dir.mkdir(parents=True)

    for i in range(1, 4):
        idx = f"{i:03d}"
        (clips_dir / f"clip_{idx}.mp4").write_bytes(b"fake-mp4-data")
        (clips_dir / f"clip_{idx}_thumb.jpg").write_bytes(b"fake-jpg-data")
        meta = {
            "product_name": f"商品 {i}",
            "duration": 15.0 + i,
            "start_time": 10.0 * i,
            "end_time": 10.0 * i + 15.0 + i,
            "confidence": 0.9,
        }
        (clips_dir / f"clip_{idx}_meta.json").write_text(json.dumps(meta))

    monkeypatch.setattr("app.api.clips.UPLOAD_DIR", tmp_path)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_list_clips(client):
    resp = await client.get(f"/api/tasks/{FIXTURE_TASK}/clips")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == FIXTURE_TASK
    assert data["total"] == 3
    assert len(data["clips"]) == 3

    clip = data["clips"][0]
    assert clip["product_name"] == "商品 1"
    assert clip["duration"] == 16.0
    assert clip["has_video"] is True
    assert clip["has_thumbnail"] is True


@pytest.mark.anyio
async def test_list_clips_not_found(client):
    resp = await client.get("/api/tasks/nonexistent/clips")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_download_clip(client):
    resp = await client.get(f"/api/clips/{FIXTURE_TASK}/clip_001/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert resp.content == b"fake-mp4-data"


@pytest.mark.anyio
async def test_download_clip_not_found(client):
    resp = await client.get(f"/api/clips/{FIXTURE_TASK}/clip_999/download")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_thumbnail(client):
    resp = await client.get(f"/api/clips/{FIXTURE_TASK}/clip_001/thumbnail")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == b"fake-jpg-data"


@pytest.mark.anyio
async def test_get_thumbnail_not_found(client):
    resp = await client.get(f"/api/clips/{FIXTURE_TASK}/clip_999/thumbnail")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_batch_download(client):
    ids = f"{FIXTURE_TASK}/clip_001,{FIXTURE_TASK}/clip_002"
    resp = await client.get(f"/api/clips/batch?ids={ids}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "clip_001.mp4" in names
        assert "clip_002.mp4" in names


@pytest.mark.anyio
async def test_batch_download_empty_ids(client):
    resp = await client.get("/api/clips/batch?ids=")
    assert resp.status_code == 400
