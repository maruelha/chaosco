"""Known Production Issues (rename + rebuild, 2026-08-06).

What must hold:
- new fields (channel, type, scenario dropdown, sub_case, how_to_detect,
  how_to_handle) save and round-trip on create + edit
- an existing free-text scenario not in the fixed list stays visible
  (never silently lost or forced)
- list page: Channel/Scenario columns + filters, note count on Edit
- inbox filing target 'prod_defect': search + file + nonexistent refused
- download route produces a standalone snapshot; email pre-tick + the
  gather_attachments branch both work
"""
from pathlib import Path

import pytest

from app import database, emailer
from app.db import email as db_email
import app.web_core as web_core
import app.web_email as web_email
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "prod_defects.db"
    database.init_db(db_path).close()
    db_email.init_schema(db_path)
    monkeypatch.setattr(web_core, "_db_path", db_path)
    monkeypatch.setattr(web_email, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _new(client, **fields):
    base = {"short_description": "issue", "scenario": "GWC"}
    base.update(fields)
    resp = client.post("/prod_defects/new", data=base)
    record_id = int(resp.headers["Location"].split("/prod_defects/")[1].split("?")[0])
    return record_id


def test_create_and_edit_round_trip_new_fields(client):
    record_id = _new(client, channel="ECOM", type="Defect",
                     sub_case="several items in one order row, GWC applied",
                     how_to_detect="check order lines for GWC flag",
                     how_to_handle="manual credit note")
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["channel"] == "ECOM"
    assert row["type"] == "Defect"
    assert row["sub_case"] == "several items in one order row, GWC applied"
    assert row["how_to_detect"] == "check order lines for GWC flag"
    assert row["how_to_handle"] == "manual credit note"
    assert row["scenario"] == "GWC"

    client.post(f"/prod_defects/{record_id}", data={
        "short_description": "issue", "scenario": "SFDC", "channel": "Retail",
        "type": "Risk", "how_to_handle": "escalate",
    })
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["channel"] == "Retail" and row["type"] == "Risk"
    assert row["scenario"] == "SFDC"
    assert row["how_to_handle"] == "escalate"


def test_legacy_scenario_not_in_fixed_list_stays_visible(client):
    record_id = _new(client, scenario="A very old free-text scenario")
    html = client.get(f"/prod_defects/{record_id}").get_data(as_text=True)
    assert "A very old free-text scenario (current)" in html
    assert 'selected>A very old free-text scenario (current)' in html \
        or "A very old free-text scenario (current)</option>" in html


def test_list_columns_filters_and_note_count(client):
    ecom_id = _new(client, short_description="EcomIssue", scenario="GWC", channel="ECOM")
    _new(client, short_description="RetailIssue", scenario="SFDC", channel="Retail")

    html = client.get("/prod_defects").get_data(as_text=True)
    assert "Known Production Issues" in html
    for col in ("Channel", "Scenario", "Short Description", "Biz Impact",
               "How to handle", "Confluence"):
        assert col in html
    assert "EcomIssue" in html and "RetailIssue" in html

    html = client.get("/prod_defects?channel=ECOM").get_data(as_text=True)
    assert "EcomIssue" in html and "RetailIssue" not in html

    html = client.get("/prod_defects?scenario=SFDC").get_data(as_text=True)
    assert "RetailIssue" in html and "EcomIssue" not in html

    conn = database.get_connection(client.db_path)
    try:
        database.add_note(conn, "prod_defect", str(ecom_id), heading="h", note_text="n")
    finally:
        conn.close()
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "Edit (1)" in html


def test_confluence_link_rendered_from_config(client, monkeypatch):
    import app.web_defects as web_defects
    monkeypatch.setitem(web_defects._cfg, "prod_defects_confluence_url",
                        "https://confluence.example/page")
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "https://confluence.example/page" in html


def test_inbox_filing_target(client):
    record_id = _new(client, short_description="Findable issue", scenario="GWC")
    conn = database.get_connection(client.db_path)
    try:
        note_id = database.add_inbox_item(conn, "H", "route me")
    finally:
        conn.close()

    hits = client.get("/inbox/targets?type=prod_defect&q=Findable").get_json()
    assert hits and hits[0]["value"] == str(record_id)

    conn = database.get_connection(client.db_path)
    try:
        assert database.file_inbox_item(conn, note_id, "prod_defect", str(record_id))
        assert database.list_notes(conn, "prod_defect", str(record_id))
        # nonexistent target refused
        assert not database.file_inbox_item(conn, note_id, "prod_defect", "99999")
    finally:
        conn.close()


def test_inbox_picker_has_known_prod_issue_option(client):
    conn = database.get_connection(client.db_path)
    try:
        database.add_inbox_item(conn, "H", "text")
    finally:
        conn.close()
    html = client.get("/inbox").get_data(as_text=True)
    assert '<option value="prod_defect">Known Prod Issue</option>' in html


def test_download_route_produces_standalone_snapshot(client):
    _new(client, short_description="DownloadRow", scenario="GWC")
    resp = client.get("/prod_defects/download")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "known_prod_defects_" in resp.headers["Content-Disposition"]
    html = resp.get_data(as_text=True)
    assert "DownloadRow" in html
    assert "<script" not in html                # standalone_html strips scripts
    assert ",form," in html                     # forms hidden via injected CSS rule


def test_email_page_pretick_and_gather_attachments():
    assert ("known_prod_defects", "Known Production Issues") in emailer.REPORT_CHOICES


def test_email_pretick_query_param(client):
    html = client.get("/email-report/?reports=known_prod_defects").get_data(as_text=True)
    assert 'value="known_prod_defects" checked' in html
    assert 'value="retail" checked' not in html
    # no query param at all -> default behaviour unchanged (everything ticked)
    html = client.get("/email-report/").get_data(as_text=True)
    assert 'value="retail" checked' in html


def test_gather_attachments_includes_known_prod_defects(client):
    _new(client, short_description="AttachMe", scenario="GWC")
    conn = database.get_connection(client.db_path)
    try:
        atts = emailer.gather_attachments(conn, {}, app, ["known_prod_defects"], "2026-08-06")
    finally:
        conn.close()
    assert [name for name, _ in atts] == ["known_prod_defects_2026-08-06.html"]
    assert "AttachMe" in atts[0][1]
