import json

import pytest


TASK_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


@pytest.fixture(autouse=True)
def _setup_task_detail(tmp_path, monkeypatch):
    task_dir = tmp_path / TASK_ID
    (task_dir / "vlm").mkdir(parents=True)
    (task_dir / "clips").mkdir(parents=True)
    (task_dir / "covers").mkdir(parents=True)
    (task_dir / "scenes").mkdir(parents=True)

    (task_dir / "original.mp4").write_bytes(b"fake-video")
    (task_dir / "meta.json").write_text(json.dumps({"duration": 120}))
    (task_dir / "settings.json").write_text(
        json.dumps({"subtitle_mode": "karaoke", "asr_provider": "dashscope"})
    )
    (task_dir / "state.json").write_text(json.dumps({"state": "COMPLETED"}))
    (task_dir / "candidates.json").write_text(
        json.dumps([{"timestamp": 10}, {"timestamp": 30}, {"timestamp": 60}])
    )
    (task_dir / "vlm" / "confirmed_segments.json").write_text(
        json.dumps([{"start_time": 10, "end_time": 40}])
    )
    (task_dir / "transcript.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 10,
                    "end_time": 12,
                    "text": "这件连衣裙很显瘦",
                    "words": [],
                }
            ],
            ensure_ascii=False,
        )
    )
    (task_dir / "text_boundaries.json").write_text(json.dumps([{"start": 10}]))
    (task_dir / "fused_candidates.json").write_text(json.dumps([{"start_time": 10}]))
    (task_dir / "enriched_segments.json").write_text(
        json.dumps(
            [
                {
                    "start_time": 10,
                    "end_time": 40,
                    "product_name": "雪纺连衣裙",
                    "confidence": 0.9,
                },
                {
                    "start_time": 50,
                    "end_time": 80,
                    "product_name": "通勤外套",
                    "confidence": 0.8,
                },
            ],
            ensure_ascii=False,
        )
    )
    (task_dir / "scenes" / "person_presence.json").write_text(
        json.dumps([{"timestamp": 10, "person_present": True}])
    )
    (task_dir / "clips" / "clip_000.mp4").write_bytes(b"clip")
    (task_dir / "covers" / "clip_000.jpg").write_bytes(b"cover")
    (task_dir / "clips" / "clip_000_meta.json").write_text(
        json.dumps(
            {
                "product_name": "雪纺连衣裙",
                "duration": 30,
                "start_time": 10,
                "end_time": 40,
                "confidence": 0.9,
            },
            ensure_ascii=False,
        )
    )

    monkeypatch.setattr("app.api.tasks.UPLOAD_DIR", tmp_path)


@pytest.mark.anyio
async def test_task_summary_reads_artifacts(client):
    response = await client.get(f"/api/tasks/{TASK_ID}/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["candidates_count"] == 3
    assert data["confirmed_count"] == 1
    assert data["transcript_segments_count"] == 1
    assert data["fused_candidates_count"] == 1
    assert data["enriched_segments_count"] == 2
    assert data["clips_count"] == 1
    assert data["empty_screen_dropped_estimate"] == 1
    assert data["artifact_status"]["transcript"] is True


@pytest.mark.anyio
async def test_task_diagnostics_builds_funnel_and_warnings(client):
    response = await client.get(f"/api/tasks/{TASK_ID}/diagnostics")

    assert response.status_code == 200
    data = response.json()
    assert data["funnel"][0] == {"label": "原始候选", "count": 3}
    assert any("DashScope" in item["message"] for item in data["warnings"])
    assert any(item["file"] == "transcript.json" for item in data["event_log"])


@pytest.mark.anyio
async def test_task_review_merges_review_status(client, tmp_path):
    patch = {
        "status": "approved",
        "product_name": "已确认连衣裙",
        "title": "雪纺连衣裙讲解",
    }
    patch_response = await client.patch(
        f"/api/tasks/{TASK_ID}/review/segments/clip_000",
        json=patch,
    )

    assert patch_response.status_code == 200
    review_response = await client.get(f"/api/tasks/{TASK_ID}/review")
    data = review_response.json()
    assert data["segments"][0]["review_status"] == "approved"
    assert data["segments"][0]["product_name"] == "已确认连衣裙"
    assert data["clips"][0]["review_status"] == "approved"


@pytest.mark.anyio
async def test_task_review_rejects_invalid_status(client):
    response = await client.patch(
        f"/api/tasks/{TASK_ID}/review/segments/clip_000",
        json={"status": "done-ish"},
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_retry_task_queues_pipeline(client, monkeypatch):
    queued: list[tuple[str, str]] = []

    class FakeStartPipeline:
        def delay(self, task_id: str, file_path: str) -> None:
            queued.append((task_id, file_path))

    monkeypatch.setattr("app.api.tasks.start_pipeline", FakeStartPipeline())

    response = await client.post(f"/api/tasks/{TASK_ID}/retry")

    assert response.status_code == 200
    assert response.json() == {"task_id": TASK_ID, "status": "queued"}
    assert queued
    assert queued[0][0] == TASK_ID
    assert queued[0][1].endswith(f"{TASK_ID}/original.mp4")


@pytest.mark.anyio
async def test_reprocess_clip_queues_single_segment(client, monkeypatch):
    queued: list[tuple[str, str, str]] = []

    class FakeResult:
        id = "reprocess-id"

    class FakeReprocessClip:
        def delay(self, task_id: str, task_dir: str, segment_id: str) -> FakeResult:
            queued.append((task_id, task_dir, segment_id))
            return FakeResult()

    monkeypatch.setattr("app.api.tasks.reprocess_clip", FakeReprocessClip())

    response = await client.post(f"/api/tasks/{TASK_ID}/clips/clip_000/reprocess")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert queued
    assert queued[0][0] == TASK_ID
    assert queued[0][2] == "clip_000"

    status_response = await client.get(f"/api/tasks/{TASK_ID}/clips/clip_000/reprocess")
    assert status_response.status_code == 200
    assert status_response.json()["job"]["status"] == "queued"
    assert status_response.json()["job"]["celery_id"] == "reprocess-id"
