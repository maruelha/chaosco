"""Sales workbook "Solman ID" column extraction (2026-09-01).

Parses the "All Countries Combined" tab of the sales Excel Marina uploads
on the Delegated Testing board and returns its "Solman ID" column values.
Parse only — no DB writes; app/web_delegated.py does the matching against
delegated tickets and the sales_xls annotation upsert.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.read_defects import ParseError, _clean, _normalise_header

SHEET_NAME = "All Countries Combined"
# The header is "Solman ID" in Marina's workbook [USER 2026-09-02: "a column
# called Solman ID not SolmanID"] — the first build matched "SolmanID".
# Matching ignores case AND internal spaces, so both spellings work.
_COLUMN = "solmanid"


def _header_key(raw) -> str:
    return _normalise_header(raw).replace(" ", "")


def parse_sales_xls(xlsx_path: Path) -> list[str]:
    """Non-empty, de-duplicated (case-insensitive) Solman ID values from the
    sheet, in first-seen order. Raises ParseError if the sheet or column is
    missing."""
    with pd.ExcelFile(xlsx_path) as xf:
        if SHEET_NAME not in xf.sheet_names:
            raise ParseError(
                f"Sheet '{SHEET_NAME}' not found in workbook.\n"
                f"  Sheets present: {xf.sheet_names}"
            )
        df = xf.parse(SHEET_NAME, header=0, dtype=str)

    col = next((raw for raw in df.columns
                if _header_key(raw) == _COLUMN), None)
    if col is None:
        raise ParseError(
            f"Column 'Solman ID' not found on sheet '{SHEET_NAME}'.\n"
            f"  Columns present: {list(df.columns)}"
        )

    values: list[str] = []
    seen: set[str] = set()
    for raw in df[col]:
        val = _clean(raw).strip()
        if val and val.lower() not in seen:
            seen.add(val.lower())
            values.append(val)
    return values
