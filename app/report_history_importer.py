"""Report history sources — workbook-tab import + email-send snapshot.

The workbook's ReportRetail / ReportECOM tabs are the hand-maintained
history Marina wants to RETIRE [USER 2026-08-05]: their existing lines are
pulled in via the history page's import button (source 'excel'); going
forward every report email automatically saves the sent numbers (source
'email', app/web_email.py). Values land in the APP's bucket columns.

Tab layout (both tabs): a label row containing "date" + the bucket labels,
below it a description/owner row, then one row per date (21.05.2026 style).
Labels are matched via the shared header normaliser; labels that are not
app buckets (Total from Sales, Sense check, Waiting for SF creation, the
combined "In Progress / In Clarification") are deliberately ignored.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app import database
from app.db import ecom as db_ecom
from app.db import manual_tests as db_manual
from app.db import report_history as db_hist
from app.read_defects import ParseError, _find_latest_xlsx, _normalise_header
from app.reporter import compute_retail_report, load_status_mappings

# normalised tab label → app bucket field
_LABEL_MAP = {
    "back with sales":        "back_with_sales",
    "with dtc":               "with_dtc",
    "in progress with dtc":   "in_progress_with_dtc",
    "passed with dtc":        "passed_with_dtc",
    "incoming (gatekeeper)":  "incoming_gatekeeper",
    "ready for validation":   "ready_for_validation",
    "in progress":            "in_progress",
    "in clarification":       "in_clarification",
    "blocked":                "blocked",
}

# tab columns that are known but NOT app buckets — skipped silently
_IGNORED_LABELS = {
    "date",  # handled separately
    "total number of test cases",
    "sense check",
    "waiting for sf creation",
    "in progress/in clarification",   # ECOM's combined column
}

# default sheet names; overridable via cfg key report_history_tabs
_DEFAULT_TABS = {"retail": "ReportRetail", "ecom": "ReportECOM"}


def _parse_tab_date(val) -> str | None:
    """Excel cell → ISO date string, or None if not a date."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip().split(" ")[0]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _to_int(val) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_report_tab(xlsx_path: Path, sheet_name: str) -> dict:
    """Parse one Report tab. Returns
    {rows: [{"date": iso, "buckets": {...}}], unmapped: [labels],
     skipped_no_date: n}. Raises ParseError if the sheet or its label row
    is missing."""
    with pd.ExcelFile(xlsx_path) as xf:
        if sheet_name not in xf.sheet_names:
            raise ParseError(
                f"Sheet '{sheet_name}' not found in workbook.\n"
                f"  Sheets present: {xf.sheet_names}")
        df = xf.parse(sheet_name, header=None)

    # find the label row: the one containing a cell that normalises to "date"
    label_row_idx = None
    for idx, row in df.iterrows():
        if any(_normalise_header(v) == "date" for v in row if isinstance(v, str)):
            label_row_idx = idx
            break
    if label_row_idx is None:
        raise ParseError(f"Sheet '{sheet_name}': no label row containing 'date' found.")

    col_map: dict[int, str] = {}   # column index → bucket field
    date_col = None
    unmapped: list[str] = []
    for col, val in df.iloc[label_row_idx].items():
        if not isinstance(val, str) or not val.strip():
            continue
        norm = _normalise_header(val)
        if norm == "date":
            date_col = col
        elif norm in _LABEL_MAP:
            col_map[col] = _LABEL_MAP[norm]
        elif norm not in _IGNORED_LABELS:
            unmapped.append(val.strip())

    rows: list[dict] = []
    skipped_no_date = 0
    for _, row in df.iloc[label_row_idx + 1:].iterrows():
        iso = _parse_tab_date(row[date_col])
        if iso is None:
            # description/owner rows and blanks land here — only count rows
            # that carry SOME value (a real line with a broken date)
            if any(_to_int(row[c]) is not None for c in col_map):
                skipped_no_date += 1
            continue
        buckets = {field: _to_int(row[col]) for col, field in col_map.items()}
        rows.append({"date": iso, "buckets": buckets})

    return {"rows": rows, "unmapped": unmapped,
            "skipped_no_date": skipped_no_date}


def import_report_tabs(cfg: dict, conn: sqlite3.Connection) -> dict:
    """The history page's import button: pull the lines of every configured
    Report tab from the newest workbook, upsert per (report, date) —
    source 'excel', re-runnable (corrected cells update). Never deletes."""
    tabs = cfg.get("report_history_tabs", _DEFAULT_TABS)
    result: dict = {"xlsx_path": None, "reports": {}}

    folder = Path(cfg["downloads_folder"])
    xlsx_path = _find_latest_xlsx(folder, cfg["filename_stem"]) if folder.exists() else None
    if xlsx_path is None:
        result["error"] = f"No matching workbook found in {folder}"
        return result
    result["xlsx_path"] = str(xlsx_path)

    for report, sheet in tabs.items():
        r = {"sheet": sheet, "imported": 0, "skipped_no_date": 0,
             "unmapped": [], "error": None}
        try:
            parsed = parse_report_tab(xlsx_path, sheet)
        except ParseError as exc:
            r["error"] = str(exc)
        else:
            for row in parsed["rows"]:
                db_hist.upsert_history_row(
                    conn, report, row["date"], row["buckets"], source="excel")
            r["imported"] = len(parsed["rows"])
            r["skipped_no_date"] = parsed["skipped_no_date"]
            r["unmapped"] = parsed["unmapped"]
        result["reports"][report] = r
    return result


# ---------------------------------------------------------------------------
# Email-send snapshot
# ---------------------------------------------------------------------------

_STATUS_COUNTERS = {
    "retail":        database.get_retail_status_counts,
    "ecom":          db_ecom.get_ecom_status_counts,
    "manual_retail": lambda conn: db_manual.get_manual_status_counts(conn, "manual_retail"),
    "manual_ecom":   lambda conn: db_manual.get_manual_status_counts(conn, "manual_ecom"),
}


def snapshot_reports(conn: sqlite3.Connection, reports: list[str],
                     day: str) -> list[str]:
    """Save the CURRENT bucket numbers of the given report keys under `day`
    (the email page's date) — called by the email send. Non-bucket choices
    (spillover, board) are ignored. Returns the report keys saved."""
    mappings = load_status_mappings()
    saved: list[str] = []
    for report in db_hist.BUCKET_REPORTS:
        if report not in reports:
            continue
        counts = _STATUS_COUNTERS[report](conn)
        buckets = compute_retail_report(counts, mappings)["buckets"]
        db_hist.upsert_history_row(conn, report, day, buckets, source="email")
        saved.append(report)
    return saved
