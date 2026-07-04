"""Topics — active working topics (app.db.topics).

The counterpart to Shelf: Shelf archives information that might matter
someday; a Topic is something Marina is actively working on. Per topic:
next steps (checkable, archived when done), the shared notes module, and a
big formatted-text workpad (stored as HTML, authored via the contenteditable
editor on the detail page).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

TOPIC_PRIORITIES = ["High", "Medium", "Low"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    category   TEXT,
    priority   TEXT NOT NULL DEFAULT 'Medium',
    status     TEXT NOT NULL DEFAULT 'active',   -- active | done
    workpad    TEXT,                             -- HTML from the workpad editor
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_steps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id   INTEGER NOT NULL,
    step       TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    done_at    TEXT,
    created_at TEXT NOT NULL
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def create_topic(conn: sqlite3.Connection, title: str,
                 category: str | None = None, priority: str = "Medium") -> int:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO topics (title, category, priority, status, created_at, updated_at)"
            " VALUES (?, ?, ?, 'active', ?, ?)",
            (title.strip(), (category or "").strip() or None,
             priority if priority in TOPIC_PRIORITIES else "Medium", now, now))
    return cur.lastrowid


def list_topics(conn: sqlite3.Connection, q: str | None = None,
                category: str | None = None, priority: str | None = None,
                include_done: bool = False) -> list[dict]:
    sql = """
        SELECT t.*,
               (SELECT COUNT(*) FROM topic_steps s
                WHERE s.topic_id = t.id AND s.done = 0) AS open_steps,
               (SELECT COUNT(*) FROM notes n
                WHERE n.entity_type = 'topic' AND n.entity_id = CAST(t.id AS TEXT)
               ) AS note_count
        FROM topics t WHERE 1=1
    """
    params: list = []
    if not include_done:
        sql += " AND t.status = 'active'"
    if q:
        sql += " AND t.title LIKE ?"
        params.append(f"%{q}%")
    if category:
        sql += " AND t.category = ?"
        params.append(category)
    if priority:
        sql += " AND t.priority = ?"
        params.append(priority)
    sql += (" ORDER BY CASE t.priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1"
            " ELSE 2 END, t.updated_at DESC")
    return _rows_to_dicts(conn.execute(sql, params))


def get_topic(conn: sqlite3.Connection, topic_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)))
    return rows[0] if rows else None


def update_topic(conn: sqlite3.Connection, topic_id: int, title: str,
                 category: str | None, priority: str, status: str) -> None:
    with conn:
        conn.execute(
            "UPDATE topics SET title=?, category=?, priority=?, status=?, updated_at=?"
            " WHERE id=?",
            (title.strip(), (category or "").strip() or None,
             priority if priority in TOPIC_PRIORITIES else "Medium",
             status if status in ("active", "done") else "active",
             _now(), topic_id))


def save_workpad(conn: sqlite3.Connection, topic_id: int, html: str | None) -> None:
    with conn:
        conn.execute("UPDATE topics SET workpad=?, updated_at=? WHERE id=?",
                     (html or None, _now(), topic_id))


def delete_topic(conn: sqlite3.Connection, topic_id: int) -> list[str]:
    """Delete topic + steps + notes. Returns attachment filenames to unlink."""
    filenames = [r[0] for r in conn.execute(
        "SELECT a.filename FROM attachments a JOIN notes n ON n.id = a.note_id"
        " WHERE n.entity_type = 'topic' AND n.entity_id = CAST(? AS TEXT)", (topic_id,))]
    with conn:
        conn.execute(
            "DELETE FROM attachments WHERE note_id IN"
            " (SELECT id FROM notes WHERE entity_type='topic' AND entity_id=CAST(? AS TEXT))",
            (topic_id,))
        conn.execute("DELETE FROM notes WHERE entity_type='topic' AND entity_id=CAST(? AS TEXT)",
                     (topic_id,))
        conn.execute("DELETE FROM topic_steps WHERE topic_id=?", (topic_id,))
        conn.execute("DELETE FROM topics WHERE id=?", (topic_id,))
    return filenames


def get_topic_categories(conn: sqlite3.Connection) -> list[str]:
    return sorted({r[0] for r in conn.execute(
        "SELECT DISTINCT category FROM topics WHERE category IS NOT NULL AND category != ''")})


def count_active_topics(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM topics WHERE status='active'").fetchone()[0]


# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

def add_step(conn: sqlite3.Connection, topic_id: int, step: str) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO topic_steps (topic_id, step, done, created_at) VALUES (?, ?, 0, ?)",
            (topic_id, step.strip(), _now()))
        conn.execute("UPDATE topics SET updated_at=? WHERE id=?", (_now(), topic_id))
    return cur.lastrowid


def list_steps(conn: sqlite3.Connection, topic_id: int) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM topic_steps WHERE topic_id=?"
        " ORDER BY done, CASE WHEN done=1 THEN done_at END DESC, created_at",
        (topic_id,)))


def set_step_done(conn: sqlite3.Connection, step_id: int, done: bool) -> None:
    with conn:
        conn.execute("UPDATE topic_steps SET done=?, done_at=? WHERE id=?",
                     (1 if done else 0, _now() if done else None, step_id))


def update_step(conn: sqlite3.Connection, step_id: int, step: str) -> None:
    with conn:
        conn.execute("UPDATE topic_steps SET step=? WHERE id=?", (step.strip(), step_id))


def delete_step(conn: sqlite3.Connection, step_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM topic_steps WHERE id=?", (step_id,))
