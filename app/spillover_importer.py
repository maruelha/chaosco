"""Parse the Core South Spillover tab and upsert rows into SQLite.

Usage:
    python -m app.spillover_importer
    python -m app.spillover_importer --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app import database
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


def parse_spillover(cfg: dict, xlsx_path: Path | None = None) -> dict:
    """Find the latest Excel export, parse the Spillover sheet, return structured result.

    If xlsx_path is provided the file-location step is skipped (caller already found it).

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
    sheet_name = cfg.get("spillover_sheet_name", _DEFAULT_SHEET)

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


def _write_skip_log(skipped_rows: list[dict], skiplog_folder: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = skiplog_folder / f"{ts}_spillover_skipped.csv"
    skiplog_folder.mkdir(parents=True, exist_ok=True)
    sample = skipped_rows[0]
    data_keys = [k for k in sample if k not in ("excel_row", "reason", "_skip_reason")]
    fieldnames = ["excel_row", "reason"] + data_keys
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(skipped_rows)
    return path


def run_spillover_import(cfg: dict) -> dict:
    """Parse → upsert → skip-log.  Returns a result dict, never raises.

    Result keys:
        ok                  : bool
        error               : str | None
        today               : str  (ISO date)
        xlsx_path           : str | None
        sheet_name          : str
        inserted            : int
        updated             : int
        skipped_blank_name  : int
        skiplog_path        : str | None
    """
    today = date.today().isoformat()
    result: dict = {
        "ok": False,
        "error": None,
        "today": today,
        "xlsx_path": None,
        "sheet_name": cfg.get("spillover_sheet_name", _DEFAULT_SHEET),
        "inserted": 0,
        "updated": 0,
        "skipped_blank_name": 0,
        "skiplog_path": None,
    }

    try:
        parse_result = parse_spillover(cfg)
    except ParseError as exc:
        result["error"] = str(exc)
        return result

    result["xlsx_path"] = str(parse_result["xlsx_path"])
    result["sheet_name"] = parse_result["sheet_name"]
    rows = parse_result["rows"]

    db_path = Path(cfg["database_path"])
    conn = database.init_db(db_path)
    try:
        upsert = database.upsert_spillover_rows(conn, rows, today)
    except Exception as exc:
        conn.close()
        result["error"] = f"Database write failed: {exc}"
        return result
    conn.close()

    skiplog_path = None
    if upsert["skipped_rows"]:
        skiplog_path = _write_skip_log(upsert["skipped_rows"], Path(cfg["skiplog_folder"]))

    result.update({
        "ok": True,
        "inserted": upsert["inserted"],
        "updated": upsert["updated"],
        "skipped_blank_name": upsert["skipped_blank_name"],
        "skiplog_path": str(skiplog_path) if skiplog_path else None,
    })
    return result


def _print_row(row: dict) -> None:
    flag = "  [WOULD SKIP — blank name]" if row.get("_skip_reason") == "blank name" else ""
    parts = [f"row {row['excel_row']:>4}"]
    for field in _OUTPUT_FIELDS:
        parts.append(f"{field}={row.get(field, '')!r}")
    print(" | ".join(parts) + flag)


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    result = run_spillover_import(cfg)

    print(f"File:  {result['xlsx_path'] or '(none)'}")
    print(f"Sheet: {result['sheet_name']}")

    if not result["ok"]:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Inserted : {result['inserted']}")
    print(f"Updated  : {result['updated']}")
    print(f"Skipped  : {result['skipped_blank_name']} (blank name)")
    if result["skiplog_path"]:
        print(f"Skip log : {result['skiplog_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse Core South Spillover sheet and print rows."
    )
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
