"""Retrofits — planned/announced system changes per channel [USER 2026-08-10].

A retrofit is a change that is coming to the live system (ECOM or Retail) and
therefore matters for sign-off: it may invalidate what was already tested, or
it may still be announced late. The list is hand-maintained here and rendered
at the BOTTOM of the ECOM and Retail status reports, so the audience always
sees what is still moving.

Two statuses on purpose:
    Confirmed  — known and agreed, it is coming
    Potential  — might still come; keeps "don't forget what could still land"
                 visible instead of only listing what is already certain

`topic_id` optionally links a retrofit to a Topic (the active-work module) for
the full background — the report and the list page then link straight there.

SQL kept Postgres-portable (CLAUDE.md rule 7).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

RETROFIT_CHANNELS = ["ECOM", "Retail"]
RETROFIT_STATUSES = ["Confirmed", "Potential"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retrofits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel     TEXT NOT NULL,                    -- ECOM | Retail
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'Confirmed',-- Confirmed | Potential
    expected    TEXT,                             -- free text: when it lands
    topic_id    INTEGER,                          -- FK topics (optional)
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
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


def _clean_channel(channel: str | None) -> str:
    """Accept any casing from a form; store the canonical spelling."""
    for c in RETROFIT_CHANNELS:
        if (channel or "").strip().lower() == c.lower():
            return c
    return RETROFIT_CHANNELS[0]


def _clean_status(status: str | None) -> str:
    for s in RETROFIT_STATUSES:
        if (status or "").strip().lower() == s.lower():
            return s
    return RETROFIT_STATUSES[0]


def _add_topic_titles(conn: sqlite3.Connection, rows: list[dict]) -> list[dict]:
    """Fill topic_title for rows that link one.

    Deliberately a SECOND query instead of a LEFT JOIN on topics: a retrofit
    must stay readable even where the topics table doesn't exist (partial-init
    DB), and no feature should hard-depend on another feature's table just to
    render its own list. A missing topics table simply means no link is shown.
    """
    ids = {r["topic_id"] for r in rows if r.get("topic_id")}
    titles: dict = {}
    if ids:
        try:
            placeholders = ",".join("?" for _ in ids)
            titles = {row[0]: row[1] for row in conn.execute(
                f"SELECT id, title FROM topics WHERE id IN ({placeholders})",
                list(ids))}
        except sqlite3.OperationalError:
            titles = {}      # topics module not initialised here
    for r in rows:
        r["topic_title"] = titles.get(r.get("topic_id"))
    return rows


def list_retrofits(conn: sqlite3.Connection,
                   channel: str | None = None,
                   status: str | None = None) -> list[dict]:
    """All retrofits (newest first per channel), with the linked topic's title.

    Confirmed rows come before Potential ones so the report reads
    "this is coming" before "this might still come"."""
    sql = "SELECT * FROM retrofits WHERE 1=1"
    params: list = []
    if channel:
        sql += " AND channel = ?"
        params.append(_clean_channel(channel))
    if status:
        sql += " AND status = ?"
        params.append(_clean_status(status))
    sql += """
        ORDER BY channel,
                 CASE status WHEN 'Confirmed' THEN 0 ELSE 1 END,
                 id DESC
    """
    return _add_topic_titles(conn, _rows_to_dicts(conn.execute(sql, params)))


def get_retrofit(conn: sqlite3.Connection, retrofit_id: int) -> dict | None:
    rows = _add_topic_titles(conn, _rows_to_dicts(conn.execute(
        "SELECT * FROM retrofits WHERE id = ?", (retrofit_id,))))
    return rows[0] if rows else None


def create_retrofit(conn: sqlite3.Connection, channel: str, title: str,
                    description: str | None = None, status: str = "Confirmed",
                    expected: str | None = None,
                    topic_id: int | None = None) -> int:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO retrofits (channel, title, description, status,"
            " expected, topic_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_clean_channel(channel), title.strip(),
             (description or "").strip() or None, _clean_status(status),
             (expected or "").strip() or None, topic_id, now, now))
    return cur.lastrowid


def update_retrofit(conn: sqlite3.Connection, retrofit_id: int, channel: str,
                    title: str, description: str | None, status: str,
                    expected: str | None, topic_id: int | None) -> None:
    with conn:
        conn.execute(
            "UPDATE retrofits SET channel=?, title=?, description=?, status=?,"
            " expected=?, topic_id=?, updated_at=? WHERE id=?",
            (_clean_channel(channel), title.strip(),
             (description or "").strip() or None, _clean_status(status),
             (expected or "").strip() or None, topic_id, _now(), retrofit_id))


def delete_retrofit(conn: sqlite3.Connection, retrofit_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM retrofits WHERE id = ?", (retrofit_id,))


def retrofit_counts(conn: sqlite3.Connection) -> dict:
    """{'total': n, 'ECOM': n, 'Retail': n} — dashboard card + page header."""
    out = {"total": 0}
    for c in RETROFIT_CHANNELS:
        out[c] = 0
    for channel, n in conn.execute(
            "SELECT channel, COUNT(*) FROM retrofits GROUP BY channel"):
        out[channel] = n
        out["total"] += n
    return out
