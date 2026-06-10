"""Step 1: parse the Core South Spillover tab and print rows.

Usage:
    python -m app.spillover_importer
    python -m app.spillover_importer --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from app.config_loader import load_config
from app.read_defects import ParseError, _clean, _find_latest_xlsx, _normalise_header

# ---------------------------------------------------------------------------
# Header mapping — source header (normalised) → clean field name
# ---------------------------------------------------------------------------
_HEADER_MAP: dict[str, str] = {
    "type":          "type",
    "ecom/retail":   "area",       # header is "ECOM\n/Retail" in the sheet
    "status":        "status",
    "assigned to":   "assigned_to",
    "id":            "external_id",
    "name":          "name",
    "order numbers": "order_numbers",
    "country":       "country",
    "content":       "content",
    "comment":       "comment",
    # --- recognised but intentionally ignored ---
    "solman status": "__ignored__",
}

_OUTPUT_FIELDS = [v for v in _HEADER_MAP.values() if not v.startswith("__")]

_DEFAULT_SHEET = "Core South Spillover"


def parse_spillover(cfg: dict) -> dict:
    """Find the latest Excel export, parse the Spillover sheet, return structured result.

    Returns:
        {
            "xlsx_path":        Path,
            "sheet_name":       str,
            "rows":             list[dict],   # excel_row + output fields + _skip_reason
            "unmapped_headers": list[str],
            "missing_fields":   list[str],
        }

    Each row's "_skip_reason" is "" for normal rows or "blank name" for rows that have
    content but lack a name value (they are kept for printing but flagged).
    Fully blank rows are dropped silently and never appear in the returned list.

    Raises ParseError on fatal errors (folder missing, file not found, sheet not found).
    """
    folder = Path(cfg["downloads_folder"])
    stem = cfg["filename_stem"]
    sheet_name = cfg.get("spillover_sheet_name", _DEFAULT_SHEET)

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
        else:
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
            continue

        row["_skip_reason"] = "" if row.get("name") else "blank name"
        rows.append(row)

    return {
        "xlsx_path": xlsx_path,
        "sheet_name": sheet_name,
        "rows": rows,
        "unmapped_headers": unmapped,
        "missing_fields": missing_fields,
    }


def _print_row(row: dict) -> None:
    flag = "  [WOULD SKIP — blank name]" if row.get("_skip_reason") == "blank name" else ""
    parts = [f"row {row['excel_row']:>4}"]
    for field in _OUTPUT_FIELDS:
        parts.append(f"{field}={row.get(field, '')!r}")
    print(" | ".join(parts) + flag)


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    try:
        result = parse_spillover(cfg)
    except ParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    rows = result["rows"]
    would_skip = [r for r in rows if r["_skip_reason"]]
    parsed = len(rows)

    print(f"File:  {result['xlsx_path']}")
    print(f"Sheet: {result['sheet_name']}")
    print(f"Rows:  {parsed} parsed, {len(would_skip)} would be skipped (blank name)\n")

    for row in rows:
        _print_row(row)

    print()
    unmapped = result["unmapped_headers"]
    missing = result["missing_fields"]
    if unmapped:
        print(f"WARNING — unexpected columns (not in mapping): {unmapped}")
    if missing:
        print(f"WARNING — expected columns not found in sheet:  {missing}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse Core South Spillover sheet and print rows."
    )
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
