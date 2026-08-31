"""Email report recipients and send groups (app.db.email).

Recipients for the "Email reports" feature live in the DB (not config) so
they can be managed in the UI. SMTP credentials live in settings.local.yaml
(gitignored) — never in code, never in this table.

A **group** (table `email_lists`, "mailing list" until 2026-08-31) is a whole
saved send: its recipients, WHICH REPORTS they get, and optionally the subject
and text to use [USER 2026-08-31]. Management and key users want different
packs and different wording — one click sets all of it.
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

-- Groups [USER 2026-07-09 as "mailing lists", extended 2026-08-31] = a named
-- saved send: recipients + reports + optional subject/text. Clicking a group
-- on /email-report applies all of it; saving under an existing name REPLACES
-- that group.
CREATE TABLE IF NOT EXISTS email_lists (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    subject    TEXT,                             -- optional, own wording
    body       TEXT,                             -- optional, own wording
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_list_members (
    list_id      INTEGER NOT NULL,               -- FK email_lists
    recipient_id INTEGER NOT NULL,               -- FK report_recipients
    UNIQUE(list_id, recipient_id)
);

-- Which reports this group always gets (keys from emailer.REPORT_CHOICES).
CREATE TABLE IF NOT EXISTS email_list_reports (
    list_id     INTEGER NOT NULL,                -- FK email_lists
    report_key  TEXT NOT NULL,
    UNIQUE(list_id, report_key)
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # additive migrations for DBs created before 2026-08-31
        for column in ("subject", "body"):
            try:
                conn.execute(f"ALTER TABLE email_lists ADD COLUMN {column} TEXT")
            except sqlite3.OperationalError:
                pass                              # already there
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
            "INSERT INTO report_recipients (email, name, active, created_at)"
            " VALUES (?, ?, 1, ?) ON CONFLICT(email) DO NOTHING",
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
                    recipient_ids: list[int],
                    report_keys: list[str] | None = None,
                    subject: str | None = None,
                    body: str | None = None) -> int:
    """Create a group, or REPLACE an existing one (same name).

    A group is the whole send [USER 2026-08-31]: its recipients, the reports
    they get, and optionally its own subject/text. Passing None for
    report_keys/subject/body keeps what the group already has — so saving only
    a recipient change never silently drops a group's report set."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("INSERT INTO email_lists (name, created_at)"
                     " VALUES (?,?) ON CONFLICT(name) DO NOTHING", (name, now))
        list_id = conn.execute("SELECT id FROM email_lists WHERE name=?",
                               (name,)).fetchone()[0]
        conn.execute("DELETE FROM email_list_members WHERE list_id=?", (list_id,))
        for rid in recipient_ids:
            conn.execute(
                "INSERT INTO email_list_members (list_id, recipient_id)"
                " VALUES (?,?) ON CONFLICT(list_id, recipient_id) DO NOTHING",
                (list_id, int(rid)))
        if report_keys is not None:
            conn.execute("DELETE FROM email_list_reports WHERE list_id=?", (list_id,))
            for key in report_keys:
                conn.execute(
                    "INSERT INTO email_list_reports (list_id, report_key)"
                    " VALUES (?,?) ON CONFLICT(list_id, report_key) DO NOTHING",
                    (list_id, str(key)))
        if subject is not None or body is not None:
            conn.execute(
                "UPDATE email_lists SET subject=?, body=? WHERE id=?",
                ((subject or "").strip() or None,
                 (body or "").strip() or None, list_id))
    return list_id


def list_email_lists(conn: sqlite3.Connection) -> list[dict]:
    """All groups with everything a click has to apply: member recipient ids,
    report keys, and the group's own subject/body when it has them."""
    lists = _rows_to_dicts(conn.execute(
        "SELECT * FROM email_lists ORDER BY name"))
    for lst in lists:
        lst["member_ids"] = [r[0] for r in conn.execute(
            "SELECT recipient_id FROM email_list_members WHERE list_id=?"
            " ORDER BY recipient_id", (lst["id"],))]
        lst["report_keys"] = [r[0] for r in conn.execute(
            "SELECT report_key FROM email_list_reports WHERE list_id=?"
            " ORDER BY report_key", (lst["id"],))]
    return lists


def delete_email_list(conn: sqlite3.Connection, list_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM email_list_members WHERE list_id=?", (list_id,))
        conn.execute("DELETE FROM email_list_reports WHERE list_id=?", (list_id,))
        conn.execute("DELETE FROM email_lists WHERE id=?", (list_id,))
