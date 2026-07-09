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

-- Mailing lists [USER 2026-07-09] = named recipient selections. Clicking a
-- list on /email-report ticks exactly its members; saving the current
-- selection under an existing name REPLACES that list's members.
CREATE TABLE IF NOT EXISTS email_lists (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_list_members (
    list_id      INTEGER NOT NULL,               -- FK email_lists
    recipient_id INTEGER NOT NULL,               -- FK report_recipients
    UNIQUE(list_id, recipient_id)
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
        conn.execute("DELETE FROM email_list_members WHERE recipient_id=?", (rid,))
        conn.execute("DELETE FROM report_recipients WHERE id=?", (rid,))


# ---------------------------------------------------------------------------
# Mailing lists
# ---------------------------------------------------------------------------

def save_email_list(conn: sqlite3.Connection, name: str,
                    recipient_ids: list[int]) -> int:
    """Create a list, or REPLACE the members of an existing one (same name).
    Saving 'the current selection' twice under one name = update."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("INSERT OR IGNORE INTO email_lists (name, created_at)"
                     " VALUES (?,?)", (name, now))
        list_id = conn.execute("SELECT id FROM email_lists WHERE name=?",
                               (name,)).fetchone()[0]
        conn.execute("DELETE FROM email_list_members WHERE list_id=?", (list_id,))
        for rid in recipient_ids:
            conn.execute(
                "INSERT OR IGNORE INTO email_list_members (list_id, recipient_id)"
                " VALUES (?,?)", (list_id, int(rid)))
    return list_id


def list_email_lists(conn: sqlite3.Connection) -> list[dict]:
    """All lists with their member recipient ids (for the select buttons)."""
    lists = _rows_to_dicts(conn.execute(
        "SELECT * FROM email_lists ORDER BY name"))
    for lst in lists:
        lst["member_ids"] = [r[0] for r in conn.execute(
            "SELECT recipient_id FROM email_list_members WHERE list_id=?"
            " ORDER BY recipient_id", (lst["id"],))]
    return lists


def delete_email_list(conn: sqlite3.Connection, list_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM email_list_members WHERE list_id=?", (list_id,))
        conn.execute("DELETE FROM email_lists WHERE id=?", (list_id,))
