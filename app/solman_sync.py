"""SolMan defect status sync — targeted UPDATE of solman_status and assigned_to.

Reads the 'Data aggregated by Defect' SolMan export (one row per defect) and
updates active defects in the DB.  Active = not Withdrawn / Confirmed.

File picker reuses _find_latest_xlsx from read_defects (same stem-based logic).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app import database
from app.read_defects import ParseError, _find_latest_xlsx

_ID_RE   = re.compile(r'\((\d{10})\)')
_NAME_RE = re.compile(r'^(.+?)\s*\(\d+\)\s*$')


def _extract_id(cell: str) -> str | None:
    m = _ID_RE.search(str(cell))
    return m.group(1) if m else None


def _extract_name(cell: str) -> str:
    """Strip the employee-ID suffix: 'Bernd Homner (43741)' → 'Bernd Homner'."""
    s = str(cell).strip()
    m = _NAME_RE.match(s)
    return m.group(1).strip() if m else s


def parse_solman_export(cfg: dict) -> dict:
    """Locate the newest SolMan export and parse it.

    Returns:
        {
            "xlsx_path": Path,
            "rows": list[{"defect_id": str, "solman_status": str, "assigned_to": str}],
        }
    Raises ParseError on any fatal problem.
    """
    folder = Path(cfg.get("solman_export_folder", "Download"))
    stem   = cfg.get("solman_export_stem",   "Data aggregated by Defect")
    sheet  = cfg.get("solman_export_sheet",  "SAP Document Export")

    if not folder.exists():
        raise ParseError(f"solman_export_folder does not exist: {folder}")

    xlsx_path = _find_latest_xlsx(folder, stem)
    if xlsx_path is None:
        raise ParseError(
            f"No matching .xlsx found in {folder}\n"
            f"  Expected name matching: {stem}[optional (n)].xlsx"
        )

    with pd.ExcelFile(xlsx_path) as xf:
        if sheet not in xf.sheet_names:
            raise ParseError(
                f"Sheet '{sheet}' not found in {xlsx_path.name}.\n"
                f"  Sheets present: {xf.sheet_names}"
            )
        df = xf.parse(sheet, header=0, dtype=str)

    rows = []
    for _, row in df.iterrows():
        defect_id = _extract_id(str(row.get("Defect", "")))
        if not defect_id:
            continue
        status    = str(row.get("Defect Status",    "")).strip()
        processor = str(row.get("Defect Processor", "")).strip()
        assigned  = _extract_name(processor) if processor and processor != "nan" else ""
        rows.append({"defect_id": defect_id, "solman_status": status, "assigned_to": assigned})

    return {"xlsx_path": xlsx_path, "rows": rows}


def run_solman_sync(cfg: dict) -> dict:
    """Parse the SolMan export and apply status/assignee updates to active defects.

    Returns:
        {
            "ok": bool,
            "error": str | None,
            "xlsx_path": str | None,
            "updated": int,
            "skipped_not_found": int,
            "skipped_inactive": int,
        }
    """
    result: dict = {
        "ok": False,
        "error": None,
        "xlsx_path": None,
        "updated": 0,
        "skipped_not_found": 0,
        "skipped_inactive": 0,
    }

    try:
        parsed = parse_solman_export(cfg)
    except ParseError as exc:
        result["error"] = str(exc)
        return result

    result["xlsx_path"] = str(parsed["xlsx_path"])

    db_path = Path(cfg["database_path"])
    conn = database.init_db(db_path)
    try:
        counts = database.sync_solman_status(conn, parsed["rows"])
        result.update({"ok": True, **counts})
    except Exception as exc:
        result["error"] = f"Database write failed: {exc}"
    finally:
        conn.close()

    return result
