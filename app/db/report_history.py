"""Report history — one row per report + date, in the APP's bucket columns.

Filled from two directions [USER 2026-08-05]:
- automatically on every report EMAIL SEND (the ticked bucket reports,
  dated with the email page's date; source 'email')
- the "Import from Excel tabs" button on the history page — pulls the
  workbook's ReportRetail / ReportECOM lines in (source 'excel'), so the
  hand-maintained tabs can be retired without losing their history.

Same date written twice → the row is REPLACED (last write wins).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts

# App bucket columns — same set/order as the report pages and the Excel log
BUCKET_FIELDS = [
    "back_with_sales",
    "with_dtc",
    "in_progress_with_dtc",
    "passed_with_dtc",
    "incoming_gatekeeper",
    "ready_for_validation",
    "in_progress",
    "in_clarification",
    "blocked",
]

# Report keys that carry bucket numbers (spillover/board are not bucket reports)
BUCKET_REPORTS = ["retail", "ecom", "manual_retail", "manual_ecom"]

REPORT_LABELS = {
    "retail": "Retail",
    "ecom": "ECOM",
    "manual_retail": "Manual Retail",
    "manual_ecom": "Manual ECOM",
}


def init_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cols = ",\n                ".join(f"{f} INTEGER" for f in BUCKET_FIELDS)
        with conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS report_history (
                    report      TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    {cols},
                    source      TEXT,
                    saved_at    TEXT,
                    PRIMARY KEY (report, report_date)
                )
            """)
    finally:
        conn.close()


def upsert_history_row(conn: sqlite3.Connection, report: str, report_date: str,
                       buckets: dict, source: str) -> None:
    """Insert or REPLACE the row for (report, date). buckets may miss keys
    (e.g. tab columns that don't exist for that report) — stored as NULL."""
    if report not in BUCKET_REPORTS:
        raise ValueError(f"unknown report: {report!r}")
    now = datetime.now().isoformat(timespec="seconds")
    cols = ["report", "report_date"] + BUCKET_FIELDS + ["source", "saved_at"]
    rec = {f: buckets.get(f) for f in BUCKET_FIELDS}
    rec.update({"report": report, "report_date": report_date,
                "source": source, "saved_at": now})
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO report_history ({}) VALUES ({})".format(
                ", ".join(cols), ", ".join(f":{c}" for c in cols)),
            rec)


def list_history(conn: sqlite3.Connection, report: str) -> list[dict]:
    """All rows for one report, newest date first (dates stored ISO)."""
    if report not in BUCKET_REPORTS:
        raise ValueError(f"unknown report: {report!r}")
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM report_history WHERE report = ? ORDER BY report_date DESC",
        (report,)))
