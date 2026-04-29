import sqlite3

import pytest

from app.services import list_index
from app.utils.json_io import write_json


def _task(upload_dir, task_id, *, state="COMPLETED", filename="video.mp4", product="商品", commerce=None):
    task_dir = upload_dir / task_id
    clips_dir = task_dir / "clips"
    covers_dir = task_dir / "covers"
    clips_dir.mkdir(parents=True)
    covers_dir.mkdir()
    write_json(task_dir / "state.json", {"state": state, "step": "done"})
    write_json(task_dir / "meta.json", {"created_at": "2026-01-01T00:00:00+00:00", "original_filename": filename, "duration": 12})
    write_json(task_dir / "settings.json", {"asr_provider": "volcengine_vc"})
    write_json(task_dir / "review.json", {"segments": {"clip_000": {"status": "approved"}}})
    (clips_dir / "clip_000.mp4").write_bytes(b"video")
    (covers_dir / "clip_000.jpg").write_bytes(b"cover")
    write_json(
        clips_dir / "clip_000_meta.json",
        {
            "product_name": product,
            "duration": 12,
            "start_time": 1,
            "end_time": 13,
            "confidence": 0.88,
        },
    )
    if commerce:
        commerce_dir = task_dir / "commerce" / "clip_000"
        commerce_dir.mkdir(parents=True)
        for name, payload in commerce.items():
            write_json(commerce_dir / name, payload)
    return task_dir


@pytest.fixture(autouse=True)
def _clear_ready_indexes():
    list_index._READY_INDEXES.clear()
    yield
    list_index._READY_INDEXES.clear()


def test_rebuild_index_creates_wal_schema_and_queries_tasks(tmp_path):
    _task(tmp_path, "task-a", filename="literal_video.mp4")

    list_index.rebuild_index(tmp_path)

    conn = sqlite3.connect(tmp_path / list_index.INDEX_DB_NAME)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("SELECT value FROM index_meta WHERE key = 'schema_version'").fetchone()[0] == list_index.SCHEMA_VERSION
    finally:
        conn.close()

    result = list_index.query_tasks(tmp_path, offset=0, limit=10, status="completed", q="literal")
    assert result["total"] == 1
    assert result["items"][0]["task_id"] == "task-a"
    assert result["summary"]["completed"] == 1


def test_like_search_escapes_percent_and_underscore(tmp_path):
    _task(tmp_path, "task-a", filename="plain-video.mp4", product="羊毛外套")
    _task(tmp_path, "task-b", filename="sale_1.mp4", product="sale_1")

    assert list_index.query_tasks(tmp_path, offset=0, limit=10, status=None, q="%")["total"] == 0
    assert list_index.query_clip_assets(tmp_path, status=None, commerce_status=None, project_id=None, q="sale_", duration=None, offset=0, limit=10)["total"] == 1


def test_query_clip_assets_filters_and_derives_commerce_status(tmp_path):
    _task(
        tmp_path,
        "task-a",
        product="连衣裙",
        commerce={
            "product_analysis.json": {"status": "completed"},
            "copywriting.json": {"status": "completed"},
            "images.json": {"status": "completed"},
        },
    )

    result = list_index.query_clip_assets(
        tmp_path,
        status="approved",
        commerce_status="completed",
        project_id="task-a",
        q="连衣裙",
        duration="short",
        offset=0,
        limit=10,
    )

    assert result["total"] == 1
    assert result["summary"]["commerce_completed"] == 1
    assert result["items"][0]["commerce_status"] == "completed"
    assert result["items"][0]["has_video"] is True


def test_ensure_index_uses_ready_cache_after_first_check(tmp_path, monkeypatch):
    _task(tmp_path, "task-a")
    list_index.ensure_index(tmp_path)

    def fail_connect(upload_dir):
        raise AssertionError("ensure_index should use ready cache")

    monkeypatch.setattr(list_index, "_connect", fail_connect)

    list_index.ensure_index(tmp_path)
