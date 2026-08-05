"""Manual Test Cases — the two imported verticals manual_retail / manual_ecom.

One module, two tables (each Excel tab keeps its own table per architecture
rule 1; the code path is shared, the table name is the parameter). Match key
for BOTH = lower(test_case_id) || '||' || lower(country), like Retail — the
ECOM tab's jira_id is a plain imported field, blank in the real data.

No annotations tables yet — the list pages are read-only + notes (generic
notes table, entity types 'manual_retail' / 'manual_ecom').
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app.db.core import _rows_to_dicts

# Imported fields per vertical — kept in sync with app/manual_importer.py
# (guarded by a drift test in tests/test_manual_importer.py).
FIELDS: dict[str, list[str]] = {
    "manual_retail": [
        "test_case_id", "country", "testcase_name", "testcase_scenario",
        "status", "assigned_to", "key_user_responsible",
        "execution_started", "execution_completed", "store_no", "sales_status",
        "order_number", "old_order_numbers", "defect_id_ref", "old_defect_ids",
        "s4_sales_order", "s4_billing_documents", "s4_journal_invoice_entry",
        "delivery_note", "comment", "reason_for_pass_with_reservation",
    ],
    "manual_ecom": [
        "test_case_id", "country", "testcase_name", "testcase_scenario",
        "status", "assigned_to", "jira_id", "description_change",
        "execution_started",
        "order_number", "old_order_numbers", "defect_id_ref", "old_defect_ids",
        "s4_sales_order", "s4_billing_documents", "s4_journal_invoice_entry",
        "delivery_note", "comment", "reason_for_pass_with_reservation",
    ],
}

TABLES = tuple(FIELDS)


def _check_vertical(vertical: str) -> None:
    if vertical not in FIELDS:
        raise ValueError(f"unknown manual vertical: {vertical!r}")


def _id_col(vertical: str) -> str:
    return f"{vertical}_id"


def init_schema(db_path: Path) -> None:
    """Create both tables if missing. Safe to re-run."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            for vertical, fields in FIELDS.items():
                cols = ",\n                    ".join(f"{f} TEXT" for f in fields)
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {vertical} (
                        {_id_col(vertical)} INTEGER PRIMARY KEY AUTOINCREMENT,
                        {cols},
                        excel_row INTEGER,
                        match_key TEXT UNIQUE,
                        first_seen TEXT,
                        last_seen TEXT
                    )
                """)
    finally:
        conn.close()


def _match_key(test_case_id: str, country: str) -> str:
    return "||".join(
        re.sub(r"\s+", " ", str(p or "")).strip().lower()
        for p in (test_case_id, country)
    )


def upsert_manual_rows(conn: sqlite3.Connection, vertical: str,
                       rows: list[dict], today: str) -> dict:
    """Match-key upsert. Never deletes. Returns counts + skipped rows.

    ONE line per test case + country [USER 2026-08-05]: the real ECOM tab
    repeats CDI0000MU34 up to 7x per country as identical rows — Marina
    judged that a data DEFECT in the workbook (to be clarified with the
    team). The first occurrence wins; further occurrences within the same
    file go to the skiplog (reason "duplicate test case+country in file")
    and are counted as skipped_duplicate on the import screen.
    """
    _check_vertical(vertical)
    fields = FIELDS[vertical]
    insert_cols = fields + ["excel_row", "match_key", "first_seen", "last_seen"]
    sql = """
        INSERT INTO {table} ({cols})
        VALUES ({placeholders})
        ON CONFLICT(match_key) DO UPDATE SET
            {updates}
    """.format(
        table=vertical,
        cols=", ".join(insert_cols),
        placeholders=", ".join(f":{c}" for c in insert_cols),
        updates=",\n            ".join(
            f"{c} = excluded.{c}" for c in fields + ["excel_row", "last_seen"]
        ),
    )

    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    n_duplicate = 0
    skipped_rows: list[dict] = []

    with conn:
        existing_keys = {r[0] for r in conn.execute(
            f"SELECT match_key FROM {vertical}")}
        seen_this_file: set[str] = set()

        for row in rows:
            if row.get("_skip_reason"):
                n_skipped += 1
                skipped_rows.append({**row, "reason": row["_skip_reason"]})
                continue

            mk = _match_key(row.get("test_case_id", "") or "",
                            row.get("country", "") or "")
            if mk in seen_this_file:
                n_duplicate += 1
                skipped_rows.append(
                    {**row, "reason": "duplicate test case+country in file"})
                continue
            seen_this_file.add(mk)
            is_new = mk not in existing_keys

            def _s(field: str):
                v = str(row.get(field, "") or "").strip()
                return v if v else None

            rec = {col: _s(col) for col in fields}
            rec["excel_row"] = row.get("excel_row")
            rec["match_key"] = mk
            rec["first_seen"] = today
            rec["last_seen"] = today

            conn.execute(sql, rec)
            if is_new:
                n_inserted += 1
                existing_keys.add(mk)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_blank_key": n_skipped,
        "skipped_duplicate": n_duplicate,
        "skipped_rows": skipped_rows,
    }


def get_manual_rows(
    conn: sqlite3.Connection,
    vertical: str,
    statuses: list[str] | None = None,
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    search: str | None = None,
) -> list[dict]:
    """List rows with optional AND-combined filters + free search
    (test case / name / defect ref / order number)."""
    _check_vertical(vertical)
    sql = f"""
        SELECT m.*,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = '{vertical}'
                AND n.entity_id = CAST(m.{_id_col(vertical)} AS TEXT)) AS note_count
        FROM {vertical} m
        WHERE 1=1
    """
    params: list = []

    def _in(col: str, values: list[str]) -> None:
        nonlocal sql
        ph = ",".join("?" * len(values))
        sql += f" AND m.{col} IN ({ph})"
        params.extend(values)

    if statuses:  _in("status", statuses)
    if countries: _in("country", countries)
    if scenarios: _in("testcase_scenario", scenarios)
    if search:
        sql += (" AND (m.test_case_id LIKE ? OR m.testcase_name LIKE ?"
                " OR m.defect_id_ref LIKE ? OR m.order_number LIKE ?)")
        params.extend([f"%{search}%"] * 4)

    sql += " ORDER BY m.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_manual_filter_options(conn: sqlite3.Connection, vertical: str) -> dict:
    _check_vertical(vertical)

    def _vals(col: str) -> list:
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM {vertical} WHERE {col} IS NOT NULL ORDER BY {col}"
        ).fetchall()]

    return {
        "statuses":  _vals("status"),
        "countries": _vals("country"),
        "scenarios": _vals("testcase_scenario"),
    }


def get_manual_status_counts(conn: sqlite3.Connection, vertical: str) -> dict[str, int]:
    """{status_value: count} over one manual table — reporter input."""
    _check_vertical(vertical)
    rows = conn.execute(
        f"SELECT COALESCE(status, '') AS status, COUNT(*) AS cnt "
        f"FROM {vertical} GROUP BY status"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# Defects-tab channel each manual vertical's report pulls from
CHANNEL: dict[str, str] = {"manual_retail": "retail", "manual_ecom": "ecom"}


def get_manual_defects_impacted(conn: sqlite3.Connection, vertical: str,
                                passed_statuses: list[str]) -> list[dict]:
    """Defects for a manual report [USER 2026-08-05]: a defect appears only
    if it is REFERENCED in the tab's defect_id_ref column AND its channel
    matches the vertical (retail/ecom, case-insensitive) — unlike the Retail
    report, which lists all active channel defects. Impacted counting =
    same rules as Retail (not-passed TCs count, passed shown muted,
    MB/Sales split via "Sales or DTC" with the DTC-O2C flag as fallback)."""
    _check_vertical(vertical)
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
               (SELECT COUNT(*) FROM {vertical} m
                WHERE m.defect_id_ref IS NOT NULL
                  AND m.defect_id_ref LIKE '%' || d.defect_id || '%'
                  AND LOWER(TRIM(COALESCE(m.status, ''))) NOT IN ({ph})) AS impacted_tc_count,
               (SELECT COUNT(*) FROM {vertical} m
                WHERE m.defect_id_ref IS NOT NULL
                  AND m.defect_id_ref LIKE '%' || d.defect_id || '%'
                  AND LOWER(TRIM(COALESCE(m.status, ''))) IN ({ph})) AS passed_tc_count
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE LOWER(TRIM(COALESCE(d.channel, ''))) = ?
          AND LOWER(TRIM(COALESCE(d.solman_status, ''))) NOT IN ('confirmed', 'withdrawn')
          AND EXISTS (SELECT 1 FROM {vertical} m
                      WHERE m.defect_id_ref IS NOT NULL
                        AND m.defect_id_ref LIKE '%' || d.defect_id || '%')
        ORDER BY impacted_tc_count DESC, d.defect_id
    """
    return _rows_to_dicts(conn.execute(
        sql, (*passed_keys, *passed_keys, CHANNEL[vertical])))


def get_manual_offchannel_defect_refs(conn: sqlite3.Connection,
                                      vertical: str) -> list[dict]:
    """Data check for the report diagnostics: defects referenced in the
    tab whose Defects-tab channel does NOT match the vertical (or is
    blank) — they are excluded from the defects section above, so they
    must not vanish silently."""
    _check_vertical(vertical)
    sql = f"""
        SELECT d.defect_id, COALESCE(d.channel, '') AS channel,
               d.solman_status,
               (SELECT COUNT(*) FROM {vertical} m
                WHERE m.defect_id_ref IS NOT NULL
                  AND m.defect_id_ref LIKE '%' || d.defect_id || '%') AS ref_count
        FROM defects d
        WHERE LOWER(TRIM(COALESCE(d.channel, ''))) != ?
          AND EXISTS (SELECT 1 FROM {vertical} m
                      WHERE m.defect_id_ref IS NOT NULL
                        AND m.defect_id_ref LIKE '%' || d.defect_id || '%')
        ORDER BY d.defect_id
    """
    return _rows_to_dicts(conn.execute(sql, (CHANNEL[vertical],)))
