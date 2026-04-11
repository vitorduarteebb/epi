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
