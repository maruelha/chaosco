"""Email report recipients (app.db.email).

Recipients for the "Email reports" feature live in the DB (not config) so
they can be managed in the UI. SMTP credentials live in settings.local.yaml
(gitignored) — never in code, never in this table.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS report_recipients (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT NOT NULL UNIQUE,
    name       TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
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


def list_recipients(conn: sqlite3.Connection, active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM report_recipients"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY email"
    return _rows_to_dicts(conn.execute(sql))


def add_recipient(conn: sqlite3.Connection, email: str, name: str | None) -> int:
    with conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO report_recipients (email, name, active, created_at)"
            " VALUES (?, ?, 1, ?)",
            (email.strip(), (name or "").strip() or None,
             datetime.now().isoformat(timespec="seconds")))
    return cur.lastrowid


def set_recipient_active(conn: sqlite3.Connection, rid: int, active: bool) -> None:
    with conn:
        conn.execute("UPDATE report_recipients SET active=? WHERE id=?",
                     (1 if active else 0, rid))


def delete_recipient(conn: sqlite3.Connection, rid: int) -> None:
    with conn:
        conn.execute("DELETE FROM report_recipients WHERE id=?", (rid,))
