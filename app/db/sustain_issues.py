"""Sustainphase Issues — storage (rewritten 2026-09-03 [USER]).

Source since 2026-09-03: the **Go-Live defect tracker** workbook, three
tabs → three imported tables (import pattern: one tab = one importer +
one table), plus two authored tables:

- `sustain_incidents`            ← tab "ASPEN Incidents" (upsert by
                                    Incident Number; rows without one are
                                    skipped [USER])
- `sustain_incident_comments`    ← column G "Latest comment/action" as a
                                    HISTORY: a new text is added ON TOP,
                                    the same text leaves it untouched
                                    [USER: "add on top instead of
                                    overwriting"]
- `sustain_incident_annotations` — authored next step per incident
- `sustain_issue_solutions`      ← tab "Issue Solution tracker", replaced
                                    wholesale per upload (rows have no
                                    identity; read-only page)
- `sustain_interfaces`           ← tab "Total" (the interface list),
                                    replaced per upload; the totals are
                                    COMPUTED here (interface_totals /
                                    reason_totals), never read from the
                                    sheet

The 2026-08-28 Defects-tab model (`sustain_issues` + SUS-nnn placeholders)
was RETIRED on 2026-09-03 [USER: "replace"] — its tables may still exist
in older DB files, untouched and unused.

Every table has a technical primary key [USER 2026-09-01]. Portable SQL
only (rule 7).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sustain_incidents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_number TEXT NOT NULL UNIQUE,
    date            TEXT,
    requestor       TEXT,
    title           TEXT,
    status          TEXT,
    assigned_to     TEXT,
    latest_comment  TEXT,
    excel_row       INTEGER,
    first_seen      TEXT,
    last_seen       TEXT
);

CREATE TABLE IF NOT EXISTS sustain_incident_comments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_number TEXT NOT NULL,
    text            TEXT NOT NULL,
    first_seen      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sustain_incident_comments
    ON sustain_incident_comments(incident_number, id);

CREATE TABLE IF NOT EXISTS sustain_incident_annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_number TEXT NOT NULL UNIQUE,
    next_step       TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS sustain_issue_solutions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner              TEXT,
    interface          TEXT,
    msg                TEXT,
    text               TEXT,
    external_reference TEXT,
    inc_reference      TEXT,
    reason             TEXT,
    solution           TEXT,
    status             TEXT,
    excel_row          INTEGER,
    imported_at        TEXT
);

CREATE TABLE IF NOT EXISTS sustain_interfaces (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace     TEXT,
    interface     TEXT,
    version       TEXT,
    name          TEXT,
    variant       TEXT,
    index_tables  TEXT,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    imported_at   TEXT
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


def _norm_text(text) -> str:
    """Comparison form for the comment history: whitespace collapsed,
    trimmed — a re-saved Excel that only re-wrapped the text is NOT a new
    comment."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


# ---------------------------------------------------------------------------
# ASPEN Incidents
# ---------------------------------------------------------------------------

INCIDENT_FIELDS = ("date", "requestor", "title", "status", "assigned_to",
                   "latest_comment")


def upsert_incidents(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    """Upsert by incident_number; the comment history gets a new entry
    when column G changed. Returns {'inserted', 'updated', 'new_comments'}.
    Rows without an incident number are the caller's business (skipped
    and counted in the importer)."""
    now = _now()
    counts = {"inserted": 0, "updated": 0, "new_comments": 0}
    with conn:
        for r in rows:
            key = r["incident_number"]
            existing = conn.execute(
                "SELECT id FROM sustain_incidents WHERE incident_number = ?",
                (key,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE sustain_incidents SET date=?, requestor=?, title=?,"
                    " status=?, assigned_to=?, latest_comment=?, excel_row=?,"
                    " last_seen=? WHERE incident_number=?",
                    (r.get("date"), r.get("requestor"), r.get("title"),
                     r.get("status"), r.get("assigned_to"), r.get("latest_comment"),
                     r.get("excel_row"), now, key))
                counts["updated"] += 1
            else:
                conn.execute(
                    "INSERT INTO sustain_incidents (incident_number, date, requestor,"
                    " title, status, assigned_to, latest_comment, excel_row,"
                    " first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (key, r.get("date"), r.get("requestor"), r.get("title"),
                     r.get("status"), r.get("assigned_to"), r.get("latest_comment"),
                     r.get("excel_row"), now, now))
                counts["inserted"] += 1
            # comment history: newest first; only a CHANGED text is added
            text = _norm_text(r.get("latest_comment"))
            if text:
                newest = conn.execute(
                    "SELECT text FROM sustain_incident_comments"
                    " WHERE incident_number = ? ORDER BY id DESC LIMIT 1",
                    (key,)).fetchone()
                if newest is None or _norm_text(newest[0]) != text:
                    conn.execute(
                        "INSERT INTO sustain_incident_comments"
                        " (incident_number, text, first_seen) VALUES (?, ?, ?)",
                        (key, text, now))
                    counts["new_comments"] += 1
    return counts


def incidents_by_status(conn: sqlite3.Connection) -> list[dict]:
    """[{status, incidents}, …] for the incidents REPORT [USER 2026-09-03:
    grouped by status]: groups in order of first appearance of the status
    over the date-desc list, "(no status)" last; incidents inside keep the
    list order (newest date first)."""
    groups: dict[str, list[dict]] = {}
    for i in list_incidents(conn):
        groups.setdefault(_norm_text(i.get("status")) or "(no status)", []).append(i)
    ordered = [{"status": k, "incidents": v} for k, v in groups.items() if k != "(no status)"]
    if "(no status)" in groups:
        ordered.append({"status": "(no status)", "incidents": groups["(no status)"]})
    return ordered


def list_incidents(conn: sqlite3.Connection) -> list[dict]:
    """All incidents, newest date first (then incident number desc)."""
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT * FROM sustain_incidents"
            " ORDER BY COALESCE(date, '') DESC, incident_number DESC"))
    except sqlite3.OperationalError:
        return []


def get_incident(conn: sqlite3.Connection, incident_number: str) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM sustain_incidents WHERE incident_number = ?",
        (incident_number,)))
    return rows[0] if rows else None


def incident_count(conn: sqlite3.Connection) -> int:
    """Dashboard badge — tolerant of the table not existing yet."""
    try:
        return conn.execute("SELECT COUNT(*) FROM sustain_incidents").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def comments_by_incident(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """{incident_number: [{text, first_seen}, …]} newest first — one query
    for the whole board."""
    out: dict[str, list[dict]] = {}
    try:
        rows = _rows_to_dicts(conn.execute(
            "SELECT incident_number, text, first_seen FROM sustain_incident_comments"
            " ORDER BY incident_number, id DESC"))
    except sqlite3.OperationalError:
        return out
    for r in rows:
        out.setdefault(r["incident_number"], []).append(
            {"text": r["text"], "first_seen": r["first_seen"]})
    return out


# ---- authored next step ----------------------------------------------------

def get_incident_annotations(conn: sqlite3.Connection) -> dict[str, dict]:
    try:
        return {r["incident_number"]: r for r in _rows_to_dicts(conn.execute(
            "SELECT incident_number, next_step, updated_at"
            " FROM sustain_incident_annotations"))}
    except sqlite3.OperationalError:
        return {}


def get_sustain_incident_next_step(conn: sqlite3.Connection,
                                   incident_number: str) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM sustain_incident_annotations WHERE incident_number = ?",
        (incident_number,)).fetchone()
    return row[0] if row else None


def set_sustain_incident_next_step(conn: sqlite3.Connection, incident_number: str,
                                   value: str | None) -> None:
    value = (value or "").strip() or None
    with conn:
        conn.execute("""
            INSERT INTO sustain_incident_annotations (incident_number, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(incident_number) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (incident_number, value, _now()))


# ---------------------------------------------------------------------------
# Issue Solution tracker (replaced wholesale per upload)
# ---------------------------------------------------------------------------

SOLUTION_FIELDS = ("owner", "interface", "msg", "text", "external_reference",
                   "inc_reference", "reason", "solution", "status")

# a tracker row counts as OPEN unless its Status is in this family
# (case-insensitive) — adjust here if the team's wording differs
SOLUTION_CLOSED_STATUSES = {"closed", "done", "resolved", "solved",
                            "completed", "fixed"}


def solution_is_open(status) -> bool:
    return _norm_text(status).casefold() not in SOLUTION_CLOSED_STATUSES


def replace_solutions(conn: sqlite3.Connection, rows: list[dict]) -> int:
    now = _now()
    with conn:
        conn.execute("DELETE FROM sustain_issue_solutions")
        conn.executemany(
            "INSERT INTO sustain_issue_solutions (owner, interface, msg, text,"
            " external_reference, inc_reference, reason, solution, status,"
            " excel_row, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [tuple(r.get(f) for f in SOLUTION_FIELDS) + (r.get("excel_row"), now)
             for r in rows])
    return len(rows)


def list_solutions(conn: sqlite3.Connection) -> list[dict]:
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT * FROM sustain_issue_solutions ORDER BY excel_row, id"))
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# Interfaces (tab "Total") + the computed totals
# ---------------------------------------------------------------------------

INTERFACE_FIELDS = ("namespace", "interface", "version", "name", "variant",
                    "index_tables")


def replace_interfaces(conn: sqlite3.Connection, rows: list[dict]) -> int:
    now = _now()
    with conn:
        conn.execute("DELETE FROM sustain_interfaces")
        conn.executemany(
            "INSERT INTO sustain_interfaces (namespace, interface, version, name,"
            " variant, index_tables, sort_order, imported_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [tuple(r.get(f) for f in INTERFACE_FIELDS) + (i, now)
             for i, r in enumerate(rows)])
    return len(rows)


def list_interfaces(conn: sqlite3.Connection) -> list[dict]:
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT * FROM sustain_interfaces ORDER BY sort_order, id"))
    except sqlite3.OperationalError:
        return []


def _key(value) -> str:
    return _norm_text(value).casefold()


def interface_totals(conn: sqlite3.Connection) -> dict:
    """The Total sheet, COMPUTED [USER 2026-09-03]: per listed interface
    the number of Issue-Solution-tracker rows whose Interface matches
    (Interface column only, case-insensitive) — once over ALL rows, once
    over OPEN rows only. Tracker interfaces that are on no listed row
    ("n/a" among them) get their own rows at the bottom, so the grand
    total equals the tracker's row count [USER: "just so the totals add
    up"]. Returns {'rows': [...], 'extra': [...], 'total_all', 'total_open'}."""
    solutions = _solutions_with_open_flag(conn)
    all_by_key: dict[str, int] = {}
    open_by_key: dict[str, int] = {}
    label_by_key: dict[str, str] = {}
    rows_by_key: dict[str, list[dict]] = {}
    for s in solutions:
        k = _key(s.get("interface"))
        label_by_key.setdefault(k, _norm_text(s.get("interface")) or "(blank)")
        all_by_key[k] = all_by_key.get(k, 0) + 1
        rows_by_key.setdefault(k, []).append(s)
        if s["is_open"]:
            open_by_key[k] = open_by_key.get(k, 0) + 1
    rows = []
    seen: set[str] = set()
    for i in list_interfaces(conn):
        k = _key(i.get("interface"))
        seen.add(k)
        rows.append({**i, "total_all": all_by_key.get(k, 0),
                     "total_open": open_by_key.get(k, 0),
                     "solutions": rows_by_key.get(k, [])})
    extra = [{"interface": label_by_key[k], "total_all": all_by_key[k],
              "total_open": open_by_key.get(k, 0),
              "solutions": rows_by_key[k]}
             for k in sorted(all_by_key, key=lambda k: label_by_key[k].casefold())
             if k not in seen]
    return {"rows": rows, "extra": extra,
            "total_all": len(solutions),
            "total_open": sum(1 for s in solutions if s["is_open"])}


def _solutions_with_open_flag(conn: sqlite3.Connection) -> list[dict]:
    """Tracker rows with `is_open`, open ones first (then sheet order) — the
    rows a Totals line expands to [USER 2026-09-03: "click on a line and get
    the rows shown that applies to"]."""
    rows = [{**s, "is_open": solution_is_open(s.get("status"))}
            for s in list_solutions(conn)]
    return sorted(rows, key=lambda s: (not s["is_open"], s.get("excel_row") or 0))


def reason_totals(conn: sqlite3.Connection) -> list[dict]:
    """[{reason, total_all, total_open}, …] over the tracker's Reason
    column, most frequent first; a blank reason is reported as "(blank)"."""
    counts: dict[str, dict] = {}
    for s in _solutions_with_open_flag(conn):
        label = _norm_text(s.get("reason")) or "(blank)"
        k = label.casefold()
        entry = counts.setdefault(k, {"reason": label, "total_all": 0,
                                      "total_open": 0, "solutions": []})
        entry["total_all"] += 1
        entry["solutions"].append(s)
        if s["is_open"]:
            entry["total_open"] += 1
    return sorted(counts.values(),
                  key=lambda e: (-e["total_all"], e["reason"].casefold()))
