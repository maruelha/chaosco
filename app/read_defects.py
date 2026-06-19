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

import pandas as pd

from app.config_loader import load_config

# ---------------------------------------------------------------------------
# Header mapping
# Keys   = normalised header text (lowercased, all whitespace collapsed to " ")
# Values = clean field names used downstream
#
# Entries marked __ignored__ are recognised but intentionally excluded from output.
# ---------------------------------------------------------------------------
_HEADER_MAP: dict[str, str] = {
    "ecom/retail":                                               "channel",
    "channel":                                                   "channel",
    "solman status":                                             "solman_status",
    "defect id":                                                 "defect_id",
    "solman name":                                               "solman_name",
    "raised by":                                                 "raised_by",
    "order number":                                              "order_number",
    "date reported":                                             "date_reported",
    "date closed":                                               "date_closed",
    "priority":                                                  "priority",
    "assigned to":                                               "assigned_to",
    "tech team":                                                 "tech_team",
    "country":                                                   "country",
    "scenario":                                                  "scenario",
    "affected testcases":                                        "affected_testcases_raw",
    "retest dependency":                                         "retest_dependency",
    "does it block execution":                                   "blocks_execution",
    "exists in production (yes/no)":                             "exists_in_production",
    "defect reason":                                             "defect_reason",
    # --- recognised but intentionally ignored ---
    "comment":                                                   "__ignored__",
    "defect status":                                             "__ignored__",
    "more defect description (expected result - actual result)": "__ignored__",
}

_OUTPUT_FIELDS = list(dict.fromkeys(v for v in _HEADER_MAP.values() if not v.startswith("__")))


def _normalise_header(raw: str) -> str:
    """Strip surrounding whitespace, collapse internal whitespace/newlines, lowercase.
    Removes spaces around '/' so 'ECOM/\\nRETAIL' and 'ECOM/RETAIL' both become 'ecom/retail'.
    """
    s = re.sub(r"\s+", " ", str(raw)).strip().lower()
    s = re.sub(r"\s*/\s*", "/", s)
    return s


def _find_latest_xlsx(folder: Path, stem: str) -> Path | None:
    """Return the newest .xlsx whose name matches stem[optional (n)].xlsx, ignoring ~$ temps."""
    pattern = re.compile(
        r"^" + re.escape(stem) + r" ?(\(\d+\))?\.xlsx$",
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


def _clean(val) -> str:
    """Convert a pandas cell value to a plain string; NaN/None become empty string."""
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    return str(val)


class ParseError(Exception):
    """Raised by parse_defects() when the source file cannot be read."""


def parse_defects(cfg: dict, xlsx_path: Path | None = None) -> dict:
    """Find the latest Excel export, parse the Defects sheet, return structured result.

    If xlsx_path is provided the file-location step is skipped (caller already found it).

    Returns:
        {
            "xlsx_path": Path,
            "rows": list[dict],   # each dict: {"excel_row": int, <field>: str, ...}
            "unmapped_headers": list[str],
            "ignored_headers":  list[str],
            "missing_fields":   list[str],
        }

    Raises ParseError on fatal errors (folder missing, file not found, sheet not found).
    """
    sheet_name = cfg["defects_sheet_name"]

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
        rows.append(row)

    return {
        "xlsx_path": xlsx_path,
        "rows": rows,
        "unmapped_headers": unmapped,
        "ignored_headers": ignored,
        "missing_fields": missing_fields,
    }


def _print_row(row: dict) -> None:
    parts = [f"row {row['excel_row']:>4}"]
    for field in _OUTPUT_FIELDS:
        parts.append(f"{field}={row.get(field, '')!r}")
    print(" | ".join(parts))


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    try:
        result = parse_defects(cfg)
    except ParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Read: {result['xlsx_path']}")
    print(f"Defects sheet: {len(result['rows'])} data rows\n")

    for row in result["rows"]:
        _print_row(row)

    print()
    unmapped = result["unmapped_headers"]
    ignored = result["ignored_headers"]
    missing = result["missing_fields"]

    print(f"Unmapped headers found in sheet : {unmapped or '(none)'}")
    if ignored:
        print(f"Recognised but ignored headers  : {ignored}")
    print(f"Expected headers not found      : {missing or '(none)'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read Defects sheet and print rows.")
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
