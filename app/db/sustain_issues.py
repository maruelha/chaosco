"""Sustainphase Issues (planning chat 2026-08-28).

Imported from the **Defects tab** of `DTC_Sustainphase_Tracking….xlsx`
(uploaded on the card — see docs/claude/sustain-issues.md). Unlike the
replace-per-tab verticals this one UPSERTS: the natural key is the ASPEN
Defect ID, but issues can exist before they are in ASPEN [USER
2026-08-28] — those get an auto-assigned `SUS-nnn` placeholder key and
are matched across uploads by their normalized short description. When
the real Defect ID later appears the issue is "promoted": the key
switches to the Defect ID, annotations move along, and the placeholder
is kept in `former_placeholder` — no longer visible, still searchable.
Issues that disappear from the upload are kept (last_seen shows
staleness). The workbook's "Exists in production" column is ignored
entirely [USER].

`sustain_issue_annotations` is USER-AUTHORED (Marina's call-outs +
next step, archive entity `sustain_issue`) — imports never touch it
except to follow a key promotion.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import get_connection

PLACEHOLDER_PREFIX = "SUS-"

# imported issue fields, in workbook column order (minus the ignored
# "Exists in production"); defect_id/short_description handled separately
FIELD_COLUMNS = [
    "channel", "sales_dtc", "aspen_status", "description", "comment",
    "raised_by", "order_number", "date_reported", "date_closed",
    "priority", "assigned_to", "tech_team", "country", "scenario",
    "affected_testcases", "retest_dependency", "blocks_execution",
    "defect_reason", "excel_row",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sustain_issues (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_key           TEXT NOT NULL UNIQUE,
    defect_id           TEXT,
    former_placeholder  TEXT,
    channel             TEXT,
    sales_dtc           TEXT,
    aspen_status        TEXT,
    short_description   TEXT,
    description         TEXT,
    comment             TEXT,
    raised_by           TEXT,
    order_number        TEXT,
    date_reported       TEXT,
    date_closed         TEXT,
    priority            TEXT,
    assigned_to         TEXT,
    tech_team           TEXT,
    country             TEXT,
    scenario            TEXT,
    affected_testcases  TEXT,
    retest_dependency   TEXT,
    blocks_execution    TEXT,
    defect_reason       TEXT,
    excel_row           INTEGER,
    first_seen          TEXT,
    last_seen           TEXT
);

CREATE TABLE IF NOT EXISTS sustain_issue_annotations (
    issue_key  TEXT PRIMARY KEY,
    callouts   TEXT,
    next_step  TEXT,
    updated_at TEXT
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


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _norm_desc(text) -> str:
    """Fallback identity for issues without a Defect ID: lowercased,
    whitespace-collapsed short description."""
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _next_placeholder(conn: sqlite3.Connection) -> str:
    """SUS-001, SUS-002, … — numbers are never reused (a promoted issue
    keeps its old placeholder in former_placeholder, which counts)."""
    top = 0
    for (key,) in conn.execute(
            "SELECT issue_key FROM sustain_issues WHERE issue_key LIKE ?"
            " UNION SELECT former_placeholder FROM sustain_issues"
            " WHERE former_placeholder LIKE ?",
            (PLACEHOLDER_PREFIX + "%", PLACEHOLDER_PREFIX + "%")):
        try:
            top = max(top, int(key[len(PLACEHOLDER_PREFIX):]))
        except (TypeError, ValueError):
            continue
    return f"{PLACEHOLDER_PREFIX}{top + 1:03d}"


def _update_fields(conn: sqlite3.Connection, issue_id: int, row: dict) -> None:
    sets = ", ".join(f"{c} = ?" for c in FIELD_COLUMNS)
    conn.execute(
        f"UPDATE sustain_issues SET {sets}, short_description = ?,"
        f" last_seen = ? WHERE id = ?",
        [row.get(c) for c in FIELD_COLUMNS]
        + [row.get("short_description"), _now(), issue_id])


def upsert_issues(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    """Upsert one upload's Defects rows. Returns
    {'inserted': n, 'updated': n, 'promoted': n} — promoted = a
    placeholder issue whose real ASPEN Defect ID arrived in this upload.
    Rows with neither Defect ID nor short description are skipped
    (nothing to identify them by). Issues absent from the upload are
    KEPT (last_seen shows staleness)."""
    counts = {"inserted": 0, "updated": 0, "promoted": 0}
    with conn:
        for row in rows:
            defect_id = (str(row.get("defect_id")).strip()
                         if row.get("defect_id") is not None else "")
            desc_norm = _norm_desc(row.get("short_description"))
            if not defect_id and not desc_norm:
                continue
            if defect_id:
                hit = conn.execute(
                    "SELECT id FROM sustain_issues WHERE defect_id = ?",
                    (defect_id,)).fetchone()
                if hit:
                    _update_fields(conn, hit[0], row)
                    counts["updated"] += 1
                    continue
                # new Defect ID — did we track it as a placeholder before?
                placeholder = None
                if desc_norm:
                    for cand in _rows_to_dicts(conn.execute(
                            "SELECT id, issue_key, short_description"
                            " FROM sustain_issues WHERE defect_id IS NULL")):
                        if _norm_desc(cand["short_description"]) == desc_norm:
                            placeholder = cand
                            break
                if placeholder:
                    conn.execute(
                        "UPDATE sustain_issues SET issue_key = ?,"
                        " defect_id = ?, former_placeholder = ? WHERE id = ?",
                        (defect_id, defect_id, placeholder["issue_key"],
                         placeholder["id"]))
                    conn.execute(
                        "UPDATE sustain_issue_annotations SET issue_key = ?"
                        " WHERE issue_key = ?",
                        (defect_id, placeholder["issue_key"]))
                    _update_fields(conn, placeholder["id"], row)
                    counts["promoted"] += 1
                    continue
                key, is_new = defect_id, True
            else:
                # no Defect ID — match existing placeholder by description
                match = None
                for cand in _rows_to_dicts(conn.execute(
                        "SELECT id, short_description FROM sustain_issues"
                        " WHERE defect_id IS NULL")):
                    if _norm_desc(cand["short_description"]) == desc_norm:
                        match = cand
                        break
                if match:
                    _update_fields(conn, match["id"], row)
                    counts["updated"] += 1
                    continue
                key, is_new = _next_placeholder(conn), True
            if is_new:
                now = _now()
                cur = conn.execute(
                    "INSERT INTO sustain_issues (issue_key, defect_id,"
                    " short_description, first_seen, last_seen)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (key, defect_id or None, row.get("short_description"),
                     now, now))
                _update_fields(conn, cur.lastrowid, row)
                counts["inserted"] += 1
    return counts


def issue_count(conn: sqlite3.Connection) -> int:
    """Total tracked issues — dashboard card badge. Tolerant of the table
    not existing yet (partial-init test fixtures)."""
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM sustain_issues").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def list_issues(conn: sqlite3.Connection) -> list[dict]:
    """All tracked issues in workbook order (excel_row; keeps the Excel's
    reading order, stale kept issues sort by their last position)."""
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT * FROM sustain_issues ORDER BY excel_row, id"))
    except sqlite3.OperationalError:
        return []


def get_issue(conn: sqlite3.Connection, issue_key: str) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM sustain_issues WHERE issue_key = ?", (issue_key,)))
    return rows[0] if rows else None


# --- authored annotations (call-outs + next step) -----------------------

def get_sustain_issue_annotations(conn: sqlite3.Connection) -> dict[str, dict]:
    """{issue_key: {'callouts': ..., 'next_step': ...}}."""
    try:
        return {k: {"callouts": c, "next_step": ns}
                for k, c, ns in conn.execute(
                    "SELECT issue_key, callouts, next_step"
                    " FROM sustain_issue_annotations")}
    except sqlite3.OperationalError:
        return {}


def get_sustain_issue_next_step(conn: sqlite3.Connection,
                                issue_key: str) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM sustain_issue_annotations WHERE issue_key=?",
        (issue_key,)).fetchone()
    return row[0] if row else None


def set_sustain_issue_next_step(conn: sqlite3.Connection, issue_key: str,
                                next_step: str | None) -> None:
    """Only-this-field upsert (inline edit + archive entity
    'sustain_issue')."""
    with conn:
        conn.execute("""
            INSERT INTO sustain_issue_annotations (issue_key, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(issue_key) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (issue_key, (next_step or "").strip() or None, _now()))


def get_sustain_issue_callouts(conn: sqlite3.Connection,
                               issue_key: str) -> str | None:
    row = conn.execute(
        "SELECT callouts FROM sustain_issue_annotations WHERE issue_key=?",
        (issue_key,)).fetchone()
    return row[0] if row else None


def set_sustain_issue_callouts(conn: sqlite3.Connection, issue_key: str,
                               callouts: str | None) -> None:
    """Only-this-field upsert — Marina's call-outs/comment per issue."""
    with conn:
        conn.execute("""
            INSERT INTO sustain_issue_annotations (issue_key, callouts, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(issue_key) DO UPDATE SET
                callouts   = excluded.callouts,
                updated_at = excluded.updated_at
        """, (issue_key, (callouts or "").strip() or None, _now()))
