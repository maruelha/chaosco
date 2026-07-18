"""Entity connections — generic many-to-many links BETWEEN entities
[USER 2026-07-18].

Topics ↔ defects / retail test cases / ECOM rows / spillover items (any
pair of the supported types, most items have none). One direction-less
row per pair: sides are stored in canonical order so connecting from
either side is the same row — UNIQUE constraint dedupes. Labels are
resolved LIVE from the current tables (renames/re-imports stay fresh).
Rendered by the drop-in component templates/_connections.html.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

CONNECTABLE_TYPES = {"topic", "defect", "retail", "ecom", "spillover"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_connections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    a_type     TEXT NOT NULL,
    a_id       TEXT NOT NULL,
    b_type     TEXT NOT NULL,
    b_id       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (a_type, a_id, b_type, b_id)
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _canonical(t1: str, i1: str, t2: str, i2: str) -> tuple:
    """Direction-less storage: sides sorted by (type, id)."""
    a, b = sorted([(t1, str(i1)), (t2, str(i2))])
    return (*a, *b)


def add_connection(conn: sqlite3.Connection, t1: str, i1: str,
                   t2: str, i2: str) -> bool:
    """Create the pair; False when invalid, self-referencing, or existing."""
    if t1 not in CONNECTABLE_TYPES or t2 not in CONNECTABLE_TYPES:
        return False
    if (t1, str(i1)) == (t2, str(i2)):
        return False
    a_type, a_id, b_type, b_id = _canonical(t1, i1, t2, i2)
    with conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO entity_connections"
            " (a_type, a_id, b_type, b_id, created_at) VALUES (?,?,?,?,?)",
            (a_type, a_id, b_type, b_id,
             datetime.now().isoformat(timespec="seconds")))
    return cur.rowcount > 0


def delete_connection(conn: sqlite3.Connection, connection_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM entity_connections WHERE id=?", (connection_id,))


def list_connections_for(conn: sqlite3.Connection, entity_type: str,
                         entity_id: str) -> list[dict]:
    """Connections of one entity → [{id, type, entity_id}] of the OTHER side."""
    eid = str(entity_id)
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM entity_connections"
        " WHERE (a_type=? AND a_id=?) OR (b_type=? AND b_id=?)"
        " ORDER BY created_at",
        (entity_type, eid, entity_type, eid)))
    out = []
    for r in rows:
        if (r["a_type"], r["a_id"]) == (entity_type, eid):
            out.append({"id": r["id"], "type": r["b_type"], "entity_id": r["b_id"]})
        else:
            out.append({"id": r["id"], "type": r["a_type"], "entity_id": r["a_id"]})
    return out


def resolve_label(conn: sqlite3.Connection, entity_type: str,
                  entity_id: str) -> str | None:
    """Live display label for one entity — None when it does not exist."""
    eid = str(entity_id)
    if entity_type == "defect":
        row = conn.execute("SELECT defect_id, solman_name FROM defects"
                           " WHERE defect_id=?", (eid,)).fetchone()
        return f"{row[0]} — {row[1] or '(no name)'}" if row else None
    if entity_type == "retail":
        row = conn.execute("SELECT test_case_id, country FROM retail"
                           " WHERE retail_id=?", (eid,)).fetchone()
        return f"{row[0]} / {row[1]}" if row else None
    if entity_type == "ecom":
        row = conn.execute("SELECT jira_id, test_case_id, country FROM ecom"
                           " WHERE ecom_id=?", (eid,)).fetchone()
        return f"{row[0]} — {row[1] or '?'} / {row[2] or '?'}" if row else None
    if entity_type == "spillover":
        row = conn.execute("SELECT name, external_id FROM spillover"
                           " WHERE spillover_id=?", (eid,)).fetchone()
        if row is None:
            return None
        return f"{row[0]} ({row[1]})" if (row[1] or "").strip() else (row[0] or f"Spillover #{eid}")
    if entity_type == "topic":
        row = conn.execute("SELECT title FROM topics WHERE id=?", (eid,)).fetchone()
        return row[0] if row else None
    return None
