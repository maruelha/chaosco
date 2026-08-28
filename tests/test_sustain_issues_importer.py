"""Sustainphase Issues (build plan step 2, 2026-08-28): importer —
Defects tab, header-name column mapping, date normalisation, upsert
wiring."""
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from app import database
from app.db import sustain_issues as db_si
from app.sustain_issues_importer import (ParseError,
                                         parse_sustain_issues_workbook,
                                         run_sustain_issues_import)

HEADERS = ["Channel", "Sales or DTC\n", "ASPEN STATUS", "Defect ID",
           "Short description",
           "more Defect description\n (expected result vs actual)",
           "Comment", "raised by", "order number", "Date Reported",
           "Date Closed", "Priority", "Assigned to", "Tech Team", "Country",
           "Scenario", "affected testcases", "Retest Dependency",
           "Does it block execution", "Exists in production (yes/no)",
           "Defect reason"]


def _workbook(tmp_path, rows) -> Path:
    wb = openpyxl.Workbook()
    wb.active.title = "SMOKETEST_KT"
    ws = wb.create_sheet("Defects")
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    wb.create_sheet("Datasheet")
    path = tmp_path / "DTC_Sustainphase_Tracking (1).xlsx"
    wb.save(path)
    return path


def _sample_rows():
    return [
        ["Retail", "DTC", "Open", "ASPEN-1", "Settlement file missing",
         "expected X got Y", None, "Marina", "4711088",
         datetime(2026, 8, 28, 0, 0), None, "High", "GBS", "SAP Team",
         "France", "POS settlement", "TC-12", None, "yes", "no",
         "Config"],
        ["eCom", "Sales", "New", None, "Wrong VAT on invoice", None, None,
         "KeyUser IT", None, datetime(2026, 8, 27, 0, 0), None, "Medium",
         None, None, "Italy", None, None, None, "no", "yes", None],
    ]


def test_parse_maps_headers_and_normalises_dates(tmp_path):
    rows = parse_sustain_issues_workbook(_workbook(tmp_path, _sample_rows()))
    assert len(rows) == 2
    first = rows[0]
    assert first["defect_id"] == "ASPEN-1"
    assert first["sales_dtc"] == "DTC"          # header had a newline
    assert first["description"] == "expected X got Y"
    assert first["order_number"] == "4711088"
    assert first["date_reported"] == "2026-08-28"
    assert first["blocks_execution"] == "yes"
    assert first["excel_row"] == 2
    assert "exists" not in first                 # ignored column dropped
    second = rows[1]
    assert second["defect_id"] is None
    assert second["short_description"] == "Wrong VAT on invoice"


def test_parse_errors_without_defects_sheet_or_headers(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Datasheet"
    path = tmp_path / "x DTC_Sustainphase_Tracking.xlsx"
    wb.save(path)
    with pytest.raises(ParseError):
        parse_sustain_issues_workbook(path)

    wb = openpyxl.Workbook()
    wb.active.title = "Defects"
    wb.active.append(["Something", "Else"])
    wb.save(path)
    with pytest.raises(ParseError):
        parse_sustain_issues_workbook(path)


def test_run_import_upserts(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    cfg = {"database_path": str(db_path)}
    result = run_sustain_issues_import(cfg, _workbook(tmp_path, _sample_rows()))
    assert result["ok"], result["error"]
    assert result["rows"] == 2
    assert result["inserted"] == 2

    conn = database.get_connection(db_path)
    try:
        keys = sorted(i["issue_key"] for i in db_si.list_issues(conn))
        assert keys == ["ASPEN-1", "SUS-001"]
    finally:
        conn.close()


def test_run_import_empty_defects_tab_is_ok(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    result = run_sustain_issues_import({"database_path": str(db_path)},
                                       _workbook(tmp_path, []))
    assert result["ok"]
    assert result["rows"] == 0
