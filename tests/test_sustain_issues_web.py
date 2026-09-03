"""Sustainphase Issues pages (rewritten 2026-09-03 [USER]): upload of the
Go-Live defect tracker, the incidents board (comment history, filters,
notes + next step), the read-only Issue Solution tracker page, the
computed Totals page."""
import io
from datetime import datetime

import pytest

from app import database
from app.db import sustain_issues as db_si
import app.web_sustain_issues as web_si
from app.web import app

from tests.test_sustain_issues_importer import workbook_bytes

FILENAME = "Go-Live defect tracker (1).xlsx"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "si.db"
    database.init_db(db_path).close()
    db_si.init_schema(db_path)
    monkeypatch.setattr(web_si, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setitem(web_si._cfg, "database_path", str(db_path))
    monkeypatch.setattr(web_si, "_UPLOAD_FOLDER", tmp_path / "uploads")
    import app.web_next_steps as web_next_steps
    import app.web_notes as web_notes
    from app.db import next_steps as db_ns
    db_ns.init_schema(db_path)
    monkeypatch.setattr(web_next_steps, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _upload(client, data=None, filename=FILENAME):
    data = data if data is not None else workbook_bytes(
        incidents=[["INC001", datetime(2026, 9, 1), "Anna", "Invoice missing", "Open",
                    "Tom", "first look"],
                   ["INC002", datetime(2026, 9, 2), "Ben", "Price wrong", "Closed",
                    None, None]],
        solutions=[["Tom", "SALES", "E1", "Order rejected", None, "INC001", "Mapping",
                    "Fix mapping", "Open", None],
                   ["Anna", "n/a", None, "Unknown thing", None, None, "Data", "Reload",
                    "Closed", None]])
    return client.post("/sustain-issues/upload", data={
        "file": (io.BytesIO(data), filename)})


def test_home_empty_state_and_filename_guard(client):
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "No incidents yet" in html and "Go-Live defect tracker" in html
    resp = _upload(client, filename="Something.xlsx")
    assert "si_ok=0" in resp.headers["Location"]
    resp = _upload(client, filename="go-live defect tracker (2).xlsx")   # case-insensitive
    assert "si_ok=1" in resp.headers["Location"]


def test_upload_board_history_filters_notes_and_next_step(client):
    from urllib.parse import unquote_plus
    resp = _upload(client)
    loc = unquote_plus(resp.headers["Location"])
    assert "2 incidents — 2 new · 0 updated · 1 new comments" in loc
    assert "2 issue-solution rows" in loc and "interfaces" in loc

    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "INC001" in html and "Invoice missing" in html
    assert 'data-requestor="Anna"' in html and 'data-assigned="Tom"' in html
    assert 'data-status="Closed"' in html
    assert "first look" in html and "si-comment--latest" in html
    # filter bar: text search + the three dropdowns from the values in use
    assert 'id="si-filter-search"' in html
    assert '<option value="Anna">' in html and '<option value="Closed">' in html
    assert '<option value="Tom">' in html
    # notes component per incident + next-step buttons
    assert 'id="notes-sustain_incident-INC001"' in html
    assert 'data-entity-type="sustain_incident" data-entity-id="INC001"' in html

    # second upload: changed comment on INC001 goes ON TOP, INC002 unchanged
    _upload(client, workbook_bytes(
        incidents=[["INC001", datetime(2026, 9, 1), "Anna", "Invoice missing",
                    "In Progress", "Tom", "fixed in AIF"],
                   ["INC002", datetime(2026, 9, 2), "Ben", "Price wrong", "Closed",
                    None, None]]))
    html = client.get("/sustain-issues/").get_data(as_text=True)
    body = html.split('data-key="INC001"')[1].split("</details>")[0]
    assert body.index("fixed in AIF") < body.index("first look")
    assert 'data-status="In Progress"' in html

    # next step inline save + the generic archive entity
    r = client.post("/sustain-issues/incident/INC001/next-step",
                    json={"next_step": "call Tom"})
    assert r.get_json()["ok"]
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "→ call Tom" in html
    r = client.post("/next-steps/sustain_incident/INC001/archive")
    assert r.status_code == 200
    conn = database.get_connection(client.db_path)
    try:
        assert db_si.get_sustain_incident_next_step(conn, "INC001") is None
    finally:
        conn.close()

    # a note on an incident lands back on the list
    r = client.post("/n/sustain_incident/INC001/add",
                    data={"heading": "Call", "note": "spoke to Tom", "return_to": "list"})
    assert r.status_code == 302 and "/sustain-issues/" in r.headers["Location"]
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "spoke to Tom" in html
    assert client.get("/n/sustain_incident/NOPE/add").status_code == 404


def test_solutions_page_is_read_only_with_filters_and_search(client):
    _upload(client)
    html = client.get("/sustain-issues/solutions").get_data(as_text=True)
    assert "Order rejected" in html and "Fix mapping" in html
    assert 'id="sol-filter-search"' in html
    for f in ("owner", "interface", "msg", "external_reference", "inc_reference", "status"):
        assert f'id="sol-filter-{f}"' in html
    assert 'id="sol-filter-reason"' not in html          # Reason is in the text search
    assert '<option value="n/a">' in html and '<option value="INC001">' in html
    assert 'data-search="order rejected mapping fix mapping"' in html
    assert "<form" not in html.split("page-header")[1]   # no edit possibility


def test_totals_page_computes_per_interface_and_reason(client):
    _upload(client)
    html = client.get("/sustain-issues/totals").get_data(as_text=True)
    sales = html.split('<span class="mono">SALES</span>')[1].split("</summary>")[0]
    assert sales.count('class="num">1</span>') == 2       # all 1, open 1
    assert "(not on the Total tab)" in html and "n/a" in html
    assert "Total issue # per reason" in html
    assert "Mapping" in html and "Data" in html
    # click a line → its rows [USER]: the SALES line's body holds the tracker row
    body = html.split('<span class="mono">SALES</span>')[1].split("</details>")[0]
    assert "Order rejected" in body and "Fix mapping" in body and "INC001" in body
    assert "⎘ Copy rows" in body and "siCopyRows" in html
    # the download keeps the expandable lines, drops toolbar + copy buttons
    resp = client.get("/sustain-issues/totals/download")
    assert 'attachment; filename="sustain_totals_' in resp.headers["Content-Disposition"]
    dl = resp.get_data(as_text=True)
    assert "<details" in dl and "Order rejected" in dl
    assert "Copy rows" not in dl and "siCopyRows" not in dl and 'class="toolbar"' not in dl
    # grand total = tracker row count
    conn = database.get_connection(client.db_path)
    try:
        t = db_si.interface_totals(conn)
    finally:
        conn.close()
    assert t["total_all"] == 2 and t["total_open"] == 1


def test_incidents_report_groups_by_status_newest_comment_no_next_step(client):
    _upload(client)
    client.post("/sustain-issues/incident/INC001/next-step", json={"next_step": "call Tom"})
    html = client.get("/sustain-issues/report").get_data(as_text=True)
    assert "ASPEN Incidents" in html
    open_part = html.split("<span>Open</span>")[1].split("sec-status")[0]
    closed_part = html.split("<span>Closed</span>")[1]
    assert "INC001" in open_part and "INC002" not in open_part
    assert "INC002" in closed_part
    assert "first look" in open_part                      # newest comment only
    assert "call Tom" not in html                         # no next step [USER]
    assert 'id="rf-search"' in html and '<option value="Anna">' in html
    resp = client.get("/sustain-issues/report/download")
    assert 'attachment; filename="sustain_incidents_' in resp.headers["Content-Disposition"]
    dl = resp.get_data(as_text=True)
    assert "INC001" in dl and 'class="toolbar"' not in dl and "rfApply" not in dl


def test_both_reports_are_email_report_choices(client):
    from app.emailer import REPORT_CHOICES, gather_attachments
    from app import web_core
    keys = [k for k, _ in REPORT_CHOICES]
    assert "sustain_incidents" in keys and "sustain_totals" in keys
    _upload(client)
    conn = database.get_connection(client.db_path)
    try:
        out = gather_attachments(conn, {}, web_core.app,
                                 ["sustain_incidents", "sustain_totals"], "2026-09-03")
    finally:
        conn.close()
    assert [n for n, _ in out] == ["sustain_incidents_2026-09-03.html",
                                   "sustain_totals_2026-09-03.html"]
    assert "INC001" in out[0][1] and "SALES" in out[1][1]
