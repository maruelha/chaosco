"""Missing Test Cases — the ONE list of test cases that do not exist yet
[USER 2026-08-30].

Until now the same gap was written down twice and drifted apart:

    Retail status report      config `retail_missing_categories` (settings.yaml)
    Retail Requirements board table `tracker_missing_tests` (free text only)

Both are now SEEDED FROM HERE — this module owns the list, everything else
renders it. An entry is a short title (what is missing) plus an optional
detail note (why it matters / what would have to be tested).

Second section: the RETROFITS (owned by app/db/retrofits.py — coming system
changes per channel). They are mirrored READ-ONLY, because a retrofit is the
usual reason a test case is missing. Their test coverage note
("no test case yet", "covered by TC-123") is authored on the RETROFITS page
[USER 2026-08-30] and lives on the retrofit row — this module, the Retail
Requirements board and the reports only display it.

SQL kept Postgres-portable (CLAUDE.md rule 7).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

# Retrofits shown on this page: Retail is the channel this list is about;
# 'ECOM & Retail' rows belong to Retail too (db/retrofits.list_retrofits
# already returns them for channel='Retail').
RETROFIT_CHANNEL = "Retail"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS missing_test_cases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,              -- the one-liner both reports show
    details    TEXT,                       -- the longer note (page + report)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


-- One-time flags (e.g. 'seeded'). Without it an emptied list would be
-- re-seeded from the legacy sources on the next restart.
CREATE TABLE IF NOT EXISTS missing_test_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------

def list_missing_tests(conn: sqlite3.Connection) -> list[dict]:
    """Oldest first — the list reads as a growing gap log, and both reports
    keep a stable order between two renders."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM missing_test_cases ORDER BY created_at, id"))


def get_missing_test(conn: sqlite3.Connection, item_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM missing_test_cases WHERE id = ?", (item_id,)))
    return rows[0] if rows else None


def create_missing_test(conn: sqlite3.Connection, title: str,
                        details: str | None = None) -> int:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO missing_test_cases (title, details, created_at, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (title.strip(), (details or "").strip() or None, now, now))
    return cur.lastrowid


def update_missing_test(conn: sqlite3.Connection, item_id: int, title: str,
                        details: str | None) -> None:
    with conn:
        conn.execute(
            "UPDATE missing_test_cases SET title=?, details=?, updated_at=?"
            " WHERE id=?",
            (title.strip(), (details or "").strip() or None, _now(), item_id))


def delete_missing_test(conn: sqlite3.Connection, item_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM missing_test_cases WHERE id = ?", (item_id,))


def missing_test_count(conn: sqlite3.Connection) -> int:
    """Dashboard card. Falls back to 0 where the table isn't there yet."""
    try:
        return conn.execute("SELECT COUNT(*) FROM missing_test_cases").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def list_for_report(conn: sqlite3.Connection) -> list[dict]:
    """What the Retail report and the Requirements board render. Same rows as
    list_missing_tests, but tolerant of a DB where the table doesn't exist —
    neither report may break because this module wasn't initialised."""
    try:
        return list_missing_tests(conn)
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# Retrofits (read-only mirror) + our coverage note
# ---------------------------------------------------------------------------

def list_retrofits_with_notes(conn: sqlite3.Connection,
                              channel: str = RETROFIT_CHANNEL) -> list[dict]:
    """The retrofit mirror for this page, the report, the email text and the
    Requirements board: rows straight from the retrofits module, with
    `coverage_note` filled from the retrofit's own `test_coverage_note`
    (authored on /retrofits). A missing retrofits table simply means an empty
    list — no page may depend on another feature being initialised."""
    from app.db import retrofits as db_retrofits
    try:
        items = db_retrofits.list_retrofits(conn, channel=channel or None)
    except sqlite3.OperationalError:
        return []
    for r in items:
        r["coverage_note"] = r.get("test_coverage_note")
    return items


# ---------------------------------------------------------------------------
# One-time seed from the two legacy sources
# ---------------------------------------------------------------------------

def _drop_legacy_table(conn: sqlite3.Connection) -> None:
    """Remove `tracker_missing_tests` — the board's old list. Only ever called
    AFTER its rows were copied into missing_test_cases (or after an earlier
    start set the 'seeded' flag, which by construction means the same), so no
    entry can be lost. Kept as its own step because the second computer runs
    the copy later than this one [USER 2026-08-30]."""
    conn.execute("DROP TABLE IF EXISTS tracker_missing_tests")


def seed_once(db_path: Path, config_categories: list[str] | None = None) -> int:
    """Fill the new list ONCE from where the two old lists lived:

        1. config `retail_missing_categories` (the Retail report bullets)
        2. table `tracker_missing_tests` (the board's alarm list)

    Guarded by the meta flag, not by "is the table empty" — deleting every
    entry must stay deleted across a restart. Returns how many rows it wrote.
    """
    conn = get_connection(db_path)
    try:
        done = conn.execute(
            "SELECT value FROM missing_test_meta WHERE key = 'seeded'").fetchone()
        if done:
            _drop_legacy_table(conn)   # already copied on an earlier start
            conn.commit()
            return 0
        now = _now()
        seen: set[str] = set()
        written = 0
        for title in (config_categories or []):
            title = (title or "").strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            conn.execute(
                "INSERT INTO missing_test_cases (title, details, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (title, "From the Retail status report list.", now, now))
            written += 1
        try:
            legacy = list(conn.execute(
                "SELECT text FROM tracker_missing_tests ORDER BY created_at, id"))
        except sqlite3.OperationalError:
            legacy = []
        for (text,) in legacy:
            text = (text or "").strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            conn.execute(
                "INSERT INTO missing_test_cases (title, details, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (text, "From the Retail Requirements board list.", now, now))
            written += 1
        conn.execute("INSERT INTO missing_test_meta (key, value) VALUES ('seeded', ?)",
                     (now,))
        _drop_legacy_table(conn)
        conn.commit()
        return written
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Email text (the copy & paste button)
# ---------------------------------------------------------------------------

def email_text(items: list[dict], retrofits: list[dict] | None = None,
               day: str | None = None) -> str:
    """Plain text for pasting into Outlook: the missing test cases with their
    detail note, and — when there are any — the retrofits with a coverage note
    underneath. Deliberately plain (no markdown), it is pasted as-is."""
    day = day or datetime.now().date().isoformat()
    lines = [f"Missing test cases — Retail (as of {day})", ""]
    if items:
        for i, item in enumerate(items, start=1):
            lines.append(f"{i}. {item['title']}")
            if item.get("details"):
                for para in str(item["details"]).splitlines():
                    if para.strip():
                        lines.append(f"   {para.strip()}")
            lines.append("")
    else:
        lines += ["No missing test cases recorded.", ""]
    if retrofits:
        lines += ["Retrofits (Retail) and their test coverage:",
                  "We need test cases for these as well.", ""]
        for r in retrofits:
            # the status is part of the message [USER 2026-08-30]: 'Potential'
            # means the change is NOT confirmed yet
            status = ("not confirmed" if (r.get("status") or "") == "Potential"
                      else "confirmed")
            expected = f", expected {r['expected']}" if r.get("expected") else ""
            lines.append(f"- {r['title']} ({status}{expected})")
            if r.get("coverage_note"):
                lines.append(f"   {r['coverage_note']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
