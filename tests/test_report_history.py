"""Report history (2026-08-05) — auto rows on email send + workbook-tab import.

What must hold:
- the ReportRetail-style tab parses: label row found below a junk header
  row, dates in 21.05.2026 style AND real datetime cells, description/blank
  rows skipped, value-carrying rows with unreadable dates counted, unknown
  columns reported (known non-bucket columns like "Total number of test
  cases" ignored silently)
- tab import upserts per (report, date): corrected Excel cells update the
  row on re-import, nothing is deleted
- email send saves the ticked bucket reports under the EMAIL date and
  replaces on a same-date resend; spillover/board are not snapshotted
- the history page renders with switcher; unknown report falls back
"""
from datetime import datetime

import openpyxl
import pytest

from app import database, emailer
from app.db import manual_tests as db_manual
from app.db import report_history as db_hist
from app.report_history_importer import (import_report_tabs, parse_report_tab,
                                         snapshot_reports)
import app.web_email as web_email
import app.web_report_history as web_hist
from app.web import app

RETAIL_LABELS = ["date", "Total number of test cases", "Back with sales",
                 "with DTC", "in progress with DTC", "Passed with DTC",
                 "Incoming (Gatekeeper)", "Ready for validation",
                 "In Progress", "In Clarification", "Blocked", "Mystery"]


def _report_wb(path, data_rows, sheet="ReportRetail"):
    """Mimic the real tab: junk header row, label row, description row, data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(["", "", "", "", "", "", "IN Progress Breakdown"])
    ws.append(RETAIL_LABELS)
    ws.append(["", "coming from Sales", "", "everything in dtc bucket"])
    for r in data_rows:
        ws.append(r)
    wb.save(path)
    return path


def _row(day, back=1, with_dtc=2, passed=1):
    return [day, "115", back, with_dtc, "1", passed, "", "3", "2", "", "1", "99"]


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "hist.db"
    database.init_db(p).close()
    db_manual.init_schema(p)
    db_hist.init_schema(p)
    from app.db import retrofits as db_retrofits
    db_retrofits.init_schema(p)   # Retail/ECOM reports render the retrofits section
    monkeypatch.setattr(web_hist, "_db_path", p)
    monkeypatch.setattr(web_email, "_db_path", p)
    return p


def test_parse_report_tab_real_layout(tmp_path):
    xlsx = _report_wb(tmp_path / "t.xlsx", [
        _row("21.05.2026"),
        _row(datetime(2026, 5, 22)),          # real datetime cell
        ["no date but values", "", 5, 5],     # -> skipped_no_date
        ["", "", "", ""],                     # blank -> silently ignored
    ])
    parsed = parse_report_tab(xlsx, "ReportRetail")
    assert parsed["unmapped"] == ["Mystery"]
    assert parsed["skipped_no_date"] == 1
    dates = [r["date"] for r in parsed["rows"]]
    assert dates == ["2026-05-21", "2026-05-22"]
    b = parsed["rows"][0]["buckets"]
    assert b["back_with_sales"] == 1
    assert b["with_dtc"] == 2
    assert b["passed_with_dtc"] == 1
    assert b["in_clarification"] is None       # blank cell -> NULL
    assert "date" not in b                     # non-bucket labels not stored


def test_tab_import_upserts_and_updates(tmp_path, db_path):
    cfg = {"downloads_folder": str(tmp_path), "filename_stem": "DTC_UAT_testtracking_ROE",
           "report_history_tabs": {"retail": "ReportRetail"}}
    conn = database.get_connection(db_path)
    try:
        _report_wb(tmp_path / "DTC_UAT_testtracking_ROE.xlsx", [_row("21.05.2026")])
        r1 = import_report_tabs(cfg, conn)
        assert r1["reports"]["retail"]["imported"] == 1

        # corrected cell in the Excel -> re-import updates the same date row
        _report_wb(tmp_path / "DTC_UAT_testtracking_ROE.xlsx",
                   [_row("21.05.2026", back=7)])
        import_report_tabs(cfg, conn)
        rows = db_hist.list_history(conn, "retail")
        assert len(rows) == 1
        assert rows[0]["back_with_sales"] == 7
        assert rows[0]["source"] == "excel"
    finally:
        conn.close()


def test_snapshot_on_send_replaces_same_date(db_path):
    conn = database.get_connection(db_path)
    try:
        conn.execute("INSERT INTO retail (match_key, test_case_id, country, status)"
                     " VALUES ('a', 'TC1', 'DE', 'Passed')")
        conn.execute("INSERT INTO retail (match_key, test_case_id, country, status)"
                     " VALUES ('b', 'TC2', 'DE', 'Blocked DTC')")
        conn.commit()
        saved = snapshot_reports(conn, ["retail", "spillover", "board"], "2026-08-05")
        assert saved == ["retail"]                 # non-bucket choices ignored
        rows = db_hist.list_history(conn, "retail")
        assert len(rows) == 1
        assert rows[0]["passed_with_dtc"] == 1
        assert rows[0]["blocked"] == 1
        assert rows[0]["source"] == "email"

        # status moves, same date resent -> row replaced, not duplicated
        conn.execute("UPDATE retail SET status = 'Passed' WHERE match_key = 'b'")
        conn.commit()
        snapshot_reports(conn, ["retail"], "2026-08-05")
        rows = db_hist.list_history(conn, "retail")
        assert len(rows) == 1
        assert rows[0]["passed_with_dtc"] == 2
    finally:
        conn.close()


def test_email_send_writes_history(db_path, monkeypatch):
    conn = database.get_connection(db_path)
    try:
        conn.execute("INSERT INTO retail (match_key, test_case_id, country, status)"
                     " VALUES ('a', 'TC1', 'DE', 'Passed')")
        conn.commit()
        from app.db import email as db_email
        db_email.init_schema(db_path)
        db_email.add_recipient(conn, "m@example.com", "M")
        rid = [r["id"] for r in db_email.list_recipients(conn)][0]
    finally:
        conn.close()
    monkeypatch.setitem(web_email._cfg, "email_user", "u@gmx.de")
    monkeypatch.setitem(web_email._cfg, "email_password", "pw")
    monkeypatch.setattr(emailer, "send_message", lambda settings, msg: None)

    resp = app.test_client().post("/email-report/send", data={
        "date": "2026-08-05", "reports": ["retail"], "recipients": [str(rid)]})
    assert resp.status_code == 302
    assert "History" in resp.headers["Location"]

    conn = database.get_connection(db_path)
    try:
        rows = db_hist.list_history(conn, "retail")
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["report_date"] == "2026-08-05"
    assert rows[0]["source"] == "email"


def test_history_page_renders_with_switcher(db_path):
    conn = database.get_connection(db_path)
    try:
        db_hist.upsert_history_row(conn, "retail", "2026-08-04",
                                   {"with_dtc": 5}, source="excel")
        db_hist.upsert_history_row(conn, "retail", "2026-08-05",
                                   {"with_dtc": 6}, source="email")
    finally:
        conn.close()
    c = app.test_client()
    html = c.get("/report-history/?report=retail").get_data(as_text=True)
    assert "Report History — Retail" in html
    assert html.index("2026-08-05") < html.index("2026-08-04")   # newest first
    assert "Manual Retail" in html                               # switcher
    html = c.get("/report-history/?report=nope").get_data(as_text=True)
    assert "Report History — Retail" in html                     # fallback
    html = c.get("/report-history/?report=manual_ecom").get_data(as_text=True)
    assert "No history yet" in html
