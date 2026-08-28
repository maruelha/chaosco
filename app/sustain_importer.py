"""Core South Sustainphase Monitoring importer (build plan step 2,
2026-08-27).

Parses the daily GBS Operations checklist workbook (file picked in the
browser, suffix-matched `DTC_GBS Operations_checklist.xlsx` — see
docs/claude/sustain.md) and writes sustain_tasks/sustain_task_details via
db_sustain.replace_day_stream, one call per `Retail_<date>`/`eCom_<date>`
tab. Loaded with data_only=True: we import the cached cell values but
never the workbook's aggregations — those are recomputed in
app/db/sustain.py. Parent task = row with a Task ID; detail row = outline
level ≥ 1 under the last parent.
"""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl

from app.db import sustain as db_sustain

_TAB_RE = re.compile(r"^(Retail|eCom)_(\d{4}-\d{2}-\d{2})$", re.IGNORECASE)
_STREAM_CANON = {"retail": db_sustain.STREAM_RETAIL,
                 "ecom": db_sustain.STREAM_ECOM}

_HEADER_ROW = 6
_FIRST_DATA_ROW = 7


class ParseError(Exception):
    """Raised when the workbook cannot be read or a day tab does not have
    the expected checklist structure."""


def _clean(val):
    """None stays None; strings stripped (blank -> None); numbers to their
    shortest text form (Task IDs arrive as text OR numbers)."""
    if val is None:
        return None
    if isinstance(val, str):
        val = val.strip()
        return val or None
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def _parse_sheet(ws) -> list[dict]:
    """One day tab -> parent-task dicts with their 'details' attached."""
    if _clean(ws.cell(_HEADER_ROW, 1).value) != "Task ID":
        raise ParseError(
            f"Tab '{ws.title}' looks like a checklist day tab by name but"
            f" row {_HEADER_ROW} column A is not 'Task ID' — structure"
            " changed?")
    tasks: list[dict] = []
    current: dict | None = None
    for r in range(_FIRST_DATA_ROW, ws.max_row + 1):
        values = [_clean(ws.cell(r, c).value) for c in range(1, 13)]
        if not any(values):
            continue
        (task_id, taxonomy, process, cadence, due_today, country, provider,
         result_fr, result_it, result_pt, result_es, overall) = values
        dim = ws.row_dimensions.get(r)
        outline_level = dim.outline_level if dim is not None else 0
        row = {
            "excel_row": r, "cadence": cadence, "due_today": due_today,
            "country": country, "provider": provider,
            "result_fr": result_fr, "result_it": result_it,
            "result_pt": result_pt, "result_es": result_es,
            "overall": overall,
        }
        if task_id is not None:
            current = {**row, "task_id": task_id, "taxonomy": taxonomy,
                       "process": process, "details": []}
            tasks.append(current)
        elif outline_level >= 1 and current is not None:
            current["details"].append(row)
        # level-0 rows without a Task ID (stray notes) are dropped
    return tasks


def parse_sustain_workbook(xlsx_path: Path) -> list[dict]:
    """Return tab dicts {'day', 'stream', 'tasks'} for every
    Retail_<date>/eCom_<date> tab, in workbook order. Non-matching tabs
    are ignored; a matching tab with the wrong structure raises
    ParseError."""
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    except Exception as exc:
        raise ParseError(f"Could not read workbook: {exc}") from exc
    try:
        tabs: list[dict] = []
        for ws in wb.worksheets:
            m = _TAB_RE.match(ws.title.strip())
            if not m:
                continue
            tabs.append({
                "day": m.group(2),
                "stream": _STREAM_CANON[m.group(1).lower()],
                "tasks": _parse_sheet(ws),
            })
        return tabs
    finally:
        wb.close()


def run_sustain_import(cfg: dict, xlsx_path: Path) -> dict:
    """Parse + replace each contained (day, stream) tab. Result dict
    mirrors run_smoke_import's shape: ok/error plus counts."""
    result: dict = {"ok": False, "error": None, "xlsx_path": str(xlsx_path),
                    "tabs": 0, "tasks": 0, "details": 0}
    try:
        tabs = parse_sustain_workbook(xlsx_path)
    except ParseError as exc:
        result["error"] = str(exc)
        return result
    if not tabs:
        result["error"] = ("No Retail_<date>/eCom_<date> day tabs found —"
                           " is this the right workbook?")
        return result

    from app import database
    db_path = Path(cfg["database_path"])
    db_sustain.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        for tab in tabs:
            counts = db_sustain.replace_day_stream(
                conn, tab["day"], tab["stream"], tab["tasks"])
            result["tabs"] += 1
            result["tasks"] += counts["tasks"]
            result["details"] += counts["details"]
    finally:
        conn.close()
    result["ok"] = True
    return result
