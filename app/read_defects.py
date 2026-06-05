"""Step 1: find the latest Defects Excel export and print its rows.

Usage:
    python -m app.read_defects
    python -m app.read_defects --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

from app.config_loader import load_config

# ---------------------------------------------------------------------------
# Header mapping
# Keys   = normalised header text (lowercased, all whitespace collapsed to " ")
# Values = clean field names used downstream
#
# Entries marked IGNORED are recognised but intentionally excluded from output.
# ---------------------------------------------------------------------------
_HEADER_MAP: dict[str, str] = {
    "ecom/retail":                                          "channel",
    "solman status":                                        "solman_status",
    "defect id":                                            "defect_id",
    "solman name":                                          "solman_name",
    "raised by":                                            "raised_by",
    "order number":                                         "order_number",
    "date reported":                                        "date_reported",
    "date closed":                                          "date_closed",
    "priority":                                             "priority",
    "assigned to":                                          "assigned_to",
    "tech team":                                            "tech_team",
    "country":                                              "country",
    "scenario":                                             "scenario",
    "affected testcases":                                   "affected_testcases_raw",
    "retest dependency":                                    "retest_dependency",
    "does it block execution":                              "blocks_execution",
    "exists in production (yes/no)":                        "exists_in_production",
    "defect reason":                                        "defect_reason",
    # --- recognised but intentionally ignored ---
    "comment":                                              "__ignored__",
    "defect status":                                        "__ignored__",
    "more defect description (expected result - actual result)": "__ignored__",
}

_OUTPUT_FIELDS = [v for v in _HEADER_MAP.values() if not v.startswith("__")]


def _normalise_header(raw: str) -> str:
    """Strip surrounding whitespace, collapse internal whitespace/newlines to a single space, lowercase.
    Also removes spaces around '/' so that 'ECOM/\\nRETAIL' and 'ECOM/RETAIL' both normalise to 'ecom/retail'.
    """
    s = re.sub(r"\s+", " ", str(raw)).strip().lower()
    s = re.sub(r"\s*/\s*", "/", s)
    return s


def _find_latest_xlsx(folder: Path, stem: str) -> Path | None:
    """Return the newest .xlsx whose name matches stem[optional (n)].xlsx, ignoring ~$ temps."""
    pattern = re.compile(
        r"^" + re.escape(stem) + r"(\(\d+\))?\.xlsx$",
        re.IGNORECASE,
    )
    candidates = [
        f for f in folder.iterdir()
        if f.is_file()
        and not f.name.startswith("~$")
        and pattern.match(f.name)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def _print_row(excel_row: int, row: dict) -> None:
    parts = [f"row {excel_row:>4}"]
    for field in _OUTPUT_FIELDS:
        val = row.get(field, "")
        if val is None or (isinstance(val, float) and pd.isna(val)):
            val = ""
        parts.append(f"{field}={val!r}")
    print(" | ".join(parts))


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    folder = Path(cfg["downloads_folder"])
    stem = cfg["filename_stem"]
    sheet_name = cfg["defects_sheet_name"]

    # --- 1. Find file ---
    if not folder.exists():
        print(f"ERROR: downloads_folder does not exist: {folder}", file=sys.stderr)
        sys.exit(1)

    xlsx_path = _find_latest_xlsx(folder, stem)
    if xlsx_path is None:
        print(
            f"ERROR: No matching .xlsx file found in {folder}\n"
            f"       Expected name matching: {stem}[optional (n)].xlsx",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Read: {xlsx_path}")

    # --- 2. Verify sheet ---
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    available_sheets = wb.sheetnames
    wb.close()

    if sheet_name not in available_sheets:
        print(
            f"ERROR: Sheet '{sheet_name}' not found in workbook.\n"
            f"       Sheets present: {available_sheets}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- 3. Read with pandas ---
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=0, dtype=str)

    # --- 4. Map headers ---
    raw_headers = list(df.columns)
    col_rename: dict[str, str] = {}      # original column name -> field name
    unmapped: list[str] = []
    ignored: list[str] = []

    for raw in raw_headers:
        norm = _normalise_header(raw)
        field = _HEADER_MAP.get(norm)
        if field is None:
            unmapped.append(raw)
        elif field == "__ignored__":
            ignored.append(raw)
        else:
            col_rename[raw] = field

    df = df.rename(columns=col_rename)

    # Keep only known output columns that actually exist
    present_output_fields = [f for f in _OUTPUT_FIELDS if f in df.columns]
    df_out = df[present_output_fields].copy()

    # Excel row numbers: header = row 1, so first data row = row 2
    excel_row_numbers = range(2, 2 + len(df_out))

    # --- 5. Print rows ---
    print(f"Defects sheet: {len(df_out)} data rows\n")
    for excel_row, (_, row) in zip(excel_row_numbers, df_out.iterrows()):
        _print_row(excel_row, row.to_dict())

    # --- 6. Summary ---
    missing_fields = [f for f in _OUTPUT_FIELDS if f not in df.columns]

    print()
    if unmapped:
        print(f"Unmapped headers found in sheet : {unmapped}")
    else:
        print("Unmapped headers found in sheet : (none)")

    if ignored:
        print(f"Recognised but ignored headers  : {ignored}")

    if missing_fields:
        print(f"Expected headers not found      : {missing_fields}")
    else:
        print("Expected headers not found      : (none)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read Defects sheet and print rows.")
    parser.add_argument("--config", default=None, help="Path to settings.yaml (default: config/settings.yaml)")
    args = parser.parse_args()
    main(config_path=args.config)
