"""Delegated Testing — authored data per JIRA TICKET (start, 2026-08-26).

The Delegated Testing card lists tickets from its OWN Jira XML export
(uploaded on the card, tagged seen_in_delegated in the shared jira store).
Authored working fields live HERE, keyed by jira_key — the importer never
touches this table. Blocked tickets carry a "why blocked" reason; every
ticket has its own next step (archive component, entity type 'delegated' —
deliberately separate from the gatekeeper's next step on the same key).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS delegated_annotations (
    jira_key       TEXT PRIMARY KEY,  -- FK jira_issues
    blocked_reason TEXT,
    next_step      TEXT,
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS delegated_goal (
    id         INTEGER PRIMARY KEY,  -- always 1 — single row, no history
    goal       INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # migrations (safe to re-run)
        for ddl in (
            # counts_toward_goal (2026-08-27, build plan step 8): per-ticket
            # authored flag — whether a BLOCKED ticket's defect was found in
            # a way that counts toward the weekly goal (depends on WHERE the
            # defect was found [USER 2026-08-27]); NOT derived from status.
            "ALTER TABLE delegated_annotations ADD COLUMN"
            " counts_toward_goal INTEGER NOT NULL DEFAULT 0",
            # backlog (2026-08-27): parked tickets — own board section,
            # excluded from the Management Summary [USER 2026-08-27].
            "ALTER TABLE delegated_annotations ADD COLUMN"
            " backlog INTEGER NOT NULL DEFAULT 0",
            # req_tool (2026-08-29 [USER]): dashboard-only authored flag,
            # filterable checked/unchecked on the board — deliberately NOT
            # shown on either report [USER: "no report - it is ONLY on the
            # dashboard"].
            "ALTER TABLE delegated_annotations ADD COLUMN"
            " req_tool INTEGER NOT NULL DEFAULT 0",
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


def is_story_type(type_: str | None) -> bool:
    """User-story check for the delegated views [USER 2026-08-27]: matches
    by SUBSTRING ("Story", "User Story", …) — an exact 'story' comparison
    emptied Marina's board because her Jira wording differed. NULL
    (export without <type>) is tolerated as a story."""
    return type_ is None or "story" in type_.strip().lower()


def delegated_counts(conn: sqlite3.Connection) -> dict:
    """{'total': n, 'blocked': n} over the delegated-tagged tickets — the
    dashboard card badge. Mirrors web_delegated._load_issues since
    2026-08-27: user stories only (is_story_type) and registered blockers
    excluded — the badge must match what the board shows."""
    try:
        rows = conn.execute(
            "SELECT jira_key, jira_status, type FROM jira_issues"
            " WHERE seen_in_delegated = 1").fetchall()
    except sqlite3.OperationalError:
        return {"total": 0, "blocked": 0}  # jira schema not initialised yet
    from app.db.blockers import list_blocker_jira_keys
    blocker_keys = list_blocker_jira_keys(conn)
    kept = [(key, status) for key, status, type_ in rows
            if key not in blocker_keys and is_story_type(type_)]
    blocked = sum(1 for _key, status in kept
                  if (status or "").strip().lower() == "blocked")
    return {"total": len(kept), "blocked": blocked}


def get_delegated_annotations(conn: sqlite3.Connection) -> dict[str, dict]:
    """{jira_key: {'blocked_reason': ..., 'next_step': ...,
    'counts_toward_goal': ..., 'backlog': ..., 'req_tool': ...}} for the card."""
    try:
        return {k: {"blocked_reason": br, "next_step": ns,
                    "counts_toward_goal": bool(ctg), "backlog": bool(bl),
                    "req_tool": bool(rt)}
                for k, br, ns, ctg, bl, rt in conn.execute(
                    "SELECT jira_key, blocked_reason, next_step,"
                    " counts_toward_goal, backlog, req_tool FROM delegated_annotations")}
    except sqlite3.OperationalError:
        return {}  # schema not initialised (partial-init test fixtures)


def get_delegated_next_step(conn: sqlite3.Connection, jira_key: str) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM delegated_annotations WHERE jira_key=?",
        (jira_key,)).fetchone()
    return row[0] if row else None


def set_delegated_next_step(conn: sqlite3.Connection, jira_key: str,
                            next_step: str | None) -> None:
    """Only-this-field upsert (inline edit + next-step archive component)."""
    with conn:
        conn.execute("""
            INSERT INTO delegated_annotations (jira_key, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (jira_key, next_step or None, _now()))


def get_delegated_blocked_reason(conn: sqlite3.Connection, jira_key: str) -> str | None:
    row = conn.execute(
        "SELECT blocked_reason FROM delegated_annotations WHERE jira_key=?",
        (jira_key,)).fetchone()
    return row[0] if row else None


def set_delegated_blocked_reason(conn: sqlite3.Connection, jira_key: str,
                                 reason: str | None) -> None:
    """Only-this-field upsert for the 'why blocked' field."""
    with conn:
        conn.execute("""
            INSERT INTO delegated_annotations (jira_key, blocked_reason, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                blocked_reason = excluded.blocked_reason,
                updated_at     = excluded.updated_at
        """, (jira_key, reason or None, _now()))


def get_delegated_counts_toward_goal(conn: sqlite3.Connection, jira_key: str) -> bool:
    row = conn.execute(
        "SELECT counts_toward_goal FROM delegated_annotations WHERE jira_key=?",
        (jira_key,)).fetchone()
    return bool(row[0]) if row else False


def set_delegated_counts_toward_goal(conn: sqlite3.Connection, jira_key: str,
                                     value: bool) -> None:
    """Only-this-field upsert — whether a BLOCKED ticket's defect counts
    toward the weekly goal (depends on WHERE the defect was found, not on
    status; authored, an import never touches it)."""
    with conn:
        conn.execute("""
            INSERT INTO delegated_annotations (jira_key, counts_toward_goal, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                counts_toward_goal = excluded.counts_toward_goal,
                updated_at         = excluded.updated_at
        """, (jira_key, 1 if value else 0, _now()))


def get_delegated_backlog(conn: sqlite3.Connection, jira_key: str) -> bool:
    row = conn.execute(
        "SELECT backlog FROM delegated_annotations WHERE jira_key=?",
        (jira_key,)).fetchone()
    return bool(row[0]) if row else False


def set_delegated_backlog(conn: sqlite3.Connection, jira_key: str,
                          value: bool) -> None:
    """Only-this-field upsert — parked ticket: own Backlog board section,
    excluded from the Management Summary [USER 2026-08-27]."""
    with conn:
        conn.execute("""
            INSERT INTO delegated_annotations (jira_key, backlog, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                backlog    = excluded.backlog,
                updated_at = excluded.updated_at
        """, (jira_key, 1 if value else 0, _now()))


def get_delegated_req_tool(conn: sqlite3.Connection, jira_key: str) -> bool:
    row = conn.execute(
        "SELECT req_tool FROM delegated_annotations WHERE jira_key=?",
        (jira_key,)).fetchone()
    return bool(row[0]) if row else False


def set_delegated_req_tool(conn: sqlite3.Connection, jira_key: str,
                           value: bool) -> None:
    """Only-this-field upsert — dashboard-only flag [USER 2026-08-29],
    deliberately never read by report_context/numbers_context."""
    with conn:
        conn.execute("""
            INSERT INTO delegated_annotations (jira_key, req_tool, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_key) DO UPDATE SET
                req_tool   = excluded.req_tool,
                updated_at = excluded.updated_at
        """, (jira_key, 1 if value else 0, _now()))


def get_delegated_goal(conn: sqlite3.Connection) -> int:
    """ONE number, editable on the Management Summary — no history is kept
    [USER 2026-08-27]; downloaded reports are the history."""
    row = conn.execute("SELECT goal FROM delegated_goal WHERE id = 1").fetchone()
    return row[0] if row else 0


def set_delegated_goal(conn: sqlite3.Connection, goal: int) -> None:
    with conn:
        conn.execute("""
            INSERT INTO delegated_goal (id, goal, updated_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                goal       = excluded.goal,
                updated_at = excluded.updated_at
        """, (goal, _now()))
