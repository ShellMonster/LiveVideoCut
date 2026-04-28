import json

import pytest


TASK_ID = "d4e5f6a7-b8c9-0123-def4-345678901234"


@pytest.fixture(autouse=True)
def _setup_commerce(tmp_path, monkeypatch):
    task_dir = tmp_path / TASK_ID
    clips_dir = task_dir / "clips"
    covers_dir = task_dir / "covers"
    commerce_dir = task_dir / "commerce" / "clip_001"
    clips_dir.mkdir(parents=True)
    covers_dir.mkdir(parents=True)
    commerce_dir.mkdir(parents=True)

    (clips_dir / "clip_001.mp4").write_bytes(b"video-data")
    (covers_dir / "clip_001.jpg").write_bytes(b"cover-data")
    (clips_dir / "clip_001_meta.json").write_text(
        json.dumps(
            {
                "product_name": "米白针织连衣裙",
                "duration": 28.5,
                "start_time": 10,
                "end_time": 38.5,
                "confidence": 0.86,
            },
            ensure_ascii=False,
        )
    )
    (commerce_dir / "product_analysis.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "provider": "gemini",
                "confidence": 0.91,
                "product_type": "连衣裙",
                "visible_attributes": {"color": "米白色", "fit": "修身中长款"},
                "selling_points": ["通勤", "显瘦"],
                "uncertain_fields": ["材质"],
                "updated_at": "2026-04-28T00:00:00",
            },
            ensure_ascii=False,
        )
    )

    monkeypatch.setattr("app.api.commerce.UPLOAD_DIR", tmp_path)


@pytest.mark.anyio
async def test_get_clip_commerce_asset_returns_clip_and_saved_analysis(client):
    response = await client.get(f"/api/commerce/clips/{TASK_ID}/clip_001")

    assert response.status_code == 200
    data = response.json()
    assert data["clip"]["product_name"] == "米白针织连衣裙"
    assert data["clip"]["thumbnail_url"] == f"/api/clips/{TASK_ID}/clip_001/thumbnail"
    assert data["analysis"]["status"] == "completed"
    assert data["analysis"]["product_type"] == "连衣裙"
    assert data["copywriting"]["status"] == "not_started"
    assert data["images"]["items"][0]["key"] == "model_front"


@pytest.mark.anyio
async def test_get_clip_commerce_asset_rejects_invalid_ids(client):
    response = await client.get("/api/commerce/clips/not-a-task-id/clip_001")

    assert response.status_code == 400


@pytest.mark.anyio
async def test_get_clip_commerce_asset_returns_not_found(client):
    response = await client.get(f"/api/commerce/clips/{TASK_ID}/clip_999")

    assert response.status_code == 404
