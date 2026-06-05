"""Storage layer — the ONLY module that writes SQL.

Public API:
    init_db(db_path)              -> sqlite3.Connection
    upsert_defects(conn, rows, today) -> dict
"""
from __future__ import annotations

import re
import sqlite3
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


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create database + all three tables (if they don't exist), return open connection."""
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
