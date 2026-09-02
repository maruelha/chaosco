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

# responsible team [USER 2026-08-28] — the fixed combobox picks; "Other"
# adds a free-text value which then joins the combobox (team_options)
FIXED_TEAMS = ["Sales BIZ", "Omni", "DTC O2C", "PDM", "MB BIZ",
               # [USER 2026-08-31] both map to the BPO stage of the
               # Delegated Testing Overview (delegated_buckets._TEAM_STAGES)
               "Kibana", "ECOM BPO"]

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


# jira statuses that auto-close a jira-backed blocker [USER 2026-08-27:
# auto from Jira + manual] — same done-family as the delegated buckets
DONE_FAMILY = {"resolved", "closed", "done"}


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # migrations (safe to re-run) — 2026-08-27: comment/impact fields,
        # optional solman id (defects), BC-NNN display id (clarifications),
        # authored next step (archive entity 'blocker'), manual close.
        for ddl in (
            "ALTER TABLE blockers ADD COLUMN comment TEXT",
            "ALTER TABLE blockers ADD COLUMN impact TEXT",
            "ALTER TABLE blockers ADD COLUMN solman_id TEXT",
            "ALTER TABLE blockers ADD COLUMN display_id TEXT",
            "ALTER TABLE blockers ADD COLUMN next_step TEXT",
            "ALTER TABLE blockers ADD COLUMN closed_at TEXT",
            # responsible team (2026-08-28 [USER]) — fixed picks + free
            # "Other" text; custom values re-appear in the combobox
            "ALTER TABLE blockers ADD COLUMN team TEXT",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_blockers_display_id"
            " ON blockers(display_id) WHERE display_id IS NOT NULL")
        # Backfill BC ids for pre-existing clarifications, oldest first —
        # idempotent (only still-NULL rows are touched).
        pending = conn.execute(
            "SELECT blocker_id FROM blockers"
            " WHERE type = 'clarification' AND display_id IS NULL"
            " ORDER BY created_at, blocker_id").fetchall()
        for (bid,) in pending:
            conn.execute("UPDATE blockers SET display_id = ? WHERE blocker_id = ?",
                         (_next_bc_id(conn), bid))
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


def _clean_solman(type_: str, solman_id: str | None) -> str | None:
    """Optional second id for DEFECTS [USER 2026-08-27]. Kept on tasks too
    (no data loss on a defect→task type flip); clarifications never carry
    external system ids — same rule as the jira key."""
    solman_id = (solman_id or "").strip() or None
    return None if type_ == "clarification" else solman_id


def _next_bc_id(conn: sqlite3.Connection) -> str:
    """BC-001 style id for business clarifications [USER 2026-08-27] —
    3-digit zero-padded, grows past 999 without truncating."""
    max_n = 0
    for (did,) in conn.execute(
            "SELECT display_id FROM blockers WHERE display_id LIKE 'BC-%'"):
        try:
            max_n = max(max_n, int(did.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"BC-{max_n + 1:03d}"


def chip_label(row: dict) -> str:
    """What the compact chips on tickets show [USER 2026-08-27: "I only
    want to see the id"] — jira key, else BC id, else the name."""
    return row.get("jira_key") or row.get("display_id") or row.get("name") or ""


def is_closed(row: dict, jira_status: str | None) -> bool:
    """Closed = manually closed OR the jira ticket reached the done family
    [USER 2026-08-27: auto from Jira + manual]."""
    if row.get("closed_at"):
        return True
    return (jira_status or "").strip().lower() in DONE_FAMILY


def create_blocker(conn: sqlite3.Connection, type_: str, name: str,
                   jira_key: str | None, comment: str | None = None,
                   impact: str | None = None,
                   solman_id: str | None = None,
                   team: str | None = None) -> dict:
    assert type_ in TYPES
    now = _now()
    with conn:
        display_id = _next_bc_id(conn) if type_ == "clarification" else None
        cur = conn.execute(
            "INSERT INTO blockers (type, name, jira_key, comment, impact,"
            " solman_id, team, display_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (type_, name.strip(), _clean_jira_key(type_, jira_key),
             (comment or "").strip() or None, (impact or "").strip() or None,
             _clean_solman(type_, solman_id), (team or "").strip() or None,
             display_id, now, now))
    return get_blocker(conn, cur.lastrowid)


def update_blocker(conn: sqlite3.Connection, blocker_id: int, type_: str,
                   name: str, jira_key: str | None,
                   comment: str | None = None, impact: str | None = None,
                   solman_id: str | None = None,
                   team: str | None = None) -> None:
    assert type_ in TYPES
    with conn:
        conn.execute(
            "UPDATE blockers SET type=?, name=?, jira_key=?, comment=?,"
            " impact=?, solman_id=?, team=?, updated_at=? WHERE blocker_id=?",
            (type_, name.strip(), _clean_jira_key(type_, jira_key),
             (comment or "").strip() or None, (impact or "").strip() or None,
             _clean_solman(type_, solman_id), (team or "").strip() or None,
             _now(), blocker_id))
        # a row edited INTO a clarification gets its BC id if it has none
        # yet; an existing id is never regenerated or removed
        row = conn.execute(
            "SELECT display_id FROM blockers WHERE blocker_id=?",
            (blocker_id,)).fetchone()
        if type_ == "clarification" and row and row[0] is None:
            conn.execute("UPDATE blockers SET display_id=? WHERE blocker_id=?",
                         (_next_bc_id(conn), blocker_id))


def set_blocker_closed(conn: sqlite3.Connection, blocker_id: int,
                       closed: bool) -> None:
    """Manual close/reopen [USER 2026-08-27] — reopen only clears the
    MANUAL flag; a jira-backed blocker whose ticket is done stays closed
    via the auto rule until Jira reopens it."""
    now = _now()
    with conn:
        conn.execute(
            "UPDATE blockers SET closed_at=?, updated_at=? WHERE blocker_id=?",
            (now if closed else None, now, blocker_id))


def get_blocker_next_step(conn: sqlite3.Connection, blocker_id: int) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM blockers WHERE blocker_id=?",
        (blocker_id,)).fetchone()
    return row[0] if row else None


def set_blocker_next_step(conn: sqlite3.Connection, blocker_id: int,
                          next_step: str | None) -> None:
    """Only-this-field update (inline edit + next-step archive component,
    entity 'blocker')."""
    with conn:
        conn.execute(
            "UPDATE blockers SET next_step=?, updated_at=? WHERE blocker_id=?",
            (next_step or None, _now(), blocker_id))


def team_options(conn: sqlite3.Connection) -> list[str]:
    """Combobox choices: the fixed teams + every custom "Other" value
    already in use (case-insensitively deduped against the fixed list,
    alphabetical) [USER 2026-08-28: "once added it appears in the
    combobox"]. Tolerant of the table not existing yet."""
    fixed_norm = {t.casefold() for t in FIXED_TEAMS}
    custom: dict[str, str] = {}
    try:
        for (team,) in conn.execute(
                "SELECT DISTINCT team FROM blockers"
                " WHERE team IS NOT NULL AND TRIM(team) <> ''"):
            t = team.strip()
            if t.casefold() not in fixed_norm:
                custom.setdefault(t.casefold(), t)
    except sqlite3.OperationalError:
        pass
    return FIXED_TEAMS + sorted(custom.values(), key=str.casefold)


def set_blocker_team(conn: sqlite3.Connection, blocker_id: int,
                     team: str | None) -> None:
    """Only-this-field update — inline team pick on the Blockers list."""
    with conn:
        conn.execute(
            "UPDATE blockers SET team=?, updated_at=? WHERE blocker_id=?",
            ((team or "").strip() or None, _now(), blocker_id))


def set_blocker_impact(conn: sqlite3.Connection, blocker_id: int,
                       impact: str | None) -> None:
    """Only-this-field update — inline edit on the Management Summary's
    blocker overview [USER 2026-08-28: "so one can see at a glance what is
    blocked"]; same field as the detail form's Impact textarea."""
    with conn:
        conn.execute(
            "UPDATE blockers SET impact=?, updated_at=? WHERE blocker_id=?",
            ((impact or "").strip() or None, _now(), blocker_id))


def get_blocker(conn: sqlite3.Connection, blocker_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM blockers WHERE blocker_id=?", (blocker_id,)))
    return rows[0] if rows else None


def list_blockers(conn: sqlite3.Connection) -> list[dict]:
    """All blockers — defects, then tasks, then clarifications; alphabetical
    within each type. Tolerant of the table not existing yet (partial-init
    test fixtures, same pattern as the rest of this module)."""
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT * FROM blockers ORDER BY"
            " CASE type WHEN 'defect' THEN 0 WHEN 'task' THEN 1 ELSE 2 END,"
            " LOWER(name)"))
    except sqlite3.OperationalError:
        return []


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


def tickets_for_blockers(conn: sqlite3.Connection,
                         blocker_ids: list[int]) -> dict[int, list[str]]:
    """{blocker_id: [jira_key, …]} — the delegated tickets each blocker is
    attached to, one query for the batch, keys sorted. The reverse of
    blockers_for_tickets; feeds the per-team blocker report (2026-09-02).
    Tolerant of the tables not existing yet (partial-init test fixtures)."""
    if not blocker_ids:
        return {}
    out: dict[int, list[str]] = {b: [] for b in blocker_ids}
    placeholders = ",".join("?" for _ in blocker_ids)
    try:
        rows = conn.execute(
            f"SELECT blocker_id, jira_key FROM blocker_links"
            f" WHERE blocker_id IN ({placeholders})"
            f" ORDER BY jira_key", list(blocker_ids)).fetchall()
    except sqlite3.OperationalError:
        return out
    for blocker_id, jira_key in rows:
        out[blocker_id].append(jira_key)
    return out


def blocked_ticket_counts(conn: sqlite3.Connection) -> dict[int, int]:
    """{blocker_id: count of delegated tickets it blocks} — Blockers list
    page and (later) the Management Summary blocker overview."""
    try:
        return dict(conn.execute(
            "SELECT blocker_id, COUNT(*) FROM blocker_links GROUP BY blocker_id"))
    except sqlite3.OperationalError:
        return {}
