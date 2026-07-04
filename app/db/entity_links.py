"""Entity links — generic per-entity URL list (app.db.entity_links).

Mirrors the notes/order_details pattern: any entity (topic, shelf item,
defect, …) can carry a list of relevant links. First consumer: Topics.
Rendered by the drop-in component templates/_entity_links.html.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    label       TEXT NOT NULL,
    url         TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def list_entity_links(conn: sqlite3.Connection, entity_type: str,
                      entity_id: str) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM entity_links WHERE entity_type=? AND entity_id=?"
        " ORDER BY label COLLATE NOCASE",
        (entity_type, str(entity_id))))


def add_entity_link(conn: sqlite3.Connection, entity_type: str, entity_id: str,
                    label: str, url: str) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO entity_links (entity_type, entity_id, label, url, created_at)"
            " VALUES (?,?,?,?,?)",
            (entity_type, str(entity_id), label.strip(), url.strip(),
             datetime.now().isoformat(timespec="seconds")))
    return cur.lastrowid


def delete_entity_link(conn: sqlite3.Connection, link_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM entity_links WHERE id=?", (link_id,))
