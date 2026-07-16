"""Issue-message types — editable reference table (2026-07-16).

[USER] Each message type (Sales order, Return billing, …) flows through a
specific TIBCO API and IIB flow; knowing them matters when asking tech
teams to check. The table is editable on its own card (/message-types) so
Marina can fill in the APIs as she learns them. The SPECIAL TEXTS of the
issue-message builder are deliberately FIXED in code (app/issue_messages.py)
— editable templates felt brittle [USER decision].

Seeded with the eight default names when the table is empty (note: deleting
ALL rows brings the defaults back on next startup — acceptable edge case).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS message_types (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    tibco_api  TEXT,
    iib_api    TEXT,
    comment    TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""

_DEFAULT_NAMES = [
    "Reservation order", "Sales order", "Sales billing", "Return order",
    "Return billing", "Exchange order", "Exchange billing", "Settlement file",
]


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        _seed_defaults(conn)
    finally:
        conn.close()


def _seed_defaults(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM message_types").fetchone()[0]:
        return
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        for i, name in enumerate(_DEFAULT_NAMES):
            conn.execute(
                "INSERT INTO message_types (name, sort_order, updated_at)"
                " VALUES (?,?,?)", (name, i, now))


def list_message_types(conn: sqlite3.Connection) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM message_types ORDER BY sort_order, name COLLATE NOCASE"))


def create_message_type(conn: sqlite3.Connection, name: str,
                        tibco_api: str | None = None, iib_api: str | None = None,
                        comment: str | None = None) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        nxt = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM message_types"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO message_types (name, tibco_api, iib_api, comment,"
            " sort_order, updated_at) VALUES (?,?,?,?,?,?)",
            (name, tibco_api or None, iib_api or None, comment or None, nxt, now))
    return cur.lastrowid


def update_message_type(conn: sqlite3.Connection, type_id: int, name: str,
                        tibco_api: str | None, iib_api: str | None,
                        comment: str | None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE message_types SET name=?, tibco_api=?, iib_api=?,"
            " comment=?, updated_at=? WHERE id=?",
            (name, tibco_api or None, iib_api or None, comment or None,
             now, type_id))


def delete_message_type(conn: sqlite3.Connection, type_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM message_types WHERE id=?", (type_id,))
