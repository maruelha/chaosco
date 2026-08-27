"""CORE SOUTH Smoke Testing importer (build plan step 2, 2026-08-27):
Excel fixture in, exact filtered scenarios+steps out. The rules a bug
would silently break:
- keep only WS in {eCOM, Retail} AND MB Invoice Validation = WAHR
- everything else (other WS, non-WAHR) is dropped, not imported
- steps attach to their scenario via ParentRow == scenario RowID
- re-import replaces the previous set wholesale
"""
from pathlib import Path

import openpyxl
import pytest

from app import database
from app.db import smoke as db_smoke
from app.smoke_importer import ParseError, parse_smoke_workbook, run_smoke_import

_HEADER = [
    "RowID", "RowType", "WS", "Package", "Scenario", "Comment", "Status",
    "Company Code", "Sales Org.", "Plant (DC)", "Store Code",
    "MB Invoice Validation", "ParentRow", "Step", "Expected result",
    "Owner eMail", "Owner", "WS Executing", "ASPEN Ticket",
    "Execution Status", "Progress",
]
_COL = {name: i for i, name in enumerate(_HEADER)}


def _row(**vals) -> list:
    row = [None] * len(_HEADER)
    for key, val in vals.items():
        row[_COL[key]] = val
    return row


def _wb(path: Path, rows: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "EU CS Smoke Test execution"
    ws.append(_HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def _sample_rows() -> list[list]:
    rows = [
        # eCOM scenario, WAHR — kept, with 2 steps
        _row(RowID=100, RowType="Scenario", WS="eCOM", Package="Click & Collect",
             Scenario="Fulfill C&C order", Status="Not Started",
             **{"Company Code": "PT01", "Sales Org.": "PT01", "Plant (DC)": "IT33",
                "MB Invoice Validation": 1.0}),
        _row(RowID=101, RowType="Step", ParentRow=100, Step="Create order",
             **{"Expected result": "Order created", "Owner eMail": "a@b.com",
                "Owner": "A B"}),
        _row(RowID=102, RowType="Step", ParentRow=100, Step="Ship order",
             **{"Expected result": "Order shipped"}),
        # eCOM scenario, NOT WAHR (blank) — dropped
        _row(RowID=110, RowType="Scenario", WS="eCOM", Package="Ship from Campus South",
             Scenario="Not validated scenario", Status="Not Started",
             **{"MB Invoice Validation": None}),
        _row(RowID=111, RowType="Step", ParentRow=110, Step="orphaned by filter"),
        # Retail scenario, WAHR — kept, with 1 step + store code
        _row(RowID=200, RowType="Scenario", WS="Retail", Package="Store Sales",
             Scenario="Store sale FR", Status="In Progress",
             **{"Company Code": "FR01", "Sales Org.": "FR01", "Store Code": "FRBY",
                "MB Invoice Validation": 1.0}),
        _row(RowID=201, RowType="Step", ParentRow=200, Step="Ring up sale"),
        # Wholesale scenario, WAHR — WS not in scope, dropped
        _row(RowID=300, RowType="Scenario", WS="Wholesale", Package="Bulk",
             Scenario="Wholesale scenario",
             **{"MB Invoice Validation": 1.0}),
        # Package row — RowType Package, always ignored
        _row(RowID=1, RowType="Package", WS="eCOM", Package="Click & Collect"),
    ]
    return rows


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "smoke.db"
    database.init_db(p).close()
    db_smoke.init_schema(p)
    return p


def _cfg(db_path: Path) -> dict:
    return {"database_path": str(db_path)}


def test_parse_keeps_only_ecom_retail_wahr_scenarios(tmp_path):
    xlsx = _wb(tmp_path / "t.xlsx", _sample_rows())
    scenarios = parse_smoke_workbook(xlsx)
    assert {s["row_id"] for s in scenarios} == {100, 200}


def test_parse_links_steps_via_parent_row(tmp_path):
    xlsx = _wb(tmp_path / "t.xlsx", _sample_rows())
    scenarios = {s["row_id"]: s for s in parse_smoke_workbook(xlsx)}
    assert [st["row_id"] for st in scenarios[100]["steps"]] == [101, 102]
    assert [st["row_id"] for st in scenarios[200]["steps"]] == [201]


def test_parse_carries_retail_store_code(tmp_path):
    xlsx = _wb(tmp_path / "t.xlsx", _sample_rows())
    scenarios = {s["row_id"]: s for s in parse_smoke_workbook(xlsx)}
    assert scenarios[200]["store_code"] == "FRBY"
    assert scenarios[100]["store_code"] is None


def test_parse_raises_on_missing_sheet(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Wrong Sheet Name"
    xlsx = tmp_path / "t.xlsx"
    wb.save(xlsx)
    with pytest.raises(ParseError):
        parse_smoke_workbook(xlsx)


def test_run_smoke_import_writes_filtered_rows(tmp_path, db_path):
    xlsx = _wb(tmp_path / "t.xlsx", _sample_rows())
    result = run_smoke_import(_cfg(db_path), xlsx)
    assert result["ok"] is True
    assert result["scenarios"] == 2
    assert result["steps"] == 3

    conn = database.get_connection(db_path)
    try:
        ecom = db_smoke.list_scenarios(conn, "eCOM")
        retail = db_smoke.list_scenarios(conn, "Retail")
    finally:
        conn.close()
    assert len(ecom) == 1 and len(ecom[0]["steps"]) == 2
    assert len(retail) == 1 and len(retail[0]["steps"]) == 1


def test_run_smoke_import_replaces_previous_import(tmp_path, db_path):
    xlsx = _wb(tmp_path / "t.xlsx", _sample_rows())
    run_smoke_import(_cfg(db_path), xlsx)

    # second import with only the retail scenario present
    xlsx2 = _wb(tmp_path / "t2.xlsx", [r for r in _sample_rows()
                                        if not (len(r) > _COL["RowID"] and
                                                r[_COL["RowID"]] in (100, 101, 102))])
    result = run_smoke_import(_cfg(db_path), xlsx2)
    assert result["scenarios"] == 1

    conn = database.get_connection(db_path)
    try:
        assert db_smoke.list_scenarios(conn, "eCOM") == []
        assert len(db_smoke.list_scenarios(conn, "Retail")) == 1
    finally:
        conn.close()


def test_run_smoke_import_errors_when_nothing_matches(tmp_path, db_path):
    rows = [_row(RowID=300, RowType="Scenario", WS="Wholesale",
                 **{"MB Invoice Validation": 1.0})]
    xlsx = _wb(tmp_path / "t.xlsx", rows)
    result = run_smoke_import(_cfg(db_path), xlsx)
    assert result["ok"] is False
    assert "No eCOM/Retail" in result["error"]
