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
    # the generic next-step archive (entity 'sustain_issue') runs in its
    # own module
    import app.web_next_steps as web_next_steps
    from app.db import next_steps as db_ns
    db_ns.init_schema(db_path)
    monkeypatch.setattr(web_next_steps, "_get_conn",
                        lambda: database.get_connection(db_path))
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


# ---------------------------------------------------------------------------
# List view (build plan step 3)

def _two_row_bytes():
    return _xlsx_bytes(rows=[
        ["Retail", "DTC", "Open", "ASPEN-1", "Settlement file missing",
         None, None, "Marina", "4711088", datetime(2026, 8, 28), None,
         "High", None, None, "France", None, None, None, "yes", "no", None],
        ["eCom", "Sales", "Closed", "ASPEN-2", "Wrong VAT on invoice",
         None, None, None, None, datetime(2026, 8, 20),
         datetime(2026, 8, 27), "Medium", None, None, "Italy", None, None,
         None, "no", "no", None],
    ])


def test_list_splits_open_and_closed_with_filters(client):
    _upload(client, data=_two_row_bytes())
    html = client.get("/sustain-issues/").get_data(as_text=True)
    # open/closed split by Date Closed (the filterbar above the sections
    # also contains the string "Closed", so anchor inside the sections)
    open_block = html.split("Open issues", 1)[1].split("Closed", 1)[0]
    assert "ASPEN-1" in open_block
    assert "Wrong VAT on invoice" not in open_block
    assert "ASPEN-2" in html
    # blocks-execution red chip only on the blocking issue
    assert html.count("blocks execution") == 1
    # filter dropdowns carry the distinct values
    assert 'id="si-filter-channel"' in html
    assert '<option value="Retail">Retail</option>' in html
    assert '<option value="Closed">Closed</option>' in html
    # data attributes drive the client-side filter
    assert 'data-channel="eCom" data-status="Closed"' in html


def test_list_renders_callouts_and_next_step(client):
    _upload(client, data=_two_row_bytes())
    client.post("/sustain-issues/issue/ASPEN-1/callouts",
                json={"callouts": "mgmt attention"})
    client.post("/sustain-issues/issue/ASPEN-1/next-step",
                json={"next_step": "retest FR"})
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "mgmt attention" in html and "📣" in html
    assert "→ retest FR" in html


def test_placeholder_promotion_shows_former_id(client):
    # first upload without ASPEN id -> SUS-001; second with it -> promoted
    no_id = _xlsx_bytes(rows=[
        ["Retail", "DTC", "Open", None, "Settlement file missing", None,
         None, None, None, None, None, "High", None, None, "France", None,
         None, None, "no", "no", None]])
    _upload(client, data=no_id)
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert "SUS-001" in html
    _upload(client)   # default row carries ASPEN-1, same description
    html = client.get("/sustain-issues/").get_data(as_text=True)
    assert 'title="formerly SUS-001"' in html
    assert ">SUS-001<" not in html   # placeholder no longer a visible key


def test_next_step_archive_via_generic_component(client):
    _upload(client)
    client.post("/sustain-issues/issue/ASPEN-1/next-step",
                json={"next_step": "chase GBS"})
    resp = client.post("/next-steps/sustain_issue/ASPEN-1/archive")
    data = resp.get_json()
    assert data["ok"] and data["archived"] == "chase GBS"
    listing = client.get("/next-steps/sustain_issue/ASPEN-1/list.json").get_json()
    assert [i["next_step"] for i in listing["items"]] == ["chase GBS"]


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
