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


# "Delegated testing" column (2026-09-03 [USER]) — same tab, same header
# row; yes-ish values mark rows that SHOULD be on the Delegated Testing
# board. Optional: older files without the column just yield delegated=False.
_DELEGATED_COLUMN = "delegatedtesting"
_YES = {"yes", "y", "x", "true", "1", "ja"}

# The header row is NOT the first row [USER 2026-09-03: "the first row is
# empty - the second row contains Solman ID" — she does not own the file].
# The parser therefore LOCATES the header row: the first of the top rows
# that carries the Solman ID header (same idea as the sustain importer).
_HEADER_SCAN_ROWS = 15


def _find_header_row(df) -> int | None:
    for idx in range(min(_HEADER_SCAN_ROWS, len(df))):
        if any(_header_key(v) == _COLUMN for v in df.iloc[idx].tolist()):
            return idx
    return None


def parse_sales_xls_rows(xlsx_path: Path) -> list[dict]:
    """[{solman_id, delegated}, …] — non-empty, de-duplicated
    (case-insensitive) Solman ID values in first-seen order; `delegated` =
    True when the row's "Delegated testing" cell is yes-ish (False when the
    column is absent). Raises ParseError if the sheet or the Solman ID
    column is missing."""
    with pd.ExcelFile(xlsx_path) as xf:
        if SHEET_NAME not in xf.sheet_names:
            raise ParseError(
                f"Sheet '{SHEET_NAME}' not found in workbook.\n"
                f"  Sheets present: {xf.sheet_names}"
            )
        raw = xf.parse(SHEET_NAME, header=None, dtype=str)

    hdr = _find_header_row(raw)
    if hdr is None:
        raise ParseError(
            f"Column 'Solman ID' not found in the first {_HEADER_SCAN_ROWS} rows"
            f" of sheet '{SHEET_NAME}'.\n"
            f"  First row: {[_clean(v) for v in raw.iloc[0].tolist()] if len(raw) else []}"
        )
    headers = [_header_key(v) for v in raw.iloc[hdr].tolist()]
    id_col = headers.index(_COLUMN)
    del_col = headers.index(_DELEGATED_COLUMN) if _DELEGATED_COLUMN in headers else None

    rows: list[dict] = []
    seen: set[str] = set()
    for _, r in raw.iloc[hdr + 1:].iterrows():
        val = _clean(r.iloc[id_col]).strip()
        if not val or val.lower() in seen:
            continue
        seen.add(val.lower())
        delegated = (del_col is not None
                     and _clean(r.iloc[del_col]).strip().lower() in _YES)
        rows.append({"solman_id": val, "delegated": delegated})
    return rows


def parse_sales_xls(xlsx_path: Path) -> list[str]:
    """Just the Solman ID values (see parse_sales_xls_rows)."""
    return [r["solman_id"] for r in parse_sales_xls_rows(xlsx_path)]
