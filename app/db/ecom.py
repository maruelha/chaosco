"""ECOM vertical — imported test-case rows + authored annotations
(day plan 05.07 step 7).

Own tab = own importer + own table (CLAUDE.md rule 1). Match key = the
JIRA ID [USER 2026-07-05] — the ECOM tab carries one per row and the
Gatekeeper v2 handover later relinks by the same key. Excel fields and
Jira fields stay strictly separate: excel `status`/`assigned_to` here are
NOT the same thing as jira_status/jira_assignee in the shared jira store
(joined read-only by jira id in step 8).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app import database
from app.db.core import _rows_to_dicts

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ecom (
    ecom_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    match_key          TEXT NOT NULL UNIQUE,   -- normalised jira_id
    jira_id            TEXT NOT NULL,
    status             TEXT,                   -- Excel status (NOT jira_status)
    assigned_to        TEXT,                   -- Excel assignee (NOT jira_assignee)
    country            TEXT,
    testcase_scenario  TEXT,
    test_case_id       TEXT,
    testcase_name      TEXT,
    description_change TEXT,                   -- display; feeds the coverage tool
    execution_started  TEXT,
    order_number       TEXT,
    old_order_numbers  TEXT,
    defect_id_ref      TEXT,
    s4_sales_order     TEXT,
    s4_billing_documents TEXT,
    s4_journal_invoice_entry TEXT,
    delivery_note      TEXT,
    reason_for_pass_with_reservation TEXT,
    comment            TEXT,
    excel_row          INTEGER,
    first_seen         TEXT NOT NULL,
    last_seen          TEXT NOT NULL
);

-- Authored working fields — NEVER written by the importer.
CREATE TABLE IF NOT EXISTS ecom_annotations (
    jira_id         TEXT PRIMARY KEY,          -- match key, survives re-imports
    next_step       TEXT,
    comment_history TEXT,
    action_needed   INTEGER DEFAULT 0,
    updated_at      TEXT
);
"""


def init_schema(db_path: Path) -> None:
    conn = database.get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        migrate_order_details_to_jira(conn)
    finally:
        conn.close()


def migrate_order_details_to_jira(conn: sqlite3.Connection) -> dict:
    """One shared order list per Jira ticket [USER 2026-07-16].

    Order rows used to be addressed at the page objects ('ecom', ecom_id /
    'ecom_gatekeeper', row id), which meant a handover step between the
    Gatekeeper Check and the ECOM board. Now both read the SAME rows at
    ('jira', jira_key) — nothing is copied, ever. This re-points existing
    rows (live table AND archived history batches) wherever a jira id is
    known; rows without one keep their old address. Idempotent, safe to
    re-run on every startup; try/except covers a fresh DB where the core
    tables don't exist yet. Returns {table: rows moved}."""
    moved: dict[str, int] = {}
    for table in ("order_details", "order_details_history"):
        try:
            with conn:
                cur_ecom = conn.execute(f"""
                    UPDATE {table}
                    SET entity_type = 'jira',
                        entity_id = (SELECT TRIM(e.jira_id) FROM ecom e
                                     WHERE CAST(e.ecom_id AS TEXT) = {table}.entity_id)
                    WHERE entity_type = 'ecom'
                      AND EXISTS (SELECT 1 FROM ecom e
                                  WHERE CAST(e.ecom_id AS TEXT) = {table}.entity_id
                                    AND TRIM(COALESCE(e.jira_id, '')) <> '')
                """)
                cur_gk = conn.execute(f"""
                    UPDATE {table}
                    SET entity_type = 'jira',
                        entity_id = (SELECT TRIM(g.jira_id) FROM ecom_gatekeeper g
                                     WHERE CAST(g.id AS TEXT) = {table}.entity_id)
                    WHERE entity_type = 'ecom_gatekeeper'
                      AND EXISTS (SELECT 1 FROM ecom_gatekeeper g
                                  WHERE CAST(g.id AS TEXT) = {table}.entity_id
                                    AND TRIM(COALESCE(g.jira_id, '')) <> '')
                """)
            moved[table] = cur_ecom.rowcount + cur_gk.rowcount
        except sqlite3.OperationalError:
            moved[table] = 0  # table not created yet (fresh DB, partial init)
    return moved


_ECOM_MUTABLE = [
    "jira_id", "status", "assigned_to", "country", "testcase_scenario",
    "test_case_id", "testcase_name", "description_change",
    "execution_started", "order_number", "old_order_numbers",
    "defect_id_ref", "s4_sales_order", "s4_billing_documents",
    "s4_journal_invoice_entry", "delivery_note",
    "reason_for_pass_with_reservation", "comment", "excel_row",
]
_ECOM_INSERT_COLS = _ECOM_MUTABLE + ["match_key", "first_seen", "last_seen"]

_ECOM_UPSERT_SQL = """
    INSERT INTO ecom ({cols})
    VALUES ({placeholders})
    ON CONFLICT(match_key) DO UPDATE SET
        {updates}
""".format(
    cols=", ".join(_ECOM_INSERT_COLS),
    placeholders=", ".join(f":{c}" for c in _ECOM_INSERT_COLS),
    updates=",\n        ".join(
        f"{c} = excluded.{c}" for c in _ECOM_MUTABLE + ["last_seen"]
    ),
)


def _ecom_match_key(jira_id: str) -> str:
    return re.sub(r"\s+", "", str(jira_id or "")).lower()


def upsert_ecom_rows(conn: sqlite3.Connection, rows: list[dict], today: str) -> dict:
    """Match-key (jira id) upsert. Never deletes. Returns counts + skipped rows."""
    n_inserted = n_updated = n_skipped = 0
    skipped_rows: list[dict] = []

    with conn:
        existing_keys = {r[0] for r in conn.execute("SELECT match_key FROM ecom")}

        for row in rows:
            if row.get("_skip_reason"):
                n_skipped += 1
                skipped_rows.append({**row, "reason": row["_skip_reason"]})
                continue

            mk = _ecom_match_key(row.get("jira_id", "") or "")
            is_new = mk not in existing_keys

            def _s(field: str):
                v = str(row.get(field, "") or "").strip()
                return v if v else None

            rec = {col: _s(col) for col in _ECOM_MUTABLE if col != "excel_row"}
            rec["excel_row"] = row.get("excel_row")
            rec["match_key"] = mk
            rec["first_seen"] = today
            rec["last_seen"] = today

            conn.execute(_ECOM_UPSERT_SQL, rec)
            if is_new:
                n_inserted += 1
                existing_keys.add(mk)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_missing_jira_id": n_skipped,
        "skipped_rows": skipped_rows,
    }


def get_ecom_rows(conn: sqlite3.Connection,
                  statuses: list[str] | None = None,
                  countries: list[str] | None = None,
                  scenarios: list[str] | None = None,
                  q: str | None = None) -> list[dict]:
    """ECOM rows LEFT JOINed with annotations + note count. All filters
    optional and ANDed; q searches jira id / test case id / name."""
    sql = """
        SELECT e.*, a.next_step, a.comment_history,
               COALESCE(a.action_needed, 0) AS action_needed,
               a.updated_at AS annotation_updated_at,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'ecom'
                  AND n.entity_id = CAST(e.ecom_id AS TEXT)) AS note_count
        FROM ecom e
        LEFT JOIN ecom_annotations a ON a.jira_id = e.jira_id
        WHERE 1=1
    """
    params: list = []
    for col, values in (("e.status", statuses), ("e.country", countries),
                        ("e.testcase_scenario", scenarios)):
        if values:
            sql += f" AND {col} IN ({','.join('?' for _ in values)})"
            params.extend(values)
    if q:
        sql += (" AND (e.jira_id LIKE ? OR e.test_case_id LIKE ?"
                " OR e.testcase_name LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY e.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_ecom_distincts(conn: sqlite3.Connection) -> dict:
    """Filter options for the list page."""
    def _vals(col):
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM ecom WHERE {col} IS NOT NULL ORDER BY {col}")]
    return {"statuses": _vals("status"), "countries": _vals("country"),
            "scenarios": _vals("testcase_scenario")}


def get_ecom_by_id(conn: sqlite3.Connection, ecom_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute("""
        SELECT e.*, a.next_step, a.comment_history,
               COALESCE(a.action_needed, 0) AS action_needed,
               a.updated_at AS annotation_updated_at
        FROM ecom e
        LEFT JOIN ecom_annotations a ON a.jira_id = e.jira_id
        WHERE e.ecom_id = ?
    """, (ecom_id,)))
    return rows[0] if rows else None


def get_ecom_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """{status: count} over the ecom table — input for the status report
    (same bucket definitions as Retail [USER 2026-07-09])."""
    rows = conn.execute(
        "SELECT COALESCE(status, '') AS status, COUNT(*) AS cnt FROM ecom GROUP BY status"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_ecom_defects_impacted(conn: sqlite3.Connection,
                              passed_statuses: list[str]) -> list[dict]:
    """ECOM-channel twin of get_retail_defects_impacted: active defects with
    counts of ECOM test cases that reference them AND have not passed yet
    (same passed family; same split rule — the Excel "Sales or DTC" column
    drives MB vs Sales, the manual dtco2c flag is the blank-cell fallback)."""
    passed_keys = [s.strip().lower() for s in passed_statuses]
    ph = ",".join("?" for _ in passed_keys) or "''"
    sql = f"""
        SELECT d.defect_id, d.solman_name, d.assigned_to, d.date_reported,
               d.solman_status, d.sales_or_dtc,
               CASE
                   WHEN LOWER(TRIM(COALESCE(d.sales_or_dtc, ''))) = 'dtc'   THEN 1
                   WHEN LOWER(TRIM(COALESCE(d.sales_or_dtc, ''))) = 'sales' THEN 0
                   ELSE COALESCE(a.dtco2c, 0)
               END AS dtco2c,
               (LOWER(TRIM(COALESCE(d.sales_or_dtc, ''))) NOT IN ('dtc', 'sales')
                AND a.dtco2c IS NULL) AS dtco2c_unset,
               (SELECT COUNT(*) FROM ecom e
                WHERE e.defect_id_ref IS NOT NULL
                  AND e.defect_id_ref LIKE '%' || d.defect_id || '%'
                  AND LOWER(TRIM(COALESCE(e.status, ''))) NOT IN ({ph})) AS impacted_tc_count,
               (SELECT COUNT(*) FROM ecom e
                WHERE e.defect_id_ref IS NOT NULL
                  AND e.defect_id_ref LIKE '%' || d.defect_id || '%'
                  AND LOWER(TRIM(COALESCE(e.status, ''))) IN ({ph})) AS passed_tc_count
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE LOWER(TRIM(d.channel)) = 'ecom'
          AND LOWER(TRIM(COALESCE(d.solman_status, ''))) NOT IN ('confirmed', 'withdrawn')
        ORDER BY impacted_tc_count DESC, d.defect_id
    """
    return _rows_to_dicts(conn.execute(sql, (*passed_keys, *passed_keys)))


def relink_gatekeeper_orders(conn: sqlite3.Connection, jira_id: str,
                             ecom_id: int) -> int:
    """LEGACY (superseded 2026-07-16 by migrate_order_details_to_jira +
    the shared ('jira', jira_key) order address — no handover step exists
    anymore; the UI button is gone, the route is kept for URL stability).

    Original behaviour (day plan step 8): re-point order_details rows of
    old-gatekeeper rows with the SAME jira id at this ECOM row. Returns # moved."""
    with conn:
        cur = conn.execute("""
            UPDATE order_details
            SET entity_type = 'ecom', entity_id = ?
            WHERE entity_type = 'ecom_gatekeeper'
              AND entity_id IN (SELECT CAST(id AS TEXT) FROM ecom_gatekeeper
                                WHERE TRIM(jira_id) = TRIM(?))
        """, (str(ecom_id), jira_id))
    return cur.rowcount


def set_ecom_next_step(conn: sqlite3.Connection, jira_id: str,
                       next_step: str | None) -> None:
    """Only-this-field upsert (used by the next-step archive component)."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO ecom_annotations (jira_id, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_id) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (jira_id, next_step or None, now))


def set_ecom_comment_history(conn: sqlite3.Connection, jira_id: str,
                             comment_history: str | None) -> None:
    """Only-this-field upsert (used by the shared Comments dialog)."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO ecom_annotations (jira_id, comment_history, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(jira_id) DO UPDATE SET
                comment_history = excluded.comment_history,
                updated_at      = excluded.updated_at
        """, (jira_id, comment_history or None, now))


def upsert_ecom_annotation(conn: sqlite3.Connection, jira_id: str,
                           next_step: str | None = None,
                           comment_history: str | None = None,
                           action_needed: bool = False) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO ecom_annotations (jira_id, next_step, comment_history,
                                          action_needed, updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(jira_id) DO UPDATE SET
                next_step       = excluded.next_step,
                comment_history = excluded.comment_history,
                action_needed   = excluded.action_needed,
                updated_at      = excluded.updated_at
        """, (jira_id, next_step or None, comment_history or None,
              1 if action_needed else 0, now))
