"""Blockers — defects/tasks/business clarifications that block Delegated
Testing tickets (planning chat 2026-08-27). Own entity, own notes thread
(registry 'blocker'). A defect/task blocker's live status + comments come
from the SHARED jira store when its key is registered there — Marina adds
the blocker issue to her delegated Jira filter, the existing delegated
upload refreshes it like any other ticket; no separate import. Business
clarifications never carry a jira_key.

Registered blocker keys are EXCLUDED from the delegated board/report/
numbers (app.web_delegated._load_issues) — a ticket that IS a blocker must
not also show up as a testing ticket to work through.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import get_connection

TYPES = ("defect", "task", "clarification")

# (type key, section label) — fixed display order everywhere: defects first,
# then tasks, then clarifications [USER 2026-08-27]
TYPE_SECTIONS = [
    ("defect", "Defects"),
    ("task", "Tasks"),
    ("clarification", "Business Clarifications"),
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS blockers (
    blocker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL,
    name       TEXT NOT NULL,
    jira_key   TEXT,              -- NULL for business clarifications
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocker_links (
    blocker_id INTEGER NOT NULL,  -- FK blockers
    jira_key   TEXT NOT NULL,     -- FK jira_issues (the delegated ticket it blocks)
    created_at TEXT NOT NULL,
    PRIMARY KEY (blocker_id, jira_key)
);
CREATE INDEX IF NOT EXISTS idx_blocker_links_jira ON blocker_links(jira_key);
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


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _clean_jira_key(type_: str, jira_key: str | None) -> str | None:
    jira_key = (jira_key or "").strip() or None
    return None if type_ == "clarification" else jira_key


def create_blocker(conn: sqlite3.Connection, type_: str, name: str,
                   jira_key: str | None) -> dict:
    assert type_ in TYPES
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO blockers (type, name, jira_key, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (type_, name.strip(), _clean_jira_key(type_, jira_key), now, now))
    return get_blocker(conn, cur.lastrowid)


def update_blocker(conn: sqlite3.Connection, blocker_id: int, type_: str,
                   name: str, jira_key: str | None) -> None:
    assert type_ in TYPES
    with conn:
        conn.execute(
            "UPDATE blockers SET type=?, name=?, jira_key=?, updated_at=?"
            " WHERE blocker_id=?",
            (type_, name.strip(), _clean_jira_key(type_, jira_key), _now(),
             blocker_id))


def get_blocker(conn: sqlite3.Connection, blocker_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM blockers WHERE blocker_id=?", (blocker_id,)))
    return rows[0] if rows else None


def list_blockers(conn: sqlite3.Connection) -> list[dict]:
    """All blockers — defects, then tasks, then clarifications; alphabetical
    within each type."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM blockers ORDER BY"
        " CASE type WHEN 'defect' THEN 0 WHEN 'task' THEN 1 ELSE 2 END,"
        " LOWER(name)"))


def list_blocker_jira_keys(conn: sqlite3.Connection) -> set[str]:
    """Jira keys registered as blockers — used to exclude them from the
    delegated board/report/numbers. Tolerant of the table not existing yet
    (partial-init test fixtures, same pattern as db/delegated.py)."""
    try:
        return {row[0] for row in conn.execute(
            "SELECT jira_key FROM blockers WHERE jira_key IS NOT NULL")}
    except sqlite3.OperationalError:
        return set()


# ---------------------------------------------------------------------------
# Attach to tickets (build plan step 8, 2026-08-27) — blocker_links, m:n
# between a blocker and the delegated ticket(s) it blocks.

def link_blocker(conn: sqlite3.Connection, blocker_id: int, jira_key: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO blocker_links (blocker_id, jira_key, created_at)"
            " VALUES (?, ?, ?) ON CONFLICT (blocker_id, jira_key) DO NOTHING",
            (blocker_id, jira_key, _now()))


def unlink_blocker(conn: sqlite3.Connection, blocker_id: int, jira_key: str) -> None:
    with conn:
        conn.execute(
            "DELETE FROM blocker_links WHERE blocker_id=? AND jira_key=?",
            (blocker_id, jira_key))


def list_blockers_for_ticket(conn: sqlite3.Connection, jira_key: str) -> list[dict]:
    """Blockers attached to one delegated ticket — defects, then tasks,
    then clarifications; used for the chips on the board/detail page.
    Tolerant of the tables not existing yet (partial-init test fixtures)."""
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT b.* FROM blockers b"
            " JOIN blocker_links l ON l.blocker_id = b.blocker_id"
            " WHERE l.jira_key = ?"
            " ORDER BY CASE b.type WHEN 'defect' THEN 0 WHEN 'task' THEN 1 ELSE 2 END,"
            " LOWER(b.name)", (jira_key,)))
    except sqlite3.OperationalError:
        return []


def blockers_for_tickets(conn: sqlite3.Connection,
                         jira_keys: list[str]) -> dict[str, list[dict]]:
    """{jira_key: [blocker, ...]} for a batch of delegated tickets — one
    query for the whole board instead of one per row. Tolerant of the
    tables not existing yet (partial-init test fixtures)."""
    if not jira_keys:
        return {}
    out: dict[str, list[dict]] = {k: [] for k in jira_keys}
    placeholders = ",".join("?" for _ in jira_keys)
    try:
        rows = conn.execute(
            f"SELECT l.jira_key AS ticket_key, b.* FROM blocker_links l"
            f" JOIN blockers b ON b.blocker_id = l.blocker_id"
            f" WHERE l.jira_key IN ({placeholders})"
            f" ORDER BY CASE b.type WHEN 'defect' THEN 0 WHEN 'task' THEN 1 ELSE 2 END,"
            f" LOWER(b.name)", jira_keys)
    except sqlite3.OperationalError:
        return out
    cols = [d[0] for d in rows.description]
    for row in rows.fetchall():
        rec = dict(zip(cols, row))
        out[rec.pop("ticket_key")].append(rec)
    return out


def blocked_ticket_counts(conn: sqlite3.Connection) -> dict[int, int]:
    """{blocker_id: count of delegated tickets it blocks} — Blockers list
    page and (later) the Management Summary blocker overview."""
    try:
        return dict(conn.execute(
            "SELECT blocker_id, COUNT(*) FROM blocker_links GROUP BY blocker_id"))
    except sqlite3.OperationalError:
        return {}
