"""Manual Test Cases importers — Excel fixture in, exact DB rows out.

The rules a bug would silently break:
- both tabs match by test_case + country (Retail rule — the ECOM tab's
  Jira ID is blank in the real data and must NOT carry the match)
- real header quirks still map: trailing newlines, newline mid-header,
  space before '/', blank header columns (pandas "Unnamed: N"), the bare
  duplicate "Order number" column on the Retail tab
- rows with an incomplete key go to the skiplog, never inserted
- re-import updates (no duplicates), first_seen survives
- the same test case + country may exist in BOTH tables (real overlap
  MU01–07) without clashing
- db field lists stay in sync with the importer's output fields
"""
from pathlib import Path

import openpyxl
import pytest

from app import database
from app.db import manual_tests as db_manual
from app.manual_importer import output_fields, parse_manual

# real headers from DTC_UAT_testtracking_ROE(46).xlsx (2026-08-05)
RETAIL_HEADER = [
    None, "Status", "assigned to\n", "Key user responsible", "Country",
    "Testcase Scenario", "Test Case", "Test Case Description",
    "execution started", "Execution completed", "Store No.",
    "Order number /Transaction number", "Defect ID (if applicable)",
    "S4 Sales order", "S4 Billing Documents", "S4 journal invoice entry",
    "Delivery Note", "Comment", "reason for pass \nwith reservation",
    "OLD \nOrder numbers / Transaction numbers", "old defect ids",
    "Concatenate", "Sales Status", "Order number",
]
ECOM_HEADER = [
    "Status\n", None, "assigned to\n", "Country", "Testcase Scenario",
    "Test Case ID", "Testcase name", "Description Change", "Jira ID",
    "date execution started", "Order number /Transaction number",
    "Defect ID (if applicable)", "S4 Sales order", "S4 Billing Documents",
    "S4 journal invoice entry", "Delivery Note \n(for TradeCo)",
    "reason for pass \nwith reservation",
    "OLD \nOrder numbers / Transaction numbers", "comments",
]

RETAIL_SHEET = "Manual Test Cases | Retail"
ECOM_SHEET = "Manual Test Cases | ECOM"


def _wb(path: Path, sheet: str, header: list, rows: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def _retail_row(status="Ready for Validation", country="Germany",
                tc="CDI0000MU01", name="CDI0000MU01_Settlement",
                scenario="Settlement File Validation", defect_ref=""):
    r = [""] * len(RETAIL_HEADER)
    r[1], r[4], r[5], r[6], r[7], r[12] = status, country, scenario, tc, name, defect_ref
    return r


def _ecom_row(status="Ready for Validation", country="Austria",
              tc="CDI0000MU01", name="CDI0000MU01_Settlement",
              scenario="Settlement File Validation Zalando", jira=""):
    r = [""] * len(ECOM_HEADER)
    r[0], r[3], r[4], r[5], r[6], r[8] = status, country, scenario, tc, name, jira
    return r


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "manual.db"
    database.init_db(p).close()
    db_manual.init_schema(p)
    return p


def test_db_fields_match_importer_output_fields():
    for vertical in db_manual.TABLES:
        assert sorted(db_manual.FIELDS[vertical]) == sorted(output_fields(vertical))


def test_parse_retail_maps_real_headers(tmp_path):
    xlsx = _wb(tmp_path / "t.xlsx", RETAIL_SHEET, RETAIL_HEADER, [
        _retail_row(),
        _retail_row(country="", tc="CDI0000MU02"),          # incomplete key
        [""] * len(RETAIL_HEADER),                           # fully blank
    ])
    result = parse_manual({}, "manual_retail", xlsx_path=xlsx)
    # blank first column is ignored, Concatenate ignored; only the bare
    # duplicate "Order number" column stays unmapped (first-wins alias rule)
    assert result["unmapped_headers"] == ["Order number"]
    assert result["missing_fields"] == []
    rows = result["rows"]
    assert len(rows) == 2                                    # blank row dropped
    assert rows[0]["_skip_reason"] == ""
    assert rows[0]["test_case_id"] == "CDI0000MU01"
    assert rows[0]["testcase_name"] == "CDI0000MU01_Settlement"
    assert rows[0]["status"] == "Ready for Validation"
    assert rows[1]["_skip_reason"] == "incomplete key"


def test_parse_ecom_maps_real_headers(tmp_path):
    xlsx = _wb(tmp_path / "t.xlsx", ECOM_SHEET, ECOM_HEADER, [
        _ecom_row(jira="S4ECOM-9999"),
    ])
    result = parse_manual({}, "manual_ecom", xlsx_path=xlsx)
    assert result["unmapped_headers"] == []
    # the real ECOM tab has no OLD Defect IDs column
    assert result["missing_fields"] == ["old_defect_ids"]
    row = result["rows"][0]
    assert row["_skip_reason"] == ""
    assert row["test_case_id"] == "CDI0000MU01"
    assert row["comment"] == ""                              # "comments" mapped
    assert row["jira_id"] == "S4ECOM-9999"
    assert row["execution_started"] == ""                    # "date execution started"


def test_ecom_blank_jira_id_is_fine_key_is_tc_plus_country(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx = _wb(tmp_path / "t.xlsx", ECOM_SHEET, ECOM_HEADER, [
            _ecom_row(country="Austria"), _ecom_row(country="Belgium")])
        r = db_manual.upsert_manual_rows(
            conn, "manual_ecom",
            parse_manual({}, "manual_ecom", xlsx_path=xlsx)["rows"], "2026-08-05")
        assert (r["inserted"], r["updated"], r["skipped_blank_key"]) == (2, 0, 0)
    finally:
        conn.close()


def test_upsert_no_duplicates_first_seen_survives(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx1 = _wb(tmp_path / "v1.xlsx", RETAIL_SHEET, RETAIL_HEADER,
                    [_retail_row()])
        db_manual.upsert_manual_rows(
            conn, "manual_retail",
            parse_manual({}, "manual_retail", xlsx_path=xlsx1)["rows"], "2026-08-05")

        xlsx2 = _wb(tmp_path / "v2.xlsx", RETAIL_SHEET, RETAIL_HEADER,
                    [_retail_row(status="Passed", defect_ref="DEF-123")])
        r2 = db_manual.upsert_manual_rows(
            conn, "manual_retail",
            parse_manual({}, "manual_retail", xlsx_path=xlsx2)["rows"], "2026-08-06")
        assert (r2["inserted"], r2["updated"]) == (0, 1)

        rows = db_manual.get_manual_rows(conn, "manual_retail")
        assert len(rows) == 1
        assert rows[0]["status"] == "Passed"
        assert rows[0]["defect_id_ref"] == "DEF-123"
        assert rows[0]["first_seen"] == "2026-08-05"
        assert rows[0]["last_seen"] == "2026-08-06"
    finally:
        conn.close()


def test_incomplete_key_rows_go_to_skiplist_not_db(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx = _wb(tmp_path / "t.xlsx", RETAIL_SHEET, RETAIL_HEADER,
                   [_retail_row(tc="")])
        r = db_manual.upsert_manual_rows(
            conn, "manual_retail",
            parse_manual({}, "manual_retail", xlsx_path=xlsx)["rows"], "2026-08-05")
        assert r["skipped_blank_key"] == 1
        assert r["skipped_rows"][0]["reason"] == "incomplete key"
        assert db_manual.get_manual_rows(conn, "manual_retail") == []
    finally:
        conn.close()


def test_same_tc_and_country_may_live_in_both_tables(tmp_path, db_path):
    """Real overlap: MU01–07 exist on BOTH tabs — separate tables, no clash."""
    conn = database.get_connection(db_path)
    try:
        xr = _wb(tmp_path / "r.xlsx", RETAIL_SHEET, RETAIL_HEADER,
                 [_retail_row(country="Germany")])
        xe = _wb(tmp_path / "e.xlsx", ECOM_SHEET, ECOM_HEADER,
                 [_ecom_row(country="Germany")])
        db_manual.upsert_manual_rows(
            conn, "manual_retail",
            parse_manual({}, "manual_retail", xlsx_path=xr)["rows"], "2026-08-05")
        db_manual.upsert_manual_rows(
            conn, "manual_ecom",
            parse_manual({}, "manual_ecom", xlsx_path=xe)["rows"], "2026-08-05")
        assert len(db_manual.get_manual_rows(conn, "manual_retail")) == 1
        assert len(db_manual.get_manual_rows(conn, "manual_ecom")) == 1
    finally:
        conn.close()


def test_duplicate_tc_country_rows_skip_to_skiplog_one_line_wins(tmp_path, db_path):
    """ONE line per test case + country [USER 2026-08-05]: the real ECOM tab
    repeats CDI0000MU34 within a country — judged a data DEFECT in the
    workbook. First occurrence wins; the rest are counted + skiplogged."""
    conn = database.get_connection(db_path)
    try:
        rows3 = [_ecom_row(tc="CDI0000MU34", country="Austria",
                           scenario="Settlement File Validation")] * 3
        xlsx1 = _wb(tmp_path / "v1.xlsx", ECOM_SHEET, ECOM_HEADER, rows3)
        r1 = db_manual.upsert_manual_rows(
            conn, "manual_ecom",
            parse_manual({}, "manual_ecom", xlsx_path=xlsx1)["rows"], "2026-08-05")
        assert (r1["inserted"], r1["updated"], r1["skipped_duplicate"]) == (1, 0, 2)
        assert r1["skipped_rows"][0]["reason"] == "duplicate test case+country in file"

        # re-import: still one row, duplicates still skipped, no growth
        xlsx2 = _wb(tmp_path / "v2.xlsx", ECOM_SHEET, ECOM_HEADER, rows3)
        r2 = db_manual.upsert_manual_rows(
            conn, "manual_ecom",
            parse_manual({}, "manual_ecom", xlsx_path=xlsx2)["rows"], "2026-08-06")
        assert (r2["inserted"], r2["updated"], r2["skipped_duplicate"]) == (0, 1, 2)
        assert len(db_manual.get_manual_rows(conn, "manual_ecom")) == 1
    finally:
        conn.close()


def test_status_counts_and_filters(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx = _wb(tmp_path / "t.xlsx", RETAIL_SHEET, RETAIL_HEADER, [
            _retail_row(country="Germany"),
            _retail_row(country="Poland", status="Passed"),
            _retail_row(country="Norway", tc="CDI0000MU02",
                        scenario="Audit of Store Cash reconciliation"),
        ])
        db_manual.upsert_manual_rows(
            conn, "manual_retail",
            parse_manual({}, "manual_retail", xlsx_path=xlsx)["rows"], "2026-08-05")

        counts = db_manual.get_manual_status_counts(conn, "manual_retail")
        assert counts == {"Ready for Validation": 2, "Passed": 1}

        opts = db_manual.get_manual_filter_options(conn, "manual_retail")
        assert opts["countries"] == ["Germany", "Norway", "Poland"]

        rows = db_manual.get_manual_rows(conn, "manual_retail",
                                         statuses=["Passed"])
        assert [r["country"] for r in rows] == ["Poland"]
        rows = db_manual.get_manual_rows(conn, "manual_retail",
                                         search="MU02")
        assert [r["country"] for r in rows] == ["Norway"]
    finally:
        conn.close()
