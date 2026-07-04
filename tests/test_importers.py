"""Characterization tests for the three original importers (refactoring step 2).

These pin the CURRENT behavior of parse + upsert so later refactoring
(splitting database.py, moving modules) can be proven harmless. They cover
the edge-case knowledge the importers accumulated:

- messy header normalization ("ECOM/\nRETAIL" -> channel/area)
- fully blank rows ignored silently; content rows without a key skipped + logged
- duplicate defect_id within one import: first kept, rest skipped
- idempotency: re-running the same import inserts 0, updates all,
  preserves first_seen, bumps last_seen
- retail match key is case/whitespace-insensitive (test_case_id || country)
- spillover match key is the excel row number (stable under renames)
"""
from pathlib import Path

import openpyxl
import pytest

from app import database
from app.read_defects import parse_defects
from app.retail_importer import parse_retail
from app.spillover_importer import parse_spillover


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def conn(tmp_path):
    c = database.init_db(tmp_path / "test.db")
    yield c
    c.close()


def _wb(path: Path, sheet: str, header: list, rows: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Defects
# ---------------------------------------------------------------------------

DEFECT_HEADER = ["ECOM/\nRETAIL", "Solman Status", "Defect ID", "Solman Name",
                 "Priority", "Assigned to", "Comment", "Mystery Column"]


@pytest.fixture()
def defects_xlsx(tmp_path):
    return _wb(tmp_path / "defects.xlsx", "Defects", DEFECT_HEADER, [
        ["Retail", "In Progress", "1000001", "POS crash on return", "High", "AB", "note", "x"],
        ["ECOM", "New", "1000002", "Voucher rejected", "Medium", "CD", "", ""],
        [None, None, None, None, None, None, None, None],          # fully blank -> ignored
        ["Retail", "New", "", "row without id", "Low", "", "", ""],  # blank id -> skipped
        ["Retail", "New", "1000001", "duplicate id", "Low", "", "", ""],  # dup -> skipped
    ])


def test_defects_parse_normalises_messy_headers(defects_xlsx):
    out = parse_defects({"defects_sheet_name": "Defects"}, xlsx_path=defects_xlsx)
    row = out["rows"][0]
    assert row["channel"] == "Retail"          # from "ECOM/\nRETAIL"
    assert row["defect_id"] == "1000001"
    assert "Comment" in out["ignored_headers"]
    assert "Mystery Column" in out["unmapped_headers"]
    assert "date_reported" in out["missing_fields"]  # absent column -> reported


def test_defects_upsert_rules_and_idempotency(defects_xlsx, conn):
    rows = parse_defects({"defects_sheet_name": "Defects"}, xlsx_path=defects_xlsx)["rows"]

    r1 = database.upsert_defects(conn, rows, today="2026-07-01")
    assert (r1["inserted"], r1["updated"]) == (2, 0)
    assert r1["ignored_blank"] == 1
    assert r1["skipped_blank_id"] == 1
    assert r1["skipped_duplicate"] == 1
    assert {s["reason"] for s in r1["skipped_rows"]} == {"blank_defect_id", "duplicate_defect_id"}

    # second run of the same file: nothing new, everything updated
    r2 = database.upsert_defects(conn, rows, today="2026-07-02")
    assert (r2["inserted"], r2["updated"]) == (0, 2)
    first, last = conn.execute(
        "SELECT first_seen, last_seen FROM defects WHERE defect_id='1000001'").fetchone()
    assert first == "2026-07-01"   # never changes
    assert last == "2026-07-02"    # bumps every run


# ---------------------------------------------------------------------------
# Spillover
# ---------------------------------------------------------------------------

SPILLOVER_HEADER = ["Type", "ECOM\n/Retail", "Status", "Assigned to", "ID",
                    "Name", "Order Numbers", "Country", "Content", "Comment"]


@pytest.fixture()
def spillover_xlsx(tmp_path):
    return _wb(tmp_path / "spill.xlsx", "Core South Spillover", SPILLOVER_HEADER, [
        ["Defect", "Retail", "Open", "AB", "J-1", "Broken pricing", "123", "DE", "c", ""],
        [None] * 10,                                                    # blank -> dropped
        ["Defect", "Retail", "Open", "", "", "", "", "", "content but no name", ""],
    ])


def test_spillover_parse_flags_blank_names(spillover_xlsx):
    out = parse_spillover({"spillover_sheet_name": "Core South Spillover",
                           "downloads_folder": ".", "filename_stem": "x"},
                          xlsx_path=spillover_xlsx)
    assert len(out["rows"]) == 2                       # blank row dropped
    assert out["rows"][0]["_skip_reason"] == ""
    assert out["rows"][0]["area"] == "Retail"          # from "ECOM\n/Retail"
    assert out["rows"][1]["_skip_reason"] == "blank name"


def test_spillover_upsert_matches_on_excel_row(spillover_xlsx, conn):
    rows = parse_spillover({"spillover_sheet_name": "Core South Spillover",
                            "downloads_folder": ".", "filename_stem": "x"},
                           xlsx_path=spillover_xlsx)["rows"]
    r1 = database.upsert_spillover_rows(conn, rows, today="2026-07-01")
    assert (r1["inserted"], r1["updated"], r1["skipped_blank_name"]) == (1, 0, 1)

    # a rename does NOT create a new row — the excel row is the identity
    rows[0]["name"] = "Broken pricing (renamed)"
    r2 = database.upsert_spillover_rows(conn, rows, today="2026-07-02")
    assert (r2["inserted"], r2["updated"]) == (0, 1)
    name, first, last = conn.execute(
        "SELECT name, first_seen, last_seen FROM spillover").fetchone()
    assert name == "Broken pricing (renamed)"
    assert (first, last) == ("2026-07-01", "2026-07-02")


# ---------------------------------------------------------------------------
# Retail
# ---------------------------------------------------------------------------

RETAIL_HEADER = ["Test Case", "Country", "Testcase Name", "Status", "Assigned to",
                 "Comment", "Concatenate"]


@pytest.fixture()
def retail_xlsx(tmp_path):
    return _wb(tmp_path / "retail.xlsx", "Retail", RETAIL_HEADER, [
        ["GKPMU000005", "Germany", "GKPMU000005_Sale of the Book", "Passed", "AB", "", "ignored"],
        ["GKPMU000005", "Poland", "GKPMU000005_Sale of the Book", "Not Ready", "", "", ""],
        ["GKPMU000006", "", "row without country", "New", "", "", ""],   # incomplete key
        [None] * 7,                                                       # blank -> dropped
    ])


def test_retail_parse_flags_incomplete_keys(retail_xlsx):
    out = parse_retail({"retail_sheet_name": "Retail",
                        "downloads_folder": ".", "filename_stem": "x"},
                       xlsx_path=retail_xlsx)
    assert len(out["rows"]) == 3
    assert [r["_skip_reason"] for r in out["rows"]] == ["", "", "incomplete key"]
    assert "Concatenate" not in out["unmapped_headers"]  # recognised + ignored


def test_retail_upsert_key_is_case_insensitive(retail_xlsx, conn):
    rows = parse_retail({"retail_sheet_name": "Retail",
                         "downloads_folder": ".", "filename_stem": "x"},
                        xlsx_path=retail_xlsx)["rows"]
    r1 = database.upsert_retail_rows(conn, rows, today="2026-07-01")
    assert (r1["inserted"], r1["updated"], r1["skipped_blank_key"]) == (2, 0, 1)

    # same test re-imported with different casing/whitespace -> same row
    rows[0]["test_case_id"] = "  gkpmu000005 "
    rows[0]["country"] = "GERMANY"
    rows[0]["status"] = "Ready for retest"
    r2 = database.upsert_retail_rows(conn, rows, today="2026-07-02")
    assert (r2["inserted"], r2["updated"]) == (0, 2)
    status, first, last = conn.execute(
        "SELECT status, first_seen, last_seen FROM retail"
        " WHERE match_key = 'gkpmu000005||germany'").fetchone()
    assert status == "Ready for retest"        # a reopened test un-counts downstream
    assert (first, last) == ("2026-07-01", "2026-07-02")
