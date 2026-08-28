"""Core South Sustainphase Monitoring (build plan step 2, 2026-08-27):
importer — tab-name pattern → (day, stream), parent/detail split via
Task ID + outline level, replace-per-tab write."""
from pathlib import Path

import openpyxl
import pytest

from app import database
from app.db import sustain as db_sustain
from app.sustain_importer import (ParseError, parse_sustain_workbook,
                                  run_sustain_import)

HEADERS = ["Task ID", "L4 Taxonomy", "Process / Task", "Cadence",
           "Due Today", "Country", "Provider / Partner / Financial Account",
           "France Result", "Italy Result", "Portugal Result", "Spain Result",
           "Task Overall (DO NOT EDIT)"]


def _sheet(wb, title):
    ws = wb.create_sheet(title)
    ws["A1"] = "Retail Daily Operations Checklist Template"
    ws["H3"], ws["H4"] = "DUE TASKS", 2
    for col, header in enumerate(HEADERS, start=1):
        ws.cell(6, col, header)
    return ws


def _row(ws, r, values, outline_level=0):
    for col, v in enumerate(values, start=1):
        ws.cell(r, col, v)
    if outline_level:
        ws.row_dimensions[r].outline_level = outline_level
        ws.row_dimensions[r].hidden = True


def _workbook(tmp_path) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    retail = _sheet(wb, "Retail_2026-09-01")
    _row(retail, 7, ["1", "Settlement", "Monitor files", "Daily", "Yes",
                     None, "Adyen (POS)", "OK ", "N/A", "N/A", "N/A", "OK"])
    _row(retail, 8, [None, None, "↳ Detail check", "Daily", "Yes", "France",
                     "Adyen for cards", "diff 12,50", "N/A", "N/A", "N/A",
                     None], outline_level=1)
    _row(retail, 9, [None, None, "↳ Detail check", "Monthly", "No", "France",
                     "Voucher CadhoC", "Not due", "N/A", "N/A", "N/A",
                     None], outline_level=1)
    _row(retail, 10, [2, "Clearing", "Monitor items", "Daily", "Yes",
                      None, "Sundry", None, None, None, None, "Pending"])
    _row(retail, 12, [None] * 12)  # trailing blank row is ignored
    ecom = _sheet(wb, "eCom_2026-09-01")
    _row(ecom, 7, ["1", "Settlement", "Monitor files", "Daily", "Yes",
                   None, "AAEFR-ADIDAS_FR", "OK", "N/A", "N/A", "N/A", "OK"])
    wb.create_sheet("Instructions")["A1"] = "not a day tab"
    path = tmp_path / "1_0109_0409-O2C DTC_GBS Operations_checklist.xlsx"
    wb.save(path)
    return path


def test_parse_splits_tabs_parents_and_details(tmp_path):
    tabs = parse_sustain_workbook(_workbook(tmp_path))
    assert [(t["day"], t["stream"]) for t in tabs] == [
        ("2026-09-01", "Retail"), ("2026-09-01", "eCom")]
    retail = tabs[0]["tasks"]
    assert [t["task_id"] for t in retail] == ["1", "2"]
    assert retail[0]["excel_row"] == 7
    assert retail[0]["result_fr"] == "OK"      # stripped
    assert retail[0]["provider"] == "Adyen (POS)"
    details = retail[0]["details"]
    assert [(d["excel_row"], d["country"], d["due_today"]) for d in details] \
        == [(8, "France", "Yes"), (9, "France", "No")]
    assert details[0]["result_fr"] == "diff 12,50"
    assert retail[1]["details"] == []
    # numeric Task ID (2) is normalised to text
    assert retail[1]["task_id"] == "2"


def test_parse_rejects_wrong_structure(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Retail_2026-09-01"   # matching name, but no header row 6
    ws["A1"] = "something else"
    path = tmp_path / "x DTC_GBS Operations_checklist.xlsx"
    wb.save(path)
    with pytest.raises(ParseError):
        parse_sustain_workbook(path)


def test_parse_no_day_tabs(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Instructions"
    path = tmp_path / "other.xlsx"
    wb.save(path)
    assert parse_sustain_workbook(path) == []


def test_run_sustain_import_writes_per_tab(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    cfg = {"database_path": str(db_path)}
    result = run_sustain_import(cfg, _workbook(tmp_path))
    assert result["ok"], result["error"]
    assert result["tabs"] == 2
    assert result["tasks"] == 3
    assert result["details"] == 2

    conn = database.get_connection(db_path)
    try:
        assert [(t["day"], t["stream"], t["task_count"])
                for t in db_sustain.list_tabs(conn)] == [
            ("2026-09-01", "Retail", 2), ("2026-09-01", "eCom", 1)]
        # the free-text detail entry rolls up to attention
        counts = db_sustain.summary_counts(conn, "2026-09-01", "Retail")
        assert counts == {"due": 2, "completed": 0, "pending": 1,
                          "attention": 1}
    finally:
        conn.close()


def test_run_sustain_import_error_on_wrong_workbook(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    wb = openpyxl.Workbook()
    wb.active.title = "Instructions"
    path = tmp_path / "other.xlsx"
    wb.save(path)
    result = run_sustain_import({"database_path": str(db_path)}, path)
    assert not result["ok"]
    assert "day tabs" in result["error"]
