"""CORE SOUTH Smoke Testing importer (build plan step 2, 2026-08-27).

Parses the EU CS Smoke Test execution workbook (file picked in the
browser, no folder config — see docs/claude/smoke.md) and writes
smoke_scenarios/smoke_steps via db_smoke.replace_all. Keeps only
RowType=Scenario rows where WS in {eCOM, Retail} AND MB Invoice
Validation is WAHR (planning chat 2026-08-27); their Step rows
(RowType=Step, ParentRow == scenario RowID) come along with them.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.db import smoke as db_smoke

_SHEET_NAME = "EU CS Smoke Test execution"

# normalised WS text -> canonical value stored/queried elsewhere
_WS_MAP = {"ecom": "eCOM", "retail": "Retail"}

_REQUIRED_COLUMNS = [
    "RowID", "RowType", "WS", "Package", "Scenario", "Comment", "Status",
    "Company Code", "Sales Org.", "Plant (DC)", "Store Code",
    "MB Invoice Validation", "ParentRow", "Step", "Expected result",
    "Owner eMail", "Owner", "WS Executing", "ASPEN Ticket",
    "Execution Status", "Progress",
]


class ParseError(Exception):
    """Raised when the workbook cannot be read or is missing expected columns."""


def _clean(val):
    """NaN/None -> None; strings stripped (blank -> None); other values as-is."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str):
        val = val.strip()
        return val or None
    return val


def _to_int(val) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return int(val)


def _is_wahr(val) -> bool:
    """MB Invoice Validation arrives as 1.0/NaN in the current export, but
    tolerate bool/text variants too (WAHR = German TRUE)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val == 1
    return str(val).strip().lower() in ("wahr", "true", "1")


def parse_smoke_workbook(xlsx_path: Path) -> list[dict]:
    """Return scenario dicts (each with a 'steps' list) ready for
    db_smoke.replace_all. Raises ParseError on a fatal read/shape problem."""
    try:
        with pd.ExcelFile(xlsx_path) as xf:
            if _SHEET_NAME not in xf.sheet_names:
                raise ParseError(
                    f"Sheet '{_SHEET_NAME}' not found in workbook.\n"
                    f"  Sheets present: {xf.sheet_names}")
            df = xf.parse(_SHEET_NAME, header=0)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"Could not read workbook: {exc}") from exc

    missing = [c for c in _REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ParseError(f"Missing expected columns: {missing}")

    steps_by_parent: dict[int, list[dict]] = {}
    for _, row in df[df["RowType"] == "Step"].iterrows():
        parent = _to_int(row["ParentRow"])
        if parent is None:
            continue  # orphan step — not attached to any scenario, drop
        steps_by_parent.setdefault(parent, []).append({
            "row_id": _to_int(row["RowID"]),
            "step": _clean(row["Step"]),
            "expected_result": _clean(row["Expected result"]),
            "comment": _clean(row["Comment"]),
            "owner_email": _clean(row["Owner eMail"]),
            "owner": _clean(row["Owner"]),
            "ws_executing": _clean(row["WS Executing"]),
            "aspen_ticket": _clean(row["ASPEN Ticket"]),
            "execution_status": _clean(row["Execution Status"]),
            "progress": _clean(row["Progress"]),
        })

    scenarios: list[dict] = []
    for _, row in df[df["RowType"] == "Scenario"].iterrows():
        ws = _WS_MAP.get((_clean(row["WS"]) or "").lower())
        if ws is None:
            continue  # not eCOM/Retail — ignore
        if not _is_wahr(row["MB Invoice Validation"]):
            continue  # MB Invoice Validation must be WAHR [USER 2026-08-27]
        row_id = _to_int(row["RowID"])
        scenarios.append({
            "row_id": row_id,
            "package": _clean(row["Package"]),
            "ws": ws,
            "scenario": _clean(row["Scenario"]),
            "comment": _clean(row["Comment"]),
            "status": _clean(row["Status"]),
            "company_code": _clean(row["Company Code"]),
            "sales_org": _clean(row["Sales Org."]),
            "plant": _clean(row["Plant (DC)"]),
            "store_code": _clean(row["Store Code"]),
            "steps": steps_by_parent.get(row_id, []),
        })
    return scenarios


def run_smoke_import(cfg: dict, xlsx_path: Path) -> dict:
    """Parse + replace-all import. Result dict mirrors run_delegated_import's
    shape: ok/error plus scenario/step counts."""
    result: dict = {"ok": False, "error": None, "xlsx_path": str(xlsx_path),
                    "scenarios": 0, "steps": 0}
    try:
        scenarios = parse_smoke_workbook(xlsx_path)
    except ParseError as exc:
        result["error"] = str(exc)
        return result
    if not scenarios:
        result["error"] = ("No eCOM/Retail scenarios with MB Invoice Validation"
                           " = WAHR found — is this the right workbook?")
        return result

    from app import database
    db_path = Path(cfg["database_path"])
    db_smoke.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        counts = db_smoke.replace_all(conn, scenarios)
    finally:
        conn.close()
    result.update(counts)
    result["ok"] = True
    return result
