"""Delegated Testing card: XML upload + buckets on the page, authored
fields (blocked reason / next step), detail page tabs, both reports."""
import io

import pytest

from app import database
from app.db import delegated as db_delegated
from app.db import jira as db_jira
import app.web_delegated as web_delegated
from app.web import app

XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="0.92"><channel>
  <item>
    <key id="1">S4ECOM-2001</key>
    <summary>SM2001_Blocked settlement case</summary>
    <status id="3">Blocked</status>
    <assignee username="JIRAUSER2">Tester, Tom</assignee>
    <link>https://jira.example.com/browse/S4ECOM-2001</link>
    <comments>
      <comment id="1" created="Mon, 24 Aug 2026 10:00:00 +0200">Order Number - TBY_SS_ADE0001111</comment>
      <comment id="2" created="Tue, 25 Aug 2026 10:00:00 +0200">Return Order: 6000084252</comment>
    </comments>
  </item>
  <item>
    <key id="2">S4ECOM-2002</key>
    <summary>SM2002_Marina gatekeeper case</summary>
    <status id="3">In Progress</status>
    <assignee username="JIRAUSER1">Haase, Marina [External]</assignee>
  </item>
  <item>
    <key id="3">S4ECOM-2003</key>
    <summary>SM2003_Team case</summary>
    <status id="3">In Progress</status>
    <assignee username="JIRAUSER2">Tester, Tom</assignee>
  </item>
  <item>
    <key id="4">S4ECOM-2004</key>
    <summary>SM2004_Odd status case</summary>
    <status id="3">Ready for Verification</status>
    <assignee username="JIRAUSER2">Tester, Tom</assignee>
  </item>
</channel></rss>
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "delegated.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_delegated.init_schema(db_path)
    monkeypatch.setattr(web_delegated, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setitem(web_delegated._cfg, "database_path", str(db_path))
    monkeypatch.setitem(web_delegated._cfg, "jira_gatekeeper_assignee", "Haase")
    monkeypatch.setattr(web_delegated, "_UPLOAD_FOLDER", tmp_path / "uploads")
    return app.test_client()


def _upload(client, data=XML, filename="delegated.xml"):
    return client.post("/delegated/upload", data={
        "file": (io.BytesIO(data.encode("utf-8")), filename)})


def test_upload_imports_and_page_shows_buckets(client):
    html = client.get("/delegated/").get_data(as_text=True)
    assert "No delegated tickets yet" in html

    resp = _upload(client)
    assert resp.status_code == 302 and "jira_ok=1" in resp.headers["Location"]

    html = client.get("/delegated/?jira_ok=1&jira_msg=x").get_data(as_text=True)
    assert "S4ECOM-2001" in html                       # blocked ticket present
    assert "BLOCKED" in html
    assert "Gatekeeper check Marina" in html
    assert "In progress with testing team" in html
    assert "Unexpected status" in html                 # odd status is visible
    assert "Return Order: 6000084252" in html          # LATEST comment's order
    # every section carries a ui-section color modifier — a bare rt-section
    # summary renders WHITE on white (invisible title) [USER 2026-08-26]
    assert 'class="rt-section "' not in html
    assert "ui-section--red" in html                   # BLOCKED section color


def test_upload_rejects_non_xml_and_missing_file(client):
    resp = _upload(client, filename="delegated.xlsx")
    assert "jira_ok=0" in resp.headers["Location"]
    resp = client.post("/delegated/upload", data={})
    assert "jira_ok=0" in resp.headers["Location"]


def test_upload_tags_delegated_without_touching_other_sources(client):
    _upload(client)
    conn = web_delegated._get_conn()
    try:
        rows = conn.execute(
            "SELECT seen_in_delegated, seen_in_gatekeeper, seen_in_ecom"
            " FROM jira_issues").fetchall()
    finally:
        conn.close()
    assert len(rows) == 4
    assert all(r[0] == 1 and r[1] == 0 and r[2] == 0 for r in rows)


def test_blocked_reason_and_next_step_save(client):
    _upload(client)
    assert client.post("/delegated/ticket/S4ECOM-2001/blocked-reason",
                       data={"blocked_reason": "waiting for settlement file"}
                       ).get_json()["ok"]
    assert client.post("/delegated/ticket/S4ECOM-2001/next-step",
                       data={"next_step": "chase GBS on Friday"}).get_json()["ok"]
    conn = web_delegated._get_conn()
    try:
        assert db_delegated.get_delegated_blocked_reason(
            conn, "S4ECOM-2001") == "waiting for settlement file"
        assert db_delegated.get_delegated_next_step(
            conn, "S4ECOM-2001") == "chase GBS on Friday"
    finally:
        conn.close()
    html = client.get("/delegated/").get_data(as_text=True)
    assert "waiting for settlement file" in html
    assert "chase GBS on Friday" in html


def test_detail_page_has_tabs_and_working_fields(client):
    _upload(client)
    html = client.get("/delegated/ticket/S4ECOM-2001").get_data(as_text=True)
    assert "Details" in html and "Messages (2)" in html
    assert "Why blocked" in html                       # blocked ticket
    html = client.get("/delegated/ticket/S4ECOM-2003").get_data(as_text=True)
    assert "Why blocked" not in html                   # not blocked
    assert client.get("/delegated/ticket/NOPE-1").status_code == 404


def test_detail_post_saves_both_fields(client):
    _upload(client)
    resp = client.post("/delegated/ticket/S4ECOM-2001", data={
        "blocked_reason": "missing master data", "next_step": "retest Monday"})
    assert resp.status_code == 302
    conn = web_delegated._get_conn()
    try:
        assert db_delegated.get_delegated_blocked_reason(
            conn, "S4ECOM-2001") == "missing master data"
        assert db_delegated.get_delegated_next_step(
            conn, "S4ECOM-2001") == "retest Monday"
    finally:
        conn.close()


def test_status_report_renders_buckets(client):
    _upload(client)
    client.post("/delegated/ticket/S4ECOM-2001/blocked-reason",
                data={"blocked_reason": "no settlement file yet"})
    html = client.get("/delegated/report").get_data(as_text=True)
    assert "Delegated Testing Report" in html
    assert "BLOCKED" in html
    assert "Gatekeeper check Marina" in html
    assert "no settlement file yet" in html            # why-blocked column
    assert "Return Order: 6000084252" in html          # LATEST comment's order
    # the report renders no comment bodies, so the OLDER comment's order
    # must not appear anywhere — proves the latest-comment-only rule
    assert "TBY_SS_ADE0001111" not in html


def test_numbers_report_counts(client):
    _upload(client)
    html = client.get("/delegated/numbers").get_data(as_text=True)
    assert "Delegated Testing Numbers" in html
    # blocked 1 · marina 1 · team 1 · unexpected 1 — all sections listed
    assert "Waiting for Settlementfile creation" in html
    assert "Resolved / Closed" in html


def test_report_download_is_standalone_attachment(client):
    _upload(client)
    client.post("/delegated/ticket/S4ECOM-2001/blocked-reason",
                data={"blocked_reason": "no settlement file yet"})
    resp = client.get("/delegated/report/download")
    assert resp.status_code == 200
    assert 'attachment; filename="delegated_report_' in resp.headers["Content-Disposition"]
    html = resp.get_data(as_text=True)
    assert "Delegated Testing Report" in html
    assert "no settlement file yet" in html            # content intact
    # interactive chrome is stripped: toolbar, filter bar, scripts, inputs
    assert 'class="toolbar"' not in html
    assert 'class="filterbar"' not in html
    assert "<script>" not in html
    assert "co-input" not in html.split("</style>")[1]  # no call-out inputs in the body


def test_report_page_keeps_its_buttons(client):
    _upload(client)
    html = client.get("/delegated/report").get_data(as_text=True)
    assert "🔢 Numbers" in html
    assert "⬇ Download HTML" in html
    # no Print button on the report [USER 2026-08-26] — Ctrl+P still works
    assert 'onclick="window.print()"' not in html


def test_numbers_download_is_standalone_attachment(client):
    _upload(client)
    resp = client.get("/delegated/numbers/download")
    assert resp.status_code == 200
    assert 'attachment; filename="delegated_numbers_' in resp.headers["Content-Disposition"]
    html = resp.get_data(as_text=True)
    assert "Delegated Testing Numbers" in html
    assert "Waiting for Settlementfile creation" in html
    # toolbar (app-local links) and the copy script are stripped
    assert 'class="toolbar"' not in html
    assert "<script>" not in html


def test_reimport_refreshes_status(client):
    _upload(client)
    updated = XML.replace(">Blocked<", ">In Review<")
    _upload(client, updated, "delegated_v2.xml")
    html = client.get("/delegated/").get_data(as_text=True)
    assert "Ready for Sales validations" in html
    conn = web_delegated._get_conn()
    try:
        row = conn.execute("SELECT jira_status FROM jira_issues"
                           " WHERE jira_key='S4ECOM-2001'").fetchone()
    finally:
        conn.close()
    assert row[0] == "In Review"
