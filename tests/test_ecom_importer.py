"""ECOM importer — characterization tests (day plan 05.07 step 7).

Excel fixture in, exact DB rows out. The rules a bug would silently break:
- match key = JIRA ID [USER]; rows without one land in the skiplog, never
  silently dropped, never inserted
- re-import updates the existing row (no duplicates), annotations survive
- Excel status/assignee are ECOM-vertical fields, strictly separate from
  the jira store's jira_status/jira_assignee
- headers with newlines / spaces around '/' (real tab quirks) still map
"""
from pathlib import Path

import openpyxl
import pytest

from app import database
from app.db import ecom as db_ecom
from app.ecom_importer import parse_ecom

# real headers from DTC_UAT_testtracking_ROE(24).xlsx / ECOM (incl. quirks:
# trailing newlines, newline mid-header, space before '/')
ECOM_HEADER = [
    "Status\n", "assigned to\n", "Country", "Testcase Scenario",
    "Test Case ID", "Testcase name", "Description Change", "Jira ID",
    "date execution started", "Order number /Transaction number",
    "Defect ID (if applicable)", "S4 Sales order", "S4 Billing Documents",
    "S4 journal invoice entry", "Delivery Note \n(for TradeCo)",
    "reason for pass \nwith reservation",
    "OLD \nOrder numbers / Transaction numbers", "comments",
]


def _wb(path: Path, rows: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ECOM"
    ws.append(ECOM_HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def _row(status="Not Ready", country="Germany (DE)", scenario="CANCELLATION",
         tc_id="CAN0001MU01", name="CAN0001MU01_Web-STH-Zeropick",
         desc_change="", jira="S4ECOM-1153", **extra):
    base = [status, "", country, scenario, tc_id, name, desc_change, jira,
            "", "", "", "", "", "", "", "", "", ""]
    for pos, val in extra.items():
        base[int(pos)] = val
    return base


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "ecom.db"
    database.init_db(p).close()
    db_ecom.init_schema(p)
    return p


def _cfg():
    return {"ecom_sheet_name": "ECOM"}


def test_parse_maps_real_headers_and_flags_missing_jira_id(tmp_path):
    xlsx = _wb(tmp_path / "t.xlsx", [
        _row(),
        _row(tc_id="CAN0001MU02", country="United Kingdom (GB)", jira=""),
        ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ])
    result = parse_ecom(_cfg(), xlsx_path=xlsx)
    assert result["unmapped_headers"] == []
    assert result["missing_fields"] == []
    rows = result["rows"]
    assert len(rows) == 2                      # fully blank row dropped silently
    assert rows[0]["_skip_reason"] == ""
    assert rows[0]["jira_id"] == "S4ECOM-1153"
    assert rows[0]["status"] == "Not Ready"
    assert rows[0]["test_case_id"] == "CAN0001MU01"
    assert rows[1]["_skip_reason"] == "missing jira id"


def test_upsert_by_jira_id_no_duplicates_and_annotation_survives(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx1 = _wb(tmp_path / "v1.xlsx", [_row(), _row(
            tc_id="CAN0001MU02", country="United Kingdom (GB)", jira="S4ECOM-1154")])
        r1 = db_ecom.upsert_ecom_rows(
            conn, parse_ecom(_cfg(), xlsx_path=xlsx1)["rows"], "2026-07-09")
        assert (r1["inserted"], r1["updated"], r1["skipped_missing_jira_id"]) == (2, 0, 0)

        db_ecom.upsert_ecom_annotation(conn, "S4ECOM-1153",
                                       next_step="ask key user", action_needed=True)

        # re-import: same jira ids, one status changed -> update, not insert
        xlsx2 = _wb(tmp_path / "v2.xlsx", [_row(status="Passed"), _row(
            tc_id="CAN0001MU02", country="United Kingdom (GB)", jira="S4ECOM-1154")])
        r2 = db_ecom.upsert_ecom_rows(
            conn, parse_ecom(_cfg(), xlsx_path=xlsx2)["rows"], "2026-07-10")
        assert (r2["inserted"], r2["updated"]) == (0, 2)

        rows = db_ecom.get_ecom_rows(conn)
        assert len(rows) == 2
        by_jira = {r["jira_id"]: r for r in rows}
        assert by_jira["S4ECOM-1153"]["status"] == "Passed"
        assert by_jira["S4ECOM-1153"]["first_seen"] == "2026-07-09"
        assert by_jira["S4ECOM-1153"]["last_seen"] == "2026-07-10"
        # authored annotation untouched by the importer
        assert by_jira["S4ECOM-1153"]["next_step"] == "ask key user"
        assert by_jira["S4ECOM-1153"]["action_needed"] == 1
    finally:
        conn.close()


def test_missing_jira_id_rows_go_to_skiplist_not_db(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx = _wb(tmp_path / "t.xlsx", [_row(jira="")])
        r = db_ecom.upsert_ecom_rows(
            conn, parse_ecom(_cfg(), xlsx_path=xlsx)["rows"], "2026-07-09")
        assert r["skipped_missing_jira_id"] == 1
        assert r["skipped_rows"][0]["reason"] == "missing jira id"
        assert db_ecom.get_ecom_rows(conn) == []
    finally:
        conn.close()


def test_match_key_tolerates_whitespace_and_case(tmp_path, db_path):
    conn = database.get_connection(db_path)
    try:
        xlsx1 = _wb(tmp_path / "v1.xlsx", [_row(jira="S4ECOM-1153")])
        db_ecom.upsert_ecom_rows(
            conn, parse_ecom(_cfg(), xlsx_path=xlsx1)["rows"], "2026-07-09")
        xlsx2 = _wb(tmp_path / "v2.xlsx", [_row(jira=" s4ecom-1153 ")])
        r = db_ecom.upsert_ecom_rows(
            conn, parse_ecom(_cfg(), xlsx_path=xlsx2)["rows"], "2026-07-09")
        assert (r["inserted"], r["updated"]) == (0, 1)
    finally:
        conn.close()
