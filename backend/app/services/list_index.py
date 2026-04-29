import datetime
import logging
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from app.utils.json_io import read_json_silent as _read_json

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"
INDEX_DB_NAME = "index.sqlite3"
_READY_INDEXES: set[Path] = set()
_READY_LOCK = RLock()


def _connect(upload_dir: Path) -> sqlite3.Connection:
    upload_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(upload_dir / INDEX_DB_NAME, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_index (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            status_group TEXT NOT NULL,
            stage TEXT,
            message TEXT,
            created_at TEXT,
            original_filename TEXT,
            display_name TEXT,
            video_duration_s REAL,
            asr_provider TEXT,
            clip_count INTEGER NOT NULL DEFAULT 0,
            thumbnail_url TEXT,
            sort_at TEXT,
            updated_at TEXT,
            task_dir_mtime REAL
        );

        CREATE TABLE IF NOT EXISTS clip_index (
            clip_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            segment_id TEXT NOT NULL,
            product_name TEXT,
            duration REAL,
            start_time REAL,
            end_time REAL,
            confidence REAL,
            review_status TEXT NOT NULL DEFAULT 'pending',
            file_size INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            video_url TEXT,
            preview_url TEXT,
            thumbnail_url TEXT,
            has_video INTEGER NOT NULL DEFAULT 0,
            has_thumbnail INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY(task_id) REFERENCES task_index(task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS commerce_index (
            clip_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            segment_id TEXT NOT NULL,
            commerce_status TEXT NOT NULL DEFAULT 'not_started',
            analysis_status TEXT NOT NULL DEFAULT 'not_started',
            copywriting_status TEXT NOT NULL DEFAULT 'not_started',
            images_status TEXT NOT NULL DEFAULT 'not_started',
            job_status TEXT,
            updated_at TEXT,
            FOREIGN KEY(clip_id) REFERENCES clip_index(clip_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_task_status_group ON task_index(status_group);
        CREATE INDEX IF NOT EXISTS idx_task_sort_at ON task_index(sort_at);
        CREATE INDEX IF NOT EXISTS idx_clip_task ON clip_index(task_id);
        CREATE INDEX IF NOT EXISTS idx_clip_review ON clip_index(review_status);
        CREATE INDEX IF NOT EXISTS idx_clip_duration ON clip_index(duration);
        CREATE INDEX IF NOT EXISTS idx_clip_created ON clip_index(created_at);
        CREATE INDEX IF NOT EXISTS idx_commerce_status ON commerce_index(commerce_status);
        """
    )


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def status_group(status: str) -> str:
    if status == "COMPLETED":
        return "completed"
    if status == "ERROR":
        return "failed"
    if status == "UPLOADED":
        return "uploaded"
    return "processing"


def _review_status(task_dir: Path, segment_id: str) -> str:
    review = _read_json(task_dir / "review.json", {})
    if not isinstance(review, dict):
        return "pending"
    segments = review.get("segments", {})
    if not isinstance(segments, dict):
        return "pending"
    entry = segments.get(segment_id, {})
    if not isinstance(entry, dict):
        return "pending"
    return str(entry.get("status", "pending"))


def _derive_commerce_status(
    analysis: dict[str, Any],
    copywriting: dict[str, Any],
    images: dict[str, Any],
    job: dict[str, Any],
) -> str:
    if job.get("status") in {"queued", "running", "failed"}:
        return str(job["status"])
    statuses = [analysis.get("status"), copywriting.get("status"), images.get("status")]
    if all(status == "completed" for status in statuses):
        return "completed"
    if any(status == "completed" for status in statuses):
        return "partial"
    return "not_started"


def _commerce_record(task_dir: Path, segment_id: str) -> dict[str, Any]:
    clip_id = f"{task_dir.name}/{segment_id}"
    commerce_dir = task_dir / "commerce" / segment_id
    analysis = _read_json(commerce_dir / "product_analysis.json", {})
    copywriting = _read_json(commerce_dir / "copywriting.json", {})
    images = _read_json(commerce_dir / "images.json", {})
    job = _read_json(commerce_dir / "job.json", {})
    analysis = analysis if isinstance(analysis, dict) else {}
    copywriting = copywriting if isinstance(copywriting, dict) else {}
    images = images if isinstance(images, dict) else {}
    job = job if isinstance(job, dict) else {}
    return {
        "clip_id": clip_id,
        "task_id": task_dir.name,
        "segment_id": segment_id,
        "commerce_status": _derive_commerce_status(analysis, copywriting, images, job),
        "analysis_status": str(analysis.get("status", "not_started")),
        "copywriting_status": str(copywriting.get("status", "not_started")),
        "images_status": str(images.get("status", "not_started")),
        "job_status": str(job.get("status", "")),
        "updated_at": _now_iso(),
    }


def _build_task_record(task_dir: Path) -> dict[str, Any] | None:
    state = _read_json(task_dir / "state.json", None)
    if not isinstance(state, dict):
        return None

    task_id = task_dir.name
    status = str(state.get("state", "UPLOADED"))
    meta = _read_json(task_dir / "meta.json", {})
    meta = meta if isinstance(meta, dict) else {}
    settings = _read_json(task_dir / "settings.json", {})
    settings = settings if isinstance(settings, dict) else {}

    clips_dir = task_dir / "clips"
    clip_count = sum(1 for f in clips_dir.iterdir() if f.name.endswith(".mp4")) if clips_dir.is_dir() else 0

    thumbnail_url = ""
    covers_dir = task_dir / "covers"
    if covers_dir.is_dir():
        for cover in sorted(covers_dir.iterdir()):
            if cover.name.endswith(".jpg"):
                thumbnail_url = f"/api/clips/{task_id}/{cover.stem}/thumbnail"
                break

    display_name = str(meta.get("original_filename") or "")
    if not display_name and clips_dir.is_dir():
        for meta_file in sorted(clips_dir.glob("*_meta.json")):
            clip_meta = _read_json(meta_file, {})
            if isinstance(clip_meta, dict):
                first_product = str(clip_meta.get("product_name") or "")
                if first_product and first_product != "未命名商品":
                    display_name = first_product
                    break
    if not display_name:
        display_name = f"{clip_count}个片段的视频" if clip_count > 0 else "视频"

    created_at = str(meta.get("created_at") or "")
    sort_at = created_at or datetime.datetime.fromtimestamp(
        task_dir.stat().st_mtime,
        tz=datetime.timezone.utc,
    ).isoformat()
    return {
        "task_id": task_id,
        "status": status,
        "status_group": status_group(status),
        "stage": state.get("step"),
        "message": state.get("message"),
        "created_at": created_at,
        "original_filename": str(meta.get("original_filename") or ""),
        "display_name": display_name,
        "video_duration_s": meta.get("duration"),
        "asr_provider": str(settings.get("asr_provider") or ""),
        "clip_count": clip_count,
        "thumbnail_url": thumbnail_url,
        "sort_at": sort_at,
        "updated_at": _now_iso(),
        "task_dir_mtime": task_dir.stat().st_mtime,
    }


def _build_clip_records(task_dir: Path) -> list[dict[str, Any]]:
    clips_dir = task_dir / "clips"
    if not clips_dir.is_dir():
        return []

    task_id = task_dir.name
    meta = _read_json(task_dir / "meta.json", {})
    created_at = str(meta.get("created_at") or "") if isinstance(meta, dict) else ""
    records: list[dict[str, Any]] = []
    for meta_file in sorted(clips_dir.glob("clip_*_meta.json")):
        segment_id = meta_file.stem.replace("_meta", "")
        clip_meta = _read_json(meta_file, {})
        if not isinstance(clip_meta, dict):
            continue
        video_path = clips_dir / f"{segment_id}.mp4"
        cover_path = task_dir / "covers" / f"{segment_id}.jpg"
        records.append(
            {
                "clip_id": f"{task_id}/{segment_id}",
                "task_id": task_id,
                "segment_id": segment_id,
                "product_name": clip_meta.get("product_name", "未知商品"),
                "duration": clip_meta.get("duration", 0),
                "start_time": clip_meta.get("start_time", 0),
                "end_time": clip_meta.get("end_time", 0),
                "confidence": clip_meta.get("confidence", 0),
                "review_status": _review_status(task_dir, segment_id),
                "file_size": video_path.stat().st_size if video_path.exists() else 0,
                "created_at": created_at,
                "video_url": f"/api/clips/{task_id}/{segment_id}/download",
                "preview_url": f"/api/clips/{task_id}/{segment_id}/preview",
                "thumbnail_url": f"/api/clips/{task_id}/{segment_id}/thumbnail",
                "has_video": 1 if video_path.exists() else 0,
                "has_thumbnail": 1 if cover_path.exists() else 0,
                "updated_at": _now_iso(),
            }
        )
    return records


def _upsert_task(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO task_index (
            task_id, status, status_group, stage, message, created_at, original_filename,
            display_name, video_duration_s, asr_provider, clip_count, thumbnail_url,
            sort_at, updated_at, task_dir_mtime
        ) VALUES (
            :task_id, :status, :status_group, :stage, :message, :created_at, :original_filename,
            :display_name, :video_duration_s, :asr_provider, :clip_count, :thumbnail_url,
            :sort_at, :updated_at, :task_dir_mtime
        )
        ON CONFLICT(task_id) DO UPDATE SET
            status=excluded.status,
            status_group=excluded.status_group,
            stage=excluded.stage,
            message=excluded.message,
            created_at=excluded.created_at,
            original_filename=excluded.original_filename,
            display_name=excluded.display_name,
            video_duration_s=excluded.video_duration_s,
            asr_provider=excluded.asr_provider,
            clip_count=excluded.clip_count,
            thumbnail_url=excluded.thumbnail_url,
            sort_at=excluded.sort_at,
            updated_at=excluded.updated_at,
            task_dir_mtime=excluded.task_dir_mtime
        """,
        record,
    )


def _upsert_clip(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO clip_index (
            clip_id, task_id, segment_id, product_name, duration, start_time, end_time,
            confidence, review_status, file_size, created_at, video_url, preview_url,
            thumbnail_url, has_video, has_thumbnail, updated_at
        ) VALUES (
            :clip_id, :task_id, :segment_id, :product_name, :duration, :start_time, :end_time,
            :confidence, :review_status, :file_size, :created_at, :video_url, :preview_url,
            :thumbnail_url, :has_video, :has_thumbnail, :updated_at
        )
        ON CONFLICT(clip_id) DO UPDATE SET
            product_name=excluded.product_name,
            duration=excluded.duration,
            start_time=excluded.start_time,
            end_time=excluded.end_time,
            confidence=excluded.confidence,
            review_status=excluded.review_status,
            file_size=excluded.file_size,
            created_at=excluded.created_at,
            video_url=excluded.video_url,
            preview_url=excluded.preview_url,
            thumbnail_url=excluded.thumbnail_url,
            has_video=excluded.has_video,
            has_thumbnail=excluded.has_thumbnail,
            updated_at=excluded.updated_at
        """,
        record,
    )


def _upsert_commerce(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO commerce_index (
            clip_id, task_id, segment_id, commerce_status, analysis_status,
            copywriting_status, images_status, job_status, updated_at
        ) VALUES (
            :clip_id, :task_id, :segment_id, :commerce_status, :analysis_status,
            :copywriting_status, :images_status, :job_status, :updated_at
        )
        ON CONFLICT(clip_id) DO UPDATE SET
            commerce_status=excluded.commerce_status,
            analysis_status=excluded.analysis_status,
            copywriting_status=excluded.copywriting_status,
            images_status=excluded.images_status,
            job_status=excluded.job_status,
            updated_at=excluded.updated_at
        """,
        record,
    )


def _index_task_locked(conn: sqlite3.Connection, task_dir: Path) -> None:
    task_record = _build_task_record(task_dir)
    if task_record is None:
        conn.execute("DELETE FROM task_index WHERE task_id = ?", (task_dir.name,))
        return
    _upsert_task(conn, task_record)
    conn.execute("DELETE FROM clip_index WHERE task_id = ?", (task_dir.name,))
    for clip_record in _build_clip_records(task_dir):
        _upsert_clip(conn, clip_record)
        _upsert_commerce(conn, _commerce_record(task_dir, str(clip_record["segment_id"])))


def rebuild_index(upload_dir: Path) -> None:
    ready_key = upload_dir.resolve()
    with _connect(upload_dir) as conn:
        _init_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM commerce_index")
        conn.execute("DELETE FROM clip_index")
        conn.execute("DELETE FROM task_index")
        if upload_dir.exists():
            for task_dir in sorted(upload_dir.iterdir()):
                if task_dir.is_dir():
                    _index_task_locked(conn, task_dir)
        conn.execute(
            "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
            ("rebuilt_at", _now_iso()),
        )
        conn.commit()
    with _READY_LOCK:
        _READY_INDEXES.add(ready_key)


def _ensure_ready(conn: sqlite3.Connection, upload_dir: Path) -> bool:
    _init_schema(conn)
    row = conn.execute(
        "SELECT value FROM index_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row and row["value"] == SCHEMA_VERSION:
        return True
    logger.info("List index missing or outdated, rebuilding")
    return False


def ensure_index(upload_dir: Path) -> None:
    ready_key = upload_dir.resolve()
    with _READY_LOCK:
        if ready_key in _READY_INDEXES and (upload_dir / INDEX_DB_NAME).exists():
            return
    with _connect(upload_dir) as conn:
        if _ensure_ready(conn, upload_dir):
            with _READY_LOCK:
                _READY_INDEXES.add(ready_key)
            return
    rebuild_index(upload_dir)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def refresh_task_index(upload_dir: Path, task_id: str) -> None:
    try:
        with _connect(upload_dir) as conn:
            _init_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            task_dir = upload_dir / task_id
            if task_dir.exists() and task_dir.is_dir():
                _index_task_locked(conn, task_dir)
            else:
                conn.execute("DELETE FROM task_index WHERE task_id = ?", (task_id,))
            conn.commit()
    except sqlite3.Error:
        logger.warning("Failed to refresh list index for task %s", task_id, exc_info=True)


def delete_task_index(upload_dir: Path, task_id: str) -> None:
    try:
        with _connect(upload_dir) as conn:
            _init_schema(conn)
            conn.execute("DELETE FROM task_index WHERE task_id = ?", (task_id,))
    except sqlite3.Error:
        logger.warning("Failed to delete list index for task %s", task_id, exc_info=True)


def _task_status_filter(status: str | None) -> tuple[str, list[Any]]:
    if not status:
        return "", []
    normalized = status.lower()
    if normalized == "processing":
        return " AND status_group = ?", ["processing"]
    if normalized in {"completed", "failed", "uploaded"}:
        return " AND status_group = ?", [normalized]
    return " AND status = ?", [status]


def query_tasks(
    upload_dir: Path,
    *,
    offset: int,
    limit: int,
    status: str | None,
    q: str | None,
) -> dict[str, Any]:
    ensure_index(upload_dir)
    with _connect(upload_dir) as conn:
        _init_schema(conn)
        summary_rows = conn.execute(
            "SELECT status_group, COUNT(*) AS count, COALESCE(SUM(clip_count), 0) AS clips FROM task_index GROUP BY status_group"
        ).fetchall()
        summary = {
            "total": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "uploaded": 0,
            "clip_count": 0,
        }
        for row in summary_rows:
            group = str(row["status_group"])
            if group in summary:
                summary[group] = int(row["count"])
            summary["total"] += int(row["count"])
            summary["clip_count"] += int(row["clips"] or 0)

        where = "WHERE 1=1"
        params: list[Any] = []
        status_sql, status_params = _task_status_filter(status)
        where += status_sql
        params.extend(status_params)
        normalized_q = (q or "").strip().lower()
        if normalized_q:
            like = f"%{_escape_like(normalized_q)}%"
            where += " AND (lower(task_id) LIKE ? ESCAPE '\\' OR lower(original_filename) LIKE ? ESCAPE '\\' OR lower(display_name) LIKE ? ESCAPE '\\')"
            params.extend([like, like, like])

        total = int(conn.execute(f"SELECT COUNT(*) FROM task_index {where}", params).fetchone()[0])
        rows = conn.execute(
            f"""
            SELECT task_id, status, stage, message, created_at, original_filename,
                   display_name, video_duration_s, asr_provider, clip_count, thumbnail_url
            FROM task_index
            {where}
            ORDER BY sort_at DESC, task_id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
            "summary": summary,
        }


def query_clip_assets(
    upload_dir: Path,
    *,
    status: str | None,
    commerce_status: str | None,
    project_id: str | None,
    q: str | None,
    duration: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    ensure_index(upload_dir)
    with _connect(upload_dir) as conn:
        _init_schema(conn)
        where = "WHERE 1=1"
        params: list[Any] = []
        if project_id:
            where += " AND c.task_id = ?"
            params.append(project_id)
        if status:
            where += " AND c.review_status = ?"
            params.append(status)
        if commerce_status:
            where += " AND COALESCE(cm.commerce_status, 'not_started') = ?"
            params.append(commerce_status)
        if duration == "short":
            where += " AND c.duration < 30"
        elif duration == "medium":
            where += " AND c.duration >= 30 AND c.duration <= 90"
        elif duration == "long":
            where += " AND c.duration > 90"
        normalized_q = (q or "").strip().lower()
        if normalized_q:
            like = f"%{_escape_like(normalized_q)}%"
            where += " AND (lower(c.product_name) LIKE ? ESCAPE '\\' OR lower(c.task_id) LIKE ? ESCAPE '\\' OR lower(c.clip_id) LIKE ? ESCAPE '\\' OR lower(c.segment_id) LIKE ? ESCAPE '\\')"
            params.extend([like, like, like, like])

        base_from = """
            FROM clip_index c
            LEFT JOIN commerce_index cm ON cm.clip_id = c.clip_id
        """
        total = int(conn.execute(f"SELECT COUNT(*) {base_from} {where}", params).fetchone()[0])
        summary_row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN c.review_status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN c.review_status = 'approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN c.review_status = 'skipped' THEN 1 ELSE 0 END) AS skipped,
                SUM(CASE WHEN c.review_status = 'needs_adjustment' THEN 1 ELSE 0 END) AS needs_adjustment,
                SUM(CASE WHEN c.has_video = 1 THEN 1 ELSE 0 END) AS downloadable,
                COALESCE(SUM(c.file_size), 0) AS total_size,
                SUM(CASE WHEN COALESCE(cm.commerce_status, 'not_started') = 'completed' THEN 1 ELSE 0 END) AS commerce_completed,
                SUM(CASE WHEN COALESCE(cm.commerce_status, 'not_started') = 'failed' THEN 1 ELSE 0 END) AS commerce_failed
            {base_from}
            {where}
            """,
            params,
        ).fetchone()
        summary = {key: int(summary_row[key] or 0) for key in summary_row.keys()}

        rows = conn.execute(
            f"""
            SELECT
                c.clip_id, c.task_id, c.segment_id, c.product_name, c.duration,
                c.start_time, c.end_time, c.confidence, c.review_status, c.file_size,
                c.created_at, c.video_url, c.preview_url, c.thumbnail_url,
                c.has_video, c.has_thumbnail,
                COALESCE(cm.commerce_status, 'not_started') AS commerce_status,
                COALESCE(cm.analysis_status, 'not_started') AS commerce_analysis_status,
                COALESCE(cm.copywriting_status, 'not_started') AS commerce_copywriting_status,
                COALESCE(cm.images_status, 'not_started') AS commerce_images_status
            {base_from}
            {where}
            ORDER BY c.created_at DESC, c.clip_id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["has_video"] = bool(item["has_video"])
            item["has_thumbnail"] = bool(item["has_thumbnail"])
            items.append(item)
        return {
            "items": items,
            "summary": summary,
            "total": total,
            "offset": offset,
            "limit": limit,
        }
