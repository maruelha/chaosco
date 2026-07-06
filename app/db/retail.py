"""Retail — imported test-case rows, annotations, report counts

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

# ---------------------------------------------------------------------------
# Retail upsert SQL
# ---------------------------------------------------------------------------

_RETAIL_MUTABLE = [
    "test_case_id", "country",
    "testcase_name", "testcase_scenario", "status", "assigned_to",
    "key_user_responsible", "evidence_in_sharepoint", "sales_file",
    "execution_started", "execution_completed", "order_number",
    "old_order_numbers", "defect_id_ref", "s4_sales_order",
    "s4_billing_documents", "s4_journal_invoice_entry", "delivery_note",
    "comment", "reason_for_pass_with_reservation", "excel_row",
]
_RETAIL_INSERT_COLS = _RETAIL_MUTABLE + ["match_key", "first_seen", "last_seen"]

_RETAIL_UPSERT_SQL = """
    INSERT INTO retail ({cols})
    VALUES ({placeholders})
    ON CONFLICT(match_key) DO UPDATE SET
        {updates}
""".format(
    cols=", ".join(_RETAIL_INSERT_COLS),
    placeholders=", ".join(f":{c}" for c in _RETAIL_INSERT_COLS),
    updates=",\n        ".join(
        f"{c} = excluded.{c}" for c in _RETAIL_MUTABLE + ["last_seen"]
    ),
)




def _retail_match_key(test_case_id: str, country: str) -> str:
    return "||".join(
        re.sub(r"\s+", " ", str(p or "")).strip().lower()
        for p in (test_case_id, country)
    )




def upsert_retail_rows(conn: sqlite3.Connection, rows: list[dict], today: str) -> dict:
    """Match-key upsert for retail rows. Never deletes. Returns counts + skipped rows."""
    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    skipped_rows: list[dict] = []

    with conn:
        existing_keys = {r[0] for r in conn.execute("SELECT match_key FROM retail")}

        for row in rows:
            if row.get("_skip_reason"):
                n_skipped += 1
                skipped_rows.append({**row, "reason": row["_skip_reason"]})
                continue

            mk = _retail_match_key(
                row.get("test_case_id", "") or "",
                row.get("country", "") or "",
            )
            is_new = mk not in existing_keys

            def _s(field: str):
                v = str(row.get(field, "") or "").strip()
                return v if v else None

            rec = {col: _s(col) for col in _RETAIL_MUTABLE if col != "excel_row"}
            rec["excel_row"] = row.get("excel_row")
            rec["match_key"] = mk
            rec["first_seen"] = today
            rec["last_seen"] = today

            conn.execute(_RETAIL_UPSERT_SQL, rec)
            if is_new:
                n_inserted += 1
                existing_keys.add(mk)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_blank_key": n_skipped,
        "skipped_rows": skipped_rows,
    }


def get_retail(
    conn: sqlite3.Connection,
    statuses: list[str] | None = None,
    assignees: list[str] | None = None,
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    search_defect: str | None = None,
    search_order: str | None = None,
    search_billing: str | None = None,
    action_needed: str | None = None,
) -> list[dict]:
    """Return retail rows LEFT JOINed with annotations. All filters/searches optional and ANDed."""
    sql = """
        SELECT r.*,
               a.next_step, a.comment_history,
               a.updated_at AS annotation_updated_at,
               COALESCE(a.action_needed, 0) AS action_needed,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'retail'
                AND n.entity_id = CAST(r.retail_id AS TEXT)) AS note_count
        FROM retail r
        LEFT JOIN retail_annotations a ON a.retail_id = r.retail_id
        WHERE 1=1
    """
    params: list = []
    sql_parts: list[str] = []

    def _in(col: str, values: list[str]) -> None:
        ph = ",".join("?" * len(values))
        sql_parts.append(f" AND {col} IN ({ph})")
        params.extend(values)

    if statuses:   _in("r.status", statuses)
    if assignees:  _in("r.assigned_to", assignees)
    if countries:  _in("r.country", countries)
    if scenarios:  _in("r.testcase_scenario", scenarios)
    sql += "".join(sql_parts)

    if search_defect:
        sql += " AND r.defect_id_ref LIKE ?"
        params.append(f"%{search_defect}%")
    if search_order:
        sql += " AND r.order_number LIKE ?"
        params.append(f"%{search_order}%")
    if search_billing:
        sql += " AND r.s4_billing_documents LIKE ?"
        params.append(f"%{search_billing}%")

    if action_needed == "yes":
        sql += " AND COALESCE(a.action_needed, 0) = 1"
    elif action_needed == "no":
        sql += " AND COALESCE(a.action_needed, 0) = 0"

    sql += " ORDER BY r.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_retail_filter_options(conn: sqlite3.Connection) -> dict:
    def _vals(col: str) -> list:
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM retail WHERE {col} IS NOT NULL ORDER BY {col}"
        ).fetchall()]
    return {
        "statuses":  _vals("status"),
        "assignees": _vals("assigned_to"),
        "countries": _vals("country"),
        "scenarios": _vals("testcase_scenario"),
    }


def get_retail_by_id(conn: sqlite3.Connection, retail_id: int) -> dict | None:
    sql = """
        SELECT r.*,
               a.next_step, a.comment_history,
               a.updated_at AS annotation_updated_at,
               COALESCE(a.action_needed, 0) AS action_needed,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'retail'
                AND n.entity_id = CAST(r.retail_id AS TEXT)) AS note_count
        FROM retail r
        LEFT JOIN retail_annotations a ON a.retail_id = r.retail_id
        WHERE r.retail_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (retail_id,)))
    return rows[0] if rows else None


def get_retail_annotation(conn: sqlite3.Connection, retail_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM retail_annotations WHERE retail_id = ?", (retail_id,)
    ))
    return rows[0] if rows else None


def upsert_retail_annotation(
    conn: sqlite3.Connection,
    retail_id: int,
    next_step: str | None,
    comment_history: str | None,
    action_needed: int = 0,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO retail_annotations (retail_id, next_step, comment_history, action_needed, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(retail_id) DO UPDATE SET
                next_step       = excluded.next_step,
                comment_history = excluded.comment_history,
                action_needed   = excluded.action_needed,
                updated_at      = excluded.updated_at
            """,
            (retail_id, next_step, comment_history, action_needed, now),
        )


def get_retail_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {status_value: count} for all rows in the retail table.

    Kept as a standalone function so a future step can persist the raw counts
    before passing them to reporter.compute_retail_report().
    """
    rows = conn.execute(
        "SELECT COALESCE(status, '') AS status, COUNT(*) AS cnt FROM retail GROUP BY status"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_retail_defects_impacted(conn: sqlite3.Connection,
                                passed_statuses: list[str]) -> list[dict]:
    """Return all active (non-confirmed/withdrawn) Retail-channel defects with
    IMPACTED test-case counts.

    "Impacted" [USER 2026-07-06]: the test case references the defect
    (defect_id_ref) AND has not passed yet — a passed test is no longer
    impacted even if the reference is still written in the Excel column.
    passed_statuses is the report's passed family (status_mappings
    passed_with_dtc — ONE definition of "passed"); passed_tc_count keeps
    those visible as muted info. dtco2c splits totals into MB (our
    follow-up) vs Sales; dtco2c_unset marks defects where nobody decided
    (they count as Sales — diagnostics lists them)."""
    passed_keys = [s.strip().lower() for s in passed_statuses]
    ph = ",".join("?" for _ in passed_keys) or "''"
    sql = f"""
        SELECT d.defect_id, d.solman_name, d.assigned_to, d.date_reported,
               d.solman_status,
               COALESCE(a.dtco2c, 0) AS dtco2c,
               (a.dtco2c IS NULL) AS dtco2c_unset,
               (SELECT COUNT(*) FROM retail r
                WHERE r.defect_id_ref IS NOT NULL
                  AND r.defect_id_ref LIKE '%' || d.defect_id || '%'
                  AND LOWER(TRIM(COALESCE(r.status, ''))) NOT IN ({ph})) AS impacted_tc_count,
               (SELECT COUNT(*) FROM retail r
                WHERE r.defect_id_ref IS NOT NULL
                  AND r.defect_id_ref LIKE '%' || d.defect_id || '%'
                  AND LOWER(TRIM(COALESCE(r.status, ''))) IN ({ph})) AS passed_tc_count
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE LOWER(TRIM(d.channel)) = 'retail'
          AND LOWER(TRIM(COALESCE(d.solman_status, ''))) NOT IN ('confirmed', 'withdrawn')
        ORDER BY impacted_tc_count DESC, d.defect_id
    """
    return _rows_to_dicts(conn.execute(sql, (*passed_keys, *passed_keys)))


