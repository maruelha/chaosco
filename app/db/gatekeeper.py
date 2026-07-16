"""Gatekeeper v2 — authored data per JIRA TICKET (start, 2026-07-11).

The Jira tickets table on /ecom-gatekeeper is the CURRENT gatekeeper
[USER 2026-07-11]; the manual ecom_gatekeeper rows are deprecated (kept).
Authored working fields live HERE, keyed by jira_key — the importer never
touches this table, and the key survives the later gatekeeper→ECOM
handover. Day plan step 3 will extend this module (internal_status,
push markers, …).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gatekeeper_annotations (
    jira_key   TEXT PRIMARY KEY,     -- FK jira_issues
    next_step  TEXT,
    updated_at TEXT
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # migrations (safe to re-run)
        for ddl in (
            # track on Sales report [USER 2026-07-16]: tickable on ANY ticket
            # in both views; the Sales report shows ticked tickets under
            # "With Sales" once they are no longer assigned to Marina.
            "ALTER TABLE gatekeeper_annotations ADD COLUMN track_sales INTEGER NOT NULL DEFAULT 0",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()


def get_gatekeeper_next_step(conn: sqlite3.Connection, jira_key: str) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM gatekeeper_annotations WHERE jira_key=?",
        (jira_key,)).fetchone()
    return row[0] if row else None


def get_gatekeeper_next_steps(conn: sqlite3.Connection) -> dict[str, str]:
    return {k: v for k, v in conn.execute(
        "SELECT jira_key, next_step FROM gatekeeper_annotations"
        " WHERE next_step IS NOT NULL")}


def set_gatekeeper_next_step(conn: sqlite3.Connection, jira_key: str,
                             next_step: str | None) -> None:
    """Only-this-field upsert (inline edit + next-step archive component)."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO gatekeeper_annotations (jira_key, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (jira_key, next_step or None, now))


def set_track_sales(conn: sqlite3.Connection, jira_key: str, track: int) -> None:
    """Only-this-field upsert for the 'track on Sales report' checkbox."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO gatekeeper_annotations (jira_key, track_sales, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                track_sales = excluded.track_sales,
                updated_at  = excluded.updated_at
        """, (jira_key, 1 if track else 0, now))


def get_track_sales_keys(conn: sqlite3.Connection) -> set[str]:
    try:
        return {k for (k,) in conn.execute(
            "SELECT jira_key FROM gatekeeper_annotations WHERE track_sales = 1")}
    except sqlite3.OperationalError:
        return set()  # schema not initialised (partial-init test fixtures)
