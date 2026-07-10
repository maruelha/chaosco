"""Next-step archive — generic history storage (2026-07-10).

"New next step" [USER]: the CURRENT next step of an entity is archived here
with a timestamp and the live field is cleared — the field stays a single
line, the past stays visible. Same generic (entity_type, entity_id) address
as notes / order_details / entity_links; consumed by the drop-in component
_next_step_history.html + app/web_next_steps.py (registry-driven).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS next_step_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    next_step   TEXT NOT NULL,
    archived_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ns_hist_entity
    ON next_step_history(entity_type, entity_id);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def archive_next_step(conn: sqlite3.Connection, entity_type: str,
                      entity_id: str, next_step: str) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO next_step_history (entity_type, entity_id, next_step,"
            " archived_at) VALUES (?,?,?,?)",
            (entity_type, str(entity_id), next_step,
             datetime.now().isoformat(sep=" ", timespec="minutes")))
    return cur.lastrowid


def list_next_step_history(conn: sqlite3.Connection, entity_type: str,
                           entity_id: str) -> list[dict]:
    """Newest first — the dialog reads top-down like a log."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM next_step_history WHERE entity_type=? AND entity_id=?"
        " ORDER BY id DESC", (entity_type, str(entity_id))))


def delete_next_step_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM next_step_history WHERE id=?", (entry_id,))
