"""Sustain Call-outs (planning chat 2026-09-01) — Marina's own daily
monitoring log for the Core South Sustainphase, independent of any
imported workbook row. Deliberately its own table, never touched by
`sustain_importer.py` — user-authored data, same separation as
`urgent_items` / `sustain_issues` from their imported siblings.

Shown above the imported-days table on the sustain card (the daily
review list) and, filtered to open/in-progress, inside the management
summary per stream (channel 'both' appears in both streams).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

CALLOUT_CHANNELS = ["retail", "ecom", "both"]

CALLOUT_TYPES = [
    "Issue", "Spotcheck", "Observation", "MigrIssue", "OrgIssue", "Question",
]

# cycling chip order — open -> in_progress -> closed -> open
CALLOUT_STATUSES = ["open", "in_progress", "closed"]
STATUS_LABELS = {
    "open": "Open", "in_progress": "In Progress", "closed": "Closed",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sustain_callouts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    channel        TEXT NOT NULL,           -- retail | ecom | both
    type           TEXT NOT NULL,           -- CALLOUT_TYPES
    topic          TEXT NOT NULL,
    responsible    TEXT,
    status         TEXT NOT NULL DEFAULT 'open',
    date_captured  TEXT NOT NULL,           -- ISO 'YYYY-MM-DD'
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # additive migration for DBs created before next_step existed
        # (build plan step 3, 2026-09-01)
        try:
            conn.execute("ALTER TABLE sustain_callouts ADD COLUMN next_step TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_channel(channel: str | None) -> str:
    key = (channel or "").strip().lower()
    return key if key in CALLOUT_CHANNELS else CALLOUT_CHANNELS[0]


def _clean_type(type_: str | None) -> str:
    key = (type_ or "").strip()
    for t in CALLOUT_TYPES:
        if key.lower() == t.lower():
            return t
    return CALLOUT_TYPES[0]


def _clean_status(status: str | None) -> str:
    key = (status or "").strip().lower()
    return key if key in CALLOUT_STATUSES else CALLOUT_STATUSES[0]


def create_callout(conn: sqlite3.Connection, channel: str, type_: str,
                   topic: str, responsible: str | None = None) -> int:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO sustain_callouts (channel, type, topic, responsible,"
            " status, date_captured, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'open', ?, ?, ?)",
            (_clean_channel(channel), _clean_type(type_), topic.strip(),
             (responsible or "").strip() or None, date.today().isoformat(),
             now, now))
    return cur.lastrowid


def update_callout(conn: sqlite3.Connection, callout_id: int, channel: str,
                   type_: str, topic: str, responsible: str | None) -> None:
    with conn:
        conn.execute(
            "UPDATE sustain_callouts SET channel=?, type=?, topic=?,"
            " responsible=?, updated_at=? WHERE id=?",
            (_clean_channel(channel), _clean_type(type_), topic.strip(),
             (responsible or "").strip() or None, _now(), callout_id))


def set_status(conn: sqlite3.Connection, callout_id: int, status: str) -> None:
    with conn:
        conn.execute(
            "UPDATE sustain_callouts SET status=?, updated_at=? WHERE id=?",
            (_clean_status(status), _now(), callout_id))


def cycle_status(conn: sqlite3.Connection, callout_id: int) -> str | None:
    """Advances open -> in_progress -> closed -> open; returns the new
    status, or None if the id doesn't exist."""
    row = conn.execute(
        "SELECT status FROM sustain_callouts WHERE id=?",
        (callout_id,)).fetchone()
    if not row:
        return None
    cur = row[0] if row[0] in CALLOUT_STATUSES else CALLOUT_STATUSES[0]
    nxt = CALLOUT_STATUSES[(CALLOUT_STATUSES.index(cur) + 1) % len(CALLOUT_STATUSES)]
    set_status(conn, callout_id, nxt)
    return nxt


def get_callout_next_step(conn: sqlite3.Connection,
                          callout_id: int) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM sustain_callouts WHERE id=?",
        (callout_id,)).fetchone()
    return row[0] if row else None


def set_callout_next_step(conn: sqlite3.Connection, callout_id: int,
                          next_step: str | None) -> None:
    with conn:
        conn.execute(
            "UPDATE sustain_callouts SET next_step=?, updated_at=? WHERE id=?",
            ((next_step or "").strip() or None, _now(), callout_id))


def delete_callout(conn: sqlite3.Connection, callout_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM sustain_callouts WHERE id = ?", (callout_id,))


def get_callout(conn: sqlite3.Connection, callout_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM sustain_callouts WHERE id = ?", (callout_id,)))
    return rows[0] if rows else None


def list_callouts(conn: sqlite3.Connection,
                  include_closed: bool = False) -> list[dict]:
    """Newest-captured first; open/in_progress before closed when both are
    shown (daily review list on the card page). Tolerant of the table not
    existing yet (partial-init test fixtures / DBs from before this
    feature) — the card page must still render."""
    sql = "SELECT * FROM sustain_callouts"
    if not include_closed:
        sql += " WHERE status != 'closed'"
    sql += " ORDER BY date_captured DESC, id DESC"
    try:
        items = _rows_to_dicts(conn.execute(sql))
    except sqlite3.OperationalError:
        return []
    if include_closed:
        items.sort(key=lambda r: r["status"] == "closed")
    return items


def list_open_for_channel(conn: sqlite3.Connection, channel: str) -> list[dict]:
    """Open + in-progress call-outs for one stream's management summary:
    that channel's own items plus every 'both' item. Tolerant of the table
    not existing yet."""
    channel = _clean_channel(channel)
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT * FROM sustain_callouts WHERE status != 'closed'"
            " AND channel IN (?, 'both') ORDER BY date_captured DESC, id DESC",
            (channel,)))
    except sqlite3.OperationalError:
        return []


def callout_count(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM sustain_callouts WHERE status != 'closed'"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return 0
