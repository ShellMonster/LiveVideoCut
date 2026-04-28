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
    (task_dir / "settings.json").write_text(
        json.dumps(
            {
                "commerce_gemini_api_base": "https://gemini.example.com",
                "commerce_gemini_model": "gemini-test",
                "commerce_gemini_timeout_seconds": 90,
                "commerce_image_api_base": "https://openai.example.com/v1",
                "commerce_image_model": "gpt-image-2",
                "commerce_image_size": "1024x1536",
                "commerce_image_quality": "auto",
                "commerce_image_timeout_seconds": 120,
            },
            ensure_ascii=False,
        )
    )
    (task_dir / "secrets.json").write_text(
        json.dumps(
            {
                "commerce_gemini_api_key": "gemini-key",
                "commerce_image_api_key": "openai-key",
            },
            ensure_ascii=False,
        )
    )
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
    assert data["clip"]["preview_url"] == f"/api/clips/{TASK_ID}/clip_001/preview"
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


@pytest.mark.anyio
async def test_analyze_clip_cover_calls_gemini_and_saves_result(client, monkeypatch, tmp_path):
    class FakeGeminiClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def analyze_cover(self, image_path, product_hint):
            assert image_path == tmp_path / TASK_ID / "covers" / "clip_001.jpg"
            assert product_hint == "米白针织连衣裙"
            return {
                "confidence": 0.93,
                "product_type": "连衣裙",
                "visible_attributes": {"color": "米白色"},
                "selling_points": ["通勤"],
                "uncertain_fields": ["材质"],
            }

    monkeypatch.setattr("app.api.commerce.GeminiVisionClient", FakeGeminiClient)

    monkeypatch.setattr("app.tasks.pipeline.process_commerce_assets.delay", lambda *args: type("Result", (), {"id": "celery-1"})())

    response = await client.post(f"/api/commerce/clips/{TASK_ID}/clip_001/analyze")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["job"]["celery_id"] == "celery-1"

    from app.api.commerce import run_commerce_actions

    result = run_commerce_actions(TASK_ID, "clip_001", ["analyze"])
    assert result["analysis_status"] == "completed"
    saved = json.loads((tmp_path / TASK_ID / "commerce" / "clip_001" / "product_analysis.json").read_text())
    assert saved["confidence"] == 0.93


@pytest.mark.anyio
async def test_generate_clip_copywriting_calls_gemini_and_saves_result(client, monkeypatch, tmp_path):
    class FakeGeminiClient:
        def __init__(self, **kwargs):
            pass

        def generate_copywriting(self, analysis, product_hint):
            assert analysis["product_type"] == "连衣裙"
            return {
                "douyin": {"title": "米白连衣裙通勤穿搭", "description": "干净显气质", "hashtags": ["#通勤穿搭"]},
                "taobao": {"title": "米白针织连衣裙", "selling_points": ["通勤"], "detail_modules": ["效果示意"]},
            }

    monkeypatch.setattr("app.api.commerce.GeminiVisionClient", FakeGeminiClient)

    monkeypatch.setattr("app.tasks.pipeline.process_commerce_assets.delay", lambda *args: type("Result", (), {"id": "celery-2"})())

    response = await client.post(f"/api/commerce/clips/{TASK_ID}/clip_001/copywriting")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["job"]["celery_id"] == "celery-2"

    from app.api.commerce import run_commerce_actions

    run_commerce_actions(TASK_ID, "clip_001", ["copywriting"])
    saved = json.loads((tmp_path / TASK_ID / "commerce" / "clip_001" / "copywriting.json").read_text())
    assert saved["taobao"]["selling_points"] == ["通勤"]


@pytest.mark.anyio
async def test_generate_clip_images_calls_openai_and_serves_images(client, monkeypatch, tmp_path):
    class FakeOpenAIImageClient:
        def __init__(self, **kwargs):
            pass

        def generate_with_reference(self, prompt, image_path, *, size, quality):
            assert image_path == tmp_path / TASK_ID / "covers" / "clip_001.jpg"
            assert size == "1024x1536"
            assert quality == "auto"
            return b"png-data"

    monkeypatch.setattr("app.api.commerce.OpenAIImageClient", FakeOpenAIImageClient)

    monkeypatch.setattr("app.tasks.pipeline.process_commerce_assets.delay", lambda *args: type("Result", (), {"id": "celery-3"})())

    response = await client.post(f"/api/commerce/clips/{TASK_ID}/clip_001/images")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["job"]["celery_id"] == "celery-3"

    from app.api.commerce import run_commerce_actions

    result = run_commerce_actions(TASK_ID, "clip_001", ["images"])
    assert result["images_status"] == "completed"
    data = json.loads((tmp_path / TASK_ID / "commerce" / "clip_001" / "images.json").read_text())
    assert len(data["items"]) == 4
    assert data["items"][0]["url"].endswith("/model_front.png")

    image_response = await client.get(data["items"][0]["url"])
    assert image_response.status_code == 200
    assert image_response.content == b"png-data"


@pytest.mark.anyio
async def test_generate_single_clip_image_preserves_other_items(client, monkeypatch, tmp_path):
    class FakeOpenAIImageClient:
        def __init__(self, **kwargs):
            pass

        def generate_with_reference(self, prompt, image_path, *, size, quality):
            assert "侧面" in prompt
            return b"side-png-data"

    images_path = tmp_path / TASK_ID / "commerce" / "clip_001" / "images.json"
    images_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "items": [
                    {"key": "model_front", "label": "正面穿搭", "status": "completed", "url": "/front.png"},
                    {"key": "model_side", "label": "侧面角度", "status": "failed", "url": ""},
                    {"key": "model_back", "label": "背面/细节", "status": "not_started", "url": ""},
                    {"key": "detail_page", "label": "淘宝详情页示例", "status": "not_started", "url": ""},
                ],
                "updated_at": "2026-04-28T00:00:00",
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("app.api.commerce.OpenAIImageClient", FakeOpenAIImageClient)
    monkeypatch.setattr("app.tasks.pipeline.process_commerce_assets.delay", lambda *args: type("Result", (), {"id": "celery-4"})())

    response = await client.post(f"/api/commerce/clips/{TASK_ID}/clip_001/images/model_side")
    assert response.status_code == 200
    assert response.json()["job"]["image_keys"] == ["model_side"]

    from app.api.commerce import run_commerce_actions

    run_commerce_actions(TASK_ID, "clip_001", ["images"], image_keys=["model_side"])
    saved = json.loads(images_path.read_text())
    by_key = {item["key"]: item for item in saved["items"]}
    assert by_key["model_front"]["url"] == "/front.png"
    assert by_key["model_side"]["status"] == "completed"
    assert by_key["model_side"]["url"].endswith("/model_side.png")
    assert (tmp_path / TASK_ID / "commerce" / "clip_001" / "images" / "model_side.png").read_bytes() == b"side-png-data"
