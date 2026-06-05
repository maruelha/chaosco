"""Storage layer — the ONLY module that writes SQL.

Public API:
    init_db(db_path)              -> sqlite3.Connection
    upsert_defects(conn, rows, today) -> dict
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

_DATE_FIELDS = frozenset({"date_reported", "date_closed"})

# All columns that are refreshed on every import (everything except defect_id and first_seen).
_UPSERT_COLS = [
    "channel", "solman_name", "raised_by", "order_number",
    "date_reported", "country", "scenario", "exists_in_production",
    "affected_testcases_raw", "retest_dependency", "blocks_execution",
    "defect_reason", "solman_status", "priority", "assigned_to",
    "tech_team", "date_closed", "excel_row",
]

_ALL_INSERT_COLS = ["defect_id"] + _UPSERT_COLS + ["first_seen", "last_seen"]

_UPSERT_SQL = """
    INSERT INTO defects ({cols})
    VALUES ({placeholders})
    ON CONFLICT(defect_id) DO UPDATE SET
        {updates}
""".format(
    cols=", ".join(_ALL_INSERT_COLS),
    placeholders=", ".join(f":{c}" for c in _ALL_INSERT_COLS),
    # first_seen intentionally absent from the UPDATE clause — it is set once on INSERT only
    updates=",\n        ".join(
        f"{c} = excluded.{c}" for c in _UPSERT_COLS + ["last_seen"]
    ),
)


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open and return a connection. Schema must already exist (call init_db once first)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create schema if needed, return open connection. Call once at startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS defects (
            defect_id              TEXT PRIMARY KEY,
            channel                TEXT,
            solman_name            TEXT,
            raised_by              TEXT,
            order_number           TEXT,
            date_reported          TEXT,
            country                TEXT,
            scenario               TEXT,
            exists_in_production   TEXT,
            affected_testcases_raw TEXT,
            retest_dependency      TEXT,
            blocks_execution       TEXT,
            defect_reason          TEXT,
            solman_status          TEXT,
            priority               TEXT,
            assigned_to            TEXT,
            tech_team              TEXT,
            date_closed            TEXT,
            excel_row              INTEGER,
            first_seen             TEXT,
            last_seen              TEXT
        );

        -- User's structured annotations — created here, NEVER written by the importer.
        CREATE TABLE IF NOT EXISTS defect_annotations (
            defect_id        TEXT PRIMARY KEY REFERENCES defects(defect_id),
            description      TEXT,
            business_impact  TEXT,
            reach            TEXT,
            retest_needs     TEXT,
            next_step        TEXT,
            action_needed    INTEGER,
            comments         TEXT,
            updated_at       TEXT
        );

        -- User's append-only notes log — created here, NEVER written by the importer.
        CREATE TABLE IF NOT EXISTS defect_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            defect_id   TEXT REFERENCES defects(defect_id),
            created_at  TEXT,
            heading     TEXT,
            note        TEXT
        );
    """)
    conn.commit()
    return conn


def _normalise_date(val: str) -> str | None:
    """Return YYYY-MM-DD string, or None for blank / unrecognised values."""
    if not val or not val.strip():
        return None
    # pandas may produce "2026-05-28 00:00:00" — take the date part only
    s = val.strip().split(" ")[0].split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else (val.strip() or None)


def _is_blank_row(row: dict) -> bool:
    """True when every field value (excluding the excel_row counter) is empty."""
    return all(not str(v).strip() for k, v in row.items() if k != "excel_row")


def _build_record(row: dict, defect_id: str, today: str) -> dict:
    rec: dict = {"defect_id": defect_id, "first_seen": today, "last_seen": today}
    for col in _UPSERT_COLS:
        if col == "excel_row":
            rec[col] = row.get("excel_row")
        elif col in _DATE_FIELDS:
            rec[col] = _normalise_date(row.get(col, "") or "")
        else:
            s = str(row.get(col, "") or "").strip()
            rec[col] = s if s else None
    return rec


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_filter_options(conn: sqlite3.Connection) -> dict:
    """Return distinct channel and solman_status values for building filter dropdowns."""
    channels = [r[0] for r in conn.execute(
        "SELECT DISTINCT channel FROM defects WHERE channel IS NOT NULL ORDER BY channel"
    ).fetchall()]
    statuses = [r[0] for r in conn.execute(
        "SELECT DISTINCT solman_status FROM defects WHERE solman_status IS NOT NULL ORDER BY solman_status"
    ).fetchall()]
    return {"channels": channels, "statuses": statuses}


def list_defects(
    conn: sqlite3.Connection,
    search: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    action_needed: str | None = None,
) -> list[dict]:
    """Return defects rows with optional filters, LEFT JOINed with defect_annotations."""
    sql = """
        SELECT d.defect_id, d.channel, d.country, d.solman_status, d.priority,
               d.assigned_to, d.excel_row, d.solman_name,
               COALESCE(a.action_needed, 0) AS action_needed,
               (SELECT COUNT(*) FROM defect_notes n WHERE n.defect_id = d.defect_id) AS note_count
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE 1=1
    """
    params: list = []
    if search:
        sql += " AND d.defect_id LIKE ?"
        params.append(f"%{search}%")
    if channel:
        sql += " AND d.channel = ?"
        params.append(channel)
    if status:
        sql += " AND d.solman_status = ?"
        params.append(status)
    if action_needed == "yes":
        sql += " AND COALESCE(a.action_needed, 0) = 1"
    elif action_needed == "no":
        sql += " AND COALESCE(a.action_needed, 0) = 0"
    sql += " ORDER BY d.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_defect(conn: sqlite3.Connection, defect_id: str) -> dict | None:
    """Return one defect with its annotation fields (NULL if no annotation row exists)."""
    sql = """
        SELECT d.*,
               a.description, a.business_impact, a.reach, a.retest_needs,
               a.next_step, COALESCE(a.action_needed, 0) AS action_needed,
               a.comments, a.updated_at
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE d.defect_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (defect_id,)))
    return rows[0] if rows else None


def get_defect_annotation(conn: sqlite3.Connection, defect_id: str) -> dict | None:
    """Return the annotation row for a defect, or None if none exists yet."""
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM defect_annotations WHERE defect_id = ?", (defect_id,)
    ))
    return rows[0] if rows else None


def upsert_defect_annotation(
    conn: sqlite3.Connection,
    defect_id: str,
    description: str | None,
    business_impact: str | None,
    reach: str | None,
    retest_needs: str | None,
    next_step: str | None,
    action_needed: bool,
    comments: str | None,
) -> None:
    """Insert or update the annotation row for defect_id. Never touches the defects table."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO defect_annotations
                (defect_id, description, business_impact, reach, retest_needs,
                 next_step, action_needed, comments, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(defect_id) DO UPDATE SET
                description     = excluded.description,
                business_impact = excluded.business_impact,
                reach           = excluded.reach,
                retest_needs    = excluded.retest_needs,
                next_step       = excluded.next_step,
                action_needed   = excluded.action_needed,
                comments        = excluded.comments,
                updated_at      = excluded.updated_at
            """,
            (defect_id, description, business_impact, reach, retest_needs,
             next_step, 1 if action_needed else 0, comments, now),
        )


def list_notes_for_defect(conn: sqlite3.Connection, defect_id: str) -> list[dict]:
    """All notes for a defect, newest-first."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM defect_notes WHERE defect_id = ? ORDER BY created_at DESC",
        (defect_id,),
    ))


def get_note(conn: sqlite3.Connection, note_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM defect_notes WHERE id = ?", (note_id,)
    ))
    return rows[0] if rows else None


def add_note(
    conn: sqlite3.Connection,
    defect_id: str,
    heading: str | None,
    note_text: str | None,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT INTO defect_notes (defect_id, created_at, heading, note) VALUES (?, ?, ?, ?)",
            (defect_id, now, heading, note_text),
        )


def update_note(
    conn: sqlite3.Connection,
    note_id: int,
    heading: str | None,
    note_text: str | None,
) -> None:
    with conn:
        conn.execute(
            "UPDATE defect_notes SET heading = ?, note = ? WHERE id = ?",
            (heading, note_text, note_id),
        )


def delete_note(conn: sqlite3.Connection, note_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM defect_notes WHERE id = ?", (note_id,))


def upsert_defects(conn: sqlite3.Connection, rows: list[dict], today: str) -> dict:
    """Process rows and upsert into defects.  All writes are in one transaction.

    Returns:
        {
            "inserted": int,
            "updated": int,
            "skipped_blank_id": int,
            "skipped_duplicate": int,
            "ignored_blank": int,
            "skipped_rows": list[dict],   # rows to write to skip-log
        }
    """
    n_inserted = 0
    n_updated = 0
    n_skipped_blank_id = 0
    n_skipped_duplicate = 0
    n_ignored_blank = 0
    skipped_rows: list[dict] = []
    seen_ids: set[str] = set()

    with conn:
        existing_ids = {r[0] for r in conn.execute("SELECT defect_id FROM defects")}

        for row in rows:
            # 1. Entirely blank — ignore silently
            if _is_blank_row(row):
                n_ignored_blank += 1
                continue

            defect_id = str(row.get("defect_id", "") or "").strip()

            # 2. Has content but no defect_id — skip and log
            if not defect_id:
                n_skipped_blank_id += 1
                skipped_rows.append({**row, "reason": "blank_defect_id"})
                continue

            # 3. Duplicate defect_id within this import — keep first, skip rest
            if defect_id in seen_ids:
                n_skipped_duplicate += 1
                skipped_rows.append({**row, "reason": "duplicate_defect_id"})
                continue

            seen_ids.add(defect_id)
            is_new = defect_id not in existing_ids

            conn.execute(_UPSERT_SQL, _build_record(row, defect_id, today))

            if is_new:
                n_inserted += 1
                existing_ids.add(defect_id)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_blank_id": n_skipped_blank_id,
        "skipped_duplicate": n_skipped_duplicate,
        "ignored_blank": n_ignored_blank,
        "skipped_rows": skipped_rows,
    }
