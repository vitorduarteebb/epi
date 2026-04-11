from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "web_feedback.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                original_name TEXT,
                path TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                frame_idx INTEGER NOT NULL,
                approved INTEGER NOT NULL,
                detections_json TEXT,
                notes TEXT,
                created_at REAL NOT NULL,
                UNIQUE(video_id, frame_idx),
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
            """
        )
        c.commit()


def insert_video(original_name: str, dest_path: Path) -> str:
    vid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            "INSERT INTO videos (id, original_name, path, created_at) VALUES (?, ?, ?, ?)",
            (vid, original_name, str(dest_path.resolve()), time.time()),
        )
        c.commit()
    return vid


def list_videos() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, original_name, path, created_at FROM videos ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_video(vid: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM videos WHERE id = ?", (vid,)).fetchone()
    return dict(row) if row else None


def upsert_feedback(
    video_id: str,
    frame_idx: int,
    approved: bool,
    detections: list[dict[str, Any]],
    notes: str | None,
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO feedback (video_id, frame_idx, approved, detections_json, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id, frame_idx) DO UPDATE SET
                approved = excluded.approved,
                detections_json = excluded.detections_json,
                notes = excluded.notes,
                created_at = excluded.created_at
            """,
            (
                video_id,
                frame_idx,
                1 if approved else 0,
                json.dumps(detections, ensure_ascii=False),
                notes or "",
                time.time(),
            ),
        )
        c.commit()


def list_feedback(video_id: str | None = None) -> list[dict[str, Any]]:
    with _conn() as c:
        if video_id:
            rows = c.execute(
                "SELECT * FROM feedback WHERE video_id = ? ORDER BY created_at DESC",
                (video_id,),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 500").fetchall()
    return [dict(r) for r in rows]


def get_training_stats() -> dict[str, Any]:
    """Métricas agregadas para o painel (taxa de acerto, por vídeo, série temporal)."""
    with _conn() as c:
        row = c.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN approved = 1 THEN 1 ELSE 0 END), 0) AS approved,
                COALESCE(SUM(CASE WHEN approved = 0 THEN 1 ELSE 0 END), 0) AS rejected
            FROM feedback
            """
        ).fetchone()
        total = int(row["total"] or 0)
        approved = int(row["approved"] or 0)
        rejected = int(row["rejected"] or 0)

        vcount = c.execute("SELECT COUNT(*) AS n FROM videos").fetchone()
        videos_count = int(vcount["n"] or 0)

        per_video_rows = c.execute(
            """
            SELECT v.id AS video_id, v.original_name AS name,
                COUNT(f.id) AS labels,
                COALESCE(SUM(CASE WHEN f.approved = 1 THEN 1 ELSE 0 END), 0) AS approved,
                COALESCE(SUM(CASE WHEN f.approved = 0 THEN 1 ELSE 0 END), 0) AS rejected
            FROM videos v
            LEFT JOIN feedback f ON f.video_id = v.id
            GROUP BY v.id
            ORDER BY labels DESC, v.created_at DESC
            """
        ).fetchall()

        daily_rows = c.execute(
            """
            SELECT
                strftime('%Y-%m-%d', datetime(created_at, 'unixepoch')) AS day,
                COUNT(*) AS cnt,
                COALESCE(SUM(CASE WHEN approved = 1 THEN 1 ELSE 0 END), 0) AS approved,
                COALESCE(SUM(CASE WHEN approved = 0 THEN 1 ELSE 0 END), 0) AS rejected
            FROM feedback
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
            """
        ).fetchall()

        fb_rows = c.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    accuracy_percent: float | None
    if total == 0:
        accuracy_percent = None
    else:
        accuracy_percent = round(100.0 * approved / total, 1)

    per_video: list[dict[str, Any]] = []
    for r in per_video_rows:
        lbl = int(r["labels"] or 0)
        ap = int(r["approved"] or 0)
        rp = int(r["rejected"] or 0)
        pct = round(100.0 * ap / lbl, 1) if lbl else None
        per_video.append(
            {
                "video_id": r["video_id"],
                "name": r["name"],
                "labels": lbl,
                "approved": ap,
                "rejected": rp,
                "accuracy_percent": pct,
            }
        )

    daily: list[dict[str, Any]] = []
    for r in reversed(list(daily_rows)):
        daily.append(
            {
                "date": r["day"],
                "count": int(r["cnt"] or 0),
                "approved": int(r["approved"] or 0),
                "rejected": int(r["rejected"] or 0),
            }
        )

    fb_items = [dict(r) for r in fb_rows]
    recent_feedback = fb_items[:25]
    chrono = list(reversed(fb_items))
    roll_total = len(chrono)
    roll_ok = sum(1 for x in chrono if x.get("approved"))
    rolling_percent = round(100.0 * roll_ok / roll_total, 1) if roll_total else None

    return {
        "total_labels": total,
        "approved": approved,
        "rejected": rejected,
        "accuracy_percent": accuracy_percent,
        "videos_count": videos_count,
        "per_video": per_video,
        "daily": daily,
        "recent_feedback": recent_feedback,
        "rolling": {
            "window": min(50, roll_total),
            "approved": roll_ok,
            "total": roll_total,
            "accuracy_percent": rolling_percent,
        },
    }
