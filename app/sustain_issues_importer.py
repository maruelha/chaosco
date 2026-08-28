"""Sustainphase Issues importer (build plan step 2, 2026-08-28).

Parses the **Defects tab** of `DTC_Sustainphase_Tracking….xlsx` (file
picked in the browser, name-contains guard in the web layer) and upserts
via db_sustain_issues.upsert_issues. Columns are mapped by HEADER NAME
(normalized: lowercased, whitespace collapsed, prefix match) — the tab's
headers contain newlines and trailing text, and matching by position
would break on the first inserted column. "Exists in production" is
ignored entirely [USER 2026-08-28]. Header row = row 1. Date cells
arrive as datetimes → stored as ISO dates.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import openpyxl

from app.db import sustain_issues as db_si

_SHEET = "defects"

# normalized header prefix -> our column name
_HEADER_MAP = [
    ("channel", "channel"),
    ("sales or dtc", "sales_dtc"),
    ("aspen status", "aspen_status"),
    ("defect id", "defect_id"),
    ("short description", "short_description"),
    ("more defect description", "description"),
    ("comment", "comment"),
    ("raised by", "raised_by"),
    ("order number", "order_number"),
    ("date reported", "date_reported"),
    ("date closed", "date_closed"),
    ("priority", "priority"),
    ("assigned to", "assigned_to"),
    ("tech team", "tech_team"),
    ("country", "country"),
    ("scenario", "scenario"),
    ("affected testcases", "affected_testcases"),
    ("retest dependency", "retest_dependency"),
    ("does it block execution", "blocks_execution"),
    ("defect reason", "defect_reason"),
    # "exists in production" deliberately unmapped -> dropped
]

_REQUIRED = {"defect_id", "short_description"}


class ParseError(Exception):
    """Raised when the workbook has no Defects tab or its headers don't
    look like the tracking template."""


def _norm_header(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _clean(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, str):
        val = re.sub(r"\s+", " ", val).strip()
        return val or None
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def parse_sustain_issues_workbook(xlsx_path: Path) -> list[dict]:
    """Defects-tab rows as dicts keyed by our column names (plus
    excel_row), ready for upsert_issues. Raises ParseError on a missing
    tab or unrecognizable headers."""
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    except Exception as exc:
        raise ParseError(f"Could not read workbook: {exc}") from exc
    try:
        sheet = next((ws for ws in wb.worksheets
                      if ws.title.strip().casefold() == _SHEET), None)
        if sheet is None:
            raise ParseError(
                f"No 'Defects' tab found. Sheets present: {wb.sheetnames}")
        col_map: dict[int, str] = {}
        for c in range(1, sheet.max_column + 1):
            header = _norm_header(sheet.cell(1, c).value)
            if not header:
                continue
            for prefix, name in _HEADER_MAP:
                if header.startswith(prefix):
                    col_map.setdefault(c, name)
                    break
        mapped = set(col_map.values())
        missing = _REQUIRED - mapped
        if missing:
            raise ParseError(
                f"Defects tab is missing expected columns: {sorted(missing)}"
                " — structure changed?")
        rows: list[dict] = []
        for r in range(2, sheet.max_row + 1):
            row = {name: _clean(sheet.cell(r, c).value)
                   for c, name in col_map.items()}
            if not any(row.values()):
                continue
            row["excel_row"] = r
            rows.append(row)
        return rows
    finally:
        wb.close()


def run_sustain_issues_import(cfg: dict, xlsx_path: Path) -> dict:
    """Parse + upsert. Result mirrors the other importers' shape:
    ok/error plus rows/inserted/updated/promoted counts. An EMPTY
    Defects tab is fine (the template starts empty) — 0 rows, ok."""
    result: dict = {"ok": False, "error": None, "xlsx_path": str(xlsx_path),
                    "rows": 0, "inserted": 0, "updated": 0, "promoted": 0}
    try:
        rows = parse_sustain_issues_workbook(xlsx_path)
    except ParseError as exc:
        result["error"] = str(exc)
        return result

    from app import database
    db_path = Path(cfg["database_path"])
    db_si.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        counts = db_si.upsert_issues(conn, rows)
    finally:
        conn.close()
    result.update(counts)
    result["rows"] = len(rows)
    result["ok"] = True
    return result
