"""Shared Jira store — schema + all SQL (day plan 05.07 step 2).

ONE store, two consumers: the Gatekeeper v2 card (step 3) and the ECOM
vertical (steps 7-8) join it by jira_key. Filled ONLY by
app/jira_importer.py from Jira XML exports — never merged into
Excel-sourced tables (future-integration rule).

Re-import rule [USER 2026-07-05]: match by jira key; ONLY jira_status,
jira_assignee, the comments and — since 2026-07-11 — the ACCEPTANCE
CRITERIA refresh (it is living test data: testers fill order numbers into
it over time); every other field keeps its first-import value. Comments
are REPLACED per import (the export always carries the full thread; no
authors — the XML only has JIRAUSER keys).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app import database

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jira_issues (
    jira_key      TEXT PRIMARY KEY,
    solman_id     TEXT,              -- summary before the first "_" (may be NULL)
    summary       TEXT,
    epic          TEXT,
    markets       TEXT,
    jira_status   TEXT,              -- refreshed on re-import
    jira_assignee TEXT,              -- refreshed on re-import
    type          TEXT,
    priority      TEXT,
    description   TEXT,              -- HTML as exported
    acceptance_criteria TEXT,        -- checklist text; refreshed on re-import
    link          TEXT,
    created       TEXT,
    updated       TEXT,
    seen_in_gatekeeper INTEGER NOT NULL DEFAULT 0,  -- source tags: which
    seen_in_ecom       INTEGER NOT NULL DEFAULT 0,  -- import(s) carried it
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jira_comments (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    jira_key TEXT NOT NULL,          -- FK jira_issues
    created  TEXT,
    body     TEXT                    -- HTML; no author by design
);

CREATE INDEX IF NOT EXISTS idx_jira_comments_key ON jira_comments(jira_key);
"""


def init_schema(db_path: Path) -> None:
    conn = database.get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # migrations (safe to re-run)
        for ddl in (
            "ALTER TABLE jira_issues ADD COLUMN acceptance_criteria TEXT",
            "ALTER TABLE jira_issues ADD COLUMN seen_in_gatekeeper INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE jira_issues ADD COLUMN seen_in_ecom INTEGER NOT NULL DEFAULT 0",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def upsert_jira_issues(conn: sqlite3.Connection, issues: list[dict],
                       seen_in: str | None = None) -> dict:
    """Upsert parsed issues by jira_key. New keys: full insert. Existing keys:
    ONLY jira_status, jira_assignee, acceptance_criteria (living test data),
    last_seen refresh. Comments of every imported issue are REPLACED
    wholesale. seen_in ('gatekeeper'|'ecom') tags the source — the flag is
    set, never cleared (a ticket may legitimately live in both worlds).
    Returns counts."""
    assert seen_in in (None, "gatekeeper", "ecom")
    flag_col = f"seen_in_{seen_in}" if seen_in else None
    inserted = updated = comments = 0
    now = _now()
    with conn:
        for iss in issues:
            exists = conn.execute(
                "SELECT 1 FROM jira_issues WHERE jira_key=?",
                (iss["jira_key"],)).fetchone()
            if exists:
                conn.execute(
                    "UPDATE jira_issues SET jira_status=?, jira_assignee=?,"
                    " acceptance_criteria=?, last_seen=? WHERE jira_key=?",
                    (iss.get("jira_status"), iss.get("jira_assignee"),
                     iss.get("acceptance_criteria"), now, iss["jira_key"]))
                updated += 1
            else:
                conn.execute(
                    "INSERT INTO jira_issues (jira_key, solman_id, summary, epic,"
                    " markets, jira_status, jira_assignee, type, priority,"
                    " description, acceptance_criteria, link, created, updated,"
                    " first_seen, last_seen)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (iss["jira_key"], iss.get("solman_id"), iss.get("summary"),
                     iss.get("epic"), iss.get("markets"), iss.get("jira_status"),
                     iss.get("jira_assignee"), iss.get("type"), iss.get("priority"),
                     iss.get("description"), iss.get("acceptance_criteria"),
                     iss.get("link"), iss.get("created"),
                     iss.get("updated"), now, now))
                inserted += 1
            if flag_col:
                conn.execute(f"UPDATE jira_issues SET {flag_col}=1 WHERE jira_key=?",
                             (iss["jira_key"],))
            conn.execute("DELETE FROM jira_comments WHERE jira_key=?",
                         (iss["jira_key"],))
            for c in iss.get("comments", []):
                conn.execute(
                    "INSERT INTO jira_comments (jira_key, created, body) VALUES (?,?,?)",
                    (iss["jira_key"], c.get("created"), c.get("body")))
                comments += 1
    return {"inserted": inserted, "updated": updated, "comments": comments}


def get_jira_issue(conn: sqlite3.Connection, jira_key: str) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM jira_issues WHERE jira_key=?", (jira_key,)))
    return rows[0] if rows else None


def list_jira_issues(conn: sqlite3.Connection,
                     seen_in: str | None = None) -> list[dict]:
    """All issues, or only those tagged with one source
    (seen_in='gatekeeper'|'ecom') — the gatekeeper page uses the tag so a
    broad ECOM export can never flood its working list."""
    sql = "SELECT * FROM jira_issues"
    if seen_in in ("gatekeeper", "ecom"):
        sql += f" WHERE seen_in_{seen_in} = 1"
    sql += " ORDER BY jira_key"
    return _rows_to_dicts(conn.execute(sql))


def list_jira_comments(conn: sqlite3.Connection, jira_key: str) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT id, jira_key, created, body FROM jira_comments"
        " WHERE jira_key=? ORDER BY id", (jira_key,)))
