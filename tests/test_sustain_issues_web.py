"""Sustainphase Issues card (build plan step 2, 2026-08-28): upload page
+ file-picker import wiring."""
import io
from datetime import datetime

import openpyxl
import pytest

from app import database
from app.db import sustain_issues as db_si
import app.web_sustain_issues as web_si
from app.web import app

from tests.test_sustain_issues_importer import HEADERS

FILENAME = "DTC_Sustainphase_Tracking (1).xlsx"


def _xlsx_bytes(rows=None) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Defects"
    ws.append(HEADERS)
    default = [["Retail", "DTC", "Open", "ASPEN-1", "Settlement file missing",
                None, None, "Marina", "4711088", datetime(2026, 8, 28), None,
                "High", None, None, "France", None, None, None, "yes", "no",
                None]]
    for r in (default if rows is None else rows):
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "si.db"
    database.init_db(db_path).close()
    db_si.init_schema(db_path)
    monkeypatch.setattr(web_si, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setitem(web_si._cfg, "database_path", str(db_path))
    monkeypatch.setattr(web_si, "_UPLOAD_FOLDER", tmp_path / "uploads")
    return app.test_client()


def _upload(client, data=None, filename=FILENAME):
    data = data if data is not None else _xlsx_bytes()
    return client.post("/sustain-issues/upload", data={
        "file": (io.BytesIO(data), filename)})


def test_home_shows_empty_state(client):
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "Sustainphase Issues" in html
    assert "No issues yet" in html


def test_upload_imports_and_reports_counts(client):
    resp = _upload(client)
    assert resp.status_code == 302 and "si_ok=1" in resp.headers["Location"]
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "1 new" in html

    conn = web_si._get_conn()
    try:
        assert db_si.issue_count(conn) == 1
    finally:
        conn.close()


def test_upload_rejects_wrong_files(client):
    resp = _upload(client, filename="notes.txt")
    assert "si_ok=0" in resp.headers["Location"]
    resp = _upload(client, filename="DTC_UAT_testtracking_ROE.xlsx")
    assert "si_ok=0" in resp.headers["Location"]
    resp = client.post("/sustain-issues/upload", data={})
    assert "si_ok=0" in resp.headers["Location"]


def test_upload_empty_defects_tab_is_ok(client):
    resp = _upload(client, data=_xlsx_bytes(rows=[]))
    assert "si_ok=1" in resp.headers["Location"]


def test_upload_dated_copy_kept(client, tmp_path):
    _upload(client)
    assert len(list((tmp_path / "uploads").glob("sustain_issues_*.xlsx"))) == 1


def test_callouts_and_next_step_save(client):
    _upload(client)
    resp = client.post("/sustain-issues/issue/ASPEN-1/callouts",
                       json={"callouts": "mgmt attention"})
    assert resp.get_json()["ok"]
    resp = client.post("/sustain-issues/issue/ASPEN-1/next-step",
                       json={"next_step": "retest FR"})
    assert resp.get_json()["ok"]
    conn = web_si._get_conn()
    try:
        anns = db_si.get_sustain_issue_annotations(conn)
        assert anns["ASPEN-1"] == {"callouts": "mgmt attention",
                                   "next_step": "retest FR"}
    finally:
        conn.close()
