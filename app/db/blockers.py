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
