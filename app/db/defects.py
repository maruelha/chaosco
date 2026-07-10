"""Defects — imported rows, annotations, SolMan sync

Part of the app.db package (refactoring step 4) — split out of the old
monolithic database.py. Callers keep using `from app import database`,
which re-exports everything from these modules.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts

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
    statuses: list[str] | None = None,
    action_needed: str | None = None,
    exclude_statuses: list[str] | None = None,
    dtco2c: str | None = None,
    daily: str | None = None,
) -> list[dict]:
    """Return defects rows with optional filters, LEFT JOINed with defect_annotations."""
    sql = """
        SELECT d.defect_id, d.channel, d.country, d.solman_status, d.priority,
               d.assigned_to, d.excel_row, d.solman_name, d.exists_in_production,
               d.date_reported,
               COALESCE(a.action_needed, 0) AS action_needed,
               COALESCE(a.dtco2c, 0) AS dtco2c,
               COALESCE(a.daily, 0) AS daily,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'defect' AND n.entity_id = d.defect_id) AS note_count,
               (SELECT COUNT(*) FROM retail r WHERE r.defect_id_ref IS NOT NULL AND r.defect_id_ref LIKE '%' || d.defect_id || '%') AS blocked_tc_count
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
    if statuses:
        ph = ",".join("?" * len(statuses))
        sql += f" AND d.solman_status IN ({ph})"
        params.extend(statuses)
    elif exclude_statuses:
        ph = ",".join("?" * len(exclude_statuses))
        sql += f" AND (d.solman_status IS NULL OR d.solman_status NOT IN ({ph}))"
        params.extend(exclude_statuses)
    if action_needed == "yes":
        sql += " AND COALESCE(a.action_needed, 0) = 1"
    elif action_needed == "no":
        sql += " AND COALESCE(a.action_needed, 0) = 0"
    if dtco2c == "yes":
        sql += " AND COALESCE(a.dtco2c, 0) = 1"
    elif dtco2c == "no":
        sql += " AND COALESCE(a.dtco2c, 0) = 0"
    if daily == "yes":
        sql += " AND COALESCE(a.daily, 0) = 1"
    elif daily == "no":
        sql += " AND COALESCE(a.daily, 0) = 0"
    sql += " ORDER BY d.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_defect(conn: sqlite3.Connection, defect_id: str) -> dict | None:
    """Return one defect with its annotation fields (NULL if no annotation row exists)."""
    sql = """
        SELECT d.*,
               a.description, a.business_impact, a.reach, a.retest_needs,
               a.next_step, COALESCE(a.action_needed, 0) AS action_needed,
               a.comments, a.updated_at,
               COALESCE(a.dtco2c, 0) AS dtco2c, a.dtco2c_resp,
               COALESCE(a.daily, 0) AS daily
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE d.defect_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (defect_id,)))
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
    dtco2c: bool = False,
    dtco2c_resp: str | None = None,
    daily: bool = False,
) -> None:
    """Insert or update the annotation row for defect_id. Never touches the defects table."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO defect_annotations
                (defect_id, description, business_impact, reach, retest_needs,
                 next_step, action_needed, comments, dtco2c, dtco2c_resp, daily, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(defect_id) DO UPDATE SET
                description     = excluded.description,
                business_impact = excluded.business_impact,
                reach           = excluded.reach,
                retest_needs    = excluded.retest_needs,
                next_step       = excluded.next_step,
                action_needed   = excluded.action_needed,
                comments        = excluded.comments,
                dtco2c          = excluded.dtco2c,
                dtco2c_resp     = excluded.dtco2c_resp,
                daily           = excluded.daily,
                updated_at      = excluded.updated_at
            """,
            (defect_id, description, business_impact, reach, retest_needs,
             next_step, 1 if action_needed else 0, comments,
             1 if dtco2c else 0, dtco2c_resp, 1 if daily else 0, now),
        )


def set_defect_next_step(conn: sqlite3.Connection, defect_id: str,
                         next_step: str | None) -> None:
    """Only-this-field upsert (used by the next-step archive component)."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO defect_annotations (defect_id, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(defect_id) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
            """,
            (defect_id, next_step or None, now),
        )


def get_defect_next_step(conn: sqlite3.Connection, defect_id: str) -> str | None:
    row = conn.execute("SELECT next_step FROM defect_annotations WHERE defect_id=?",
                       (defect_id,)).fetchone()
    return row[0] if row else None


def set_defect_dtco2c(conn: sqlite3.Connection, defect_id: str, value: bool) -> None:
    """Set the dtco2c flag for a defect annotation. Creates the annotation row if absent."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO defect_annotations (defect_id, dtco2c, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(defect_id) DO UPDATE SET
                dtco2c     = excluded.dtco2c,
                updated_at = excluded.updated_at
            """,
            (defect_id, 1 if value else 0, now),
        )


def set_defect_daily(conn: sqlite3.Connection, defect_id: str, value: bool) -> None:
    """Set the daily flag for a defect annotation. Creates the annotation row if absent."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO defect_annotations (defect_id, daily, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(defect_id) DO UPDATE SET
                daily      = excluded.daily,
                updated_at = excluded.updated_at
            """,
            (defect_id, 1 if value else 0, now),
        )




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




def sync_solman_status(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    """Update solman_status and assigned_to for active defects from a SolMan export.

    Skips defects that are Withdrawn or Confirmed (case-insensitive).
    Skips defects not present in the DB (they may belong to other channels).

    Returns:
        {"updated": int, "skipped_not_found": int, "skipped_inactive": int}
    """
    _INACTIVE = {"withdrawn", "confirmed"}
    updated = skipped_not_found = skipped_inactive = 0

    for row in rows:
        existing = conn.execute(
            "SELECT solman_status FROM defects WHERE defect_id = ?", (row["defect_id"],)
        ).fetchone()

        if existing is None:
            skipped_not_found += 1
            continue

        if (existing[0] or "").lower() in _INACTIVE:
            skipped_inactive += 1
            continue

        conn.execute(
            "UPDATE defects SET solman_status = ?, assigned_to = ? WHERE defect_id = ?",
            (row["solman_status"], row["assigned_to"], row["defect_id"]),
        )
        updated += 1

    conn.commit()
    return {"updated": updated, "skipped_not_found": skipped_not_found, "skipped_inactive": skipped_inactive}


