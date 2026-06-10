"""Parse the Retail test-cases tab — Step 1: parse only, no DB writes.

Usage:
    python -m app.retail_importer
    python -m app.retail_importer --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from app.config_loader import load_config
from app.read_defects import ParseError, _clean, _find_latest_xlsx, _normalise_header

# ---------------------------------------------------------------------------
# Header mapping — normalised source header → clean field name
# Verified against: DTC_UAT_testtracking_ROE.xlsx / "Retail" tab
# ---------------------------------------------------------------------------
_HEADER_MAP: dict[str, str] = {
    "test case":                                 "test_case_id",           # match key
    "country":                                   "country",                # match key
    "testcase name":                             "testcase_name",
    "testcase scenario":                         "testcase_scenario",
    "status":                                    "status",
    "assigned to":                               "assigned_to",
    "key user responsible":                      "key_user_responsible",
    "evidence in the sharepoint":                "evidence_in_sharepoint",
    "sales file":                                "sales_file",
    "execution started":                         "execution_started",
    "execution completed":                       "execution_completed",
    "order number/transaction number":            "order_number",
    "old order numbers/transaction numbers":      "old_order_numbers",
    "defect id (if applicable)":                 "defect_id_ref",
    "s4 sales order":                            "s4_sales_order",
    "s4 billing documents":                      "s4_billing_documents",
    "s4 journal invoice entry":                  "s4_journal_invoice_entry",
    "delivery note":                             "delivery_note",
    "comment":                                   "comment",
    "reason for pass with reservation":          "reason_for_pass_with_reservation",
    # recognised but intentionally ignored
    "concatenate":                               "__ignored__",
}

_OUTPUT_FIELDS = [v for v in _HEADER_MAP.values() if not v.startswith("__")]

_DEFAULT_SHEET = "Retail"


def parse_retail(cfg: dict, xlsx_path: Path | None = None) -> dict:
    """Find the latest Excel export, parse the Retail sheet, return structured result.

    If xlsx_path is provided the file-location step is skipped.

    Returns:
        {
            "xlsx_path":        Path,
            "sheet_name":       str,
            "rows":             list[dict],
            "unmapped_headers": list[str],
            "missing_fields":   list[str],
        }

    Each row dict contains excel_row, all output fields, and _skip_reason:
        ""                — normal row (both match-key fields present)
        "incomplete key"  — has content but missing test_case_id or country

    Fully blank rows are dropped silently.
    Raises ParseError on fatal errors.
    """
    sheet_name = cfg.get("retail_sheet_name", _DEFAULT_SHEET)

    if xlsx_path is None:
        folder = Path(cfg["downloads_folder"])
        stem = cfg["filename_stem"]
        if not folder.exists():
            raise ParseError(f"downloads_folder does not exist: {folder}")
        xlsx_path = _find_latest_xlsx(folder, stem)
        if xlsx_path is None:
            raise ParseError(
                f"No matching .xlsx file found in {folder}\n"
                f"  Expected name matching: {stem}[optional (n)].xlsx"
            )

    with pd.ExcelFile(xlsx_path) as xf:
        if sheet_name not in xf.sheet_names:
            raise ParseError(
                f"Sheet '{sheet_name}' not found in workbook.\n"
                f"  Sheets present: {xf.sheet_names}"
            )
        df = xf.parse(sheet_name, header=0, dtype=str)

    raw_headers = list(df.columns)
    col_rename: dict[str, str] = {}
    unmapped: list[str] = []

    for raw in raw_headers:
        norm = _normalise_header(raw)
        field = _HEADER_MAP.get(norm)
        if field is None:
            unmapped.append(raw)
        elif field != "__ignored__":
            col_rename[raw] = field

    df = df.rename(columns=col_rename)
    present_fields = [f for f in _OUTPUT_FIELDS if f in df.columns]
    missing_fields = [f for f in _OUTPUT_FIELDS if f not in df.columns]
    df_out = df[present_fields].copy()

    rows: list[dict] = []
    for excel_row, (_, pandas_row) in enumerate(df_out.iterrows(), start=2):
        row: dict = {"excel_row": excel_row}
        for field in present_fields:
            row[field] = _clean(pandas_row[field])
        for field in missing_fields:
            row[field] = ""

        if all(row[f] == "" for f in _OUTPUT_FIELDS):
            continue  # fully blank — ignore silently

        has_key = bool(row.get("test_case_id")) and bool(row.get("country"))
        row["_skip_reason"] = "" if has_key else "incomplete key"
        rows.append(row)

    return {
        "xlsx_path": xlsx_path,
        "sheet_name": sheet_name,
        "rows": rows,
        "unmapped_headers": unmapped,
        "missing_fields": missing_fields,
    }


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)

    try:
        result = parse_retail(cfg)
    except ParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    rows       = result["rows"]
    normal     = [r for r in rows if not r["_skip_reason"]]
    would_skip = [r for r in rows if r["_skip_reason"]]

    print(f"File : {result['xlsx_path']}")
    print(f"Sheet: {result['sheet_name']}")
    print(f"Rows : {len(rows)} parsed  |  {len(normal)} ok  |  {len(would_skip)} would-skip")

    if result["unmapped_headers"]:
        print(f"WARN  unmapped columns (not in header map): {result['unmapped_headers']}")
    if result["missing_fields"]:
        print(f"WARN  missing expected fields: {result['missing_fields']}")

    print()
    for row in rows:
        flag = f"  [WOULD SKIP — {row['_skip_reason']}]" if row["_skip_reason"] else ""
        parts = [f"row {row['excel_row']:>4}"]
        for field in _OUTPUT_FIELDS:
            val = row.get(field, "")
            if val:
                parts.append(f"{field}={val!r}")
        print(" | ".join(parts) + flag)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse Retail test-cases sheet and print rows (Step 1 — no DB writes)."
    )
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
