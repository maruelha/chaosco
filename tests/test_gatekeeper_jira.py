"""Old Gatekeeper page: Jira import button + tickets table (2026-07-11)."""
import pytest

from app import database
from app.db import jira as db_jira
import app.web_reference as web_reference
from app.web import app

XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="0.92"><channel>
  <item>
    <key id="1">S4ECOM-1492</key>
    <summary>PCS0001MU01_DE_Sportscheck ShipfromDC and Return</summary>
    <status id="3">Blocked</status>
    <assignee username="JIRAUSER1">Haase, Marina [External]</assignee>
    <link>https://jira.example.com/browse/S4ECOM-1492</link>
    <description>&lt;p&gt;DE Sportscheck ShipfromDC &amp; Return&lt;/p&gt;</description>
    <comments>
      <comment id="1" created="Mon, 29 Jun 2026 16:00:00 +0200">Order Number - TBY_SS_ADE0006955 DN - 320982487</comment>
    </comments>
  </item>
</channel></rss>
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "gk.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    folder = tmp_path / "jira_gk"
    folder.mkdir()
    (folder / "export.xml").write_text(XML, encoding="utf-8")
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setitem(web_reference._cfg, "database_path", str(db_path))
    monkeypatch.setitem(web_reference._cfg, "jira_gatekeeper_folder", str(folder))
    return app.test_client()


def test_import_button_fills_table_with_comments(client):
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert "No Jira data yet" in html

    resp = client.post("/ecom-gatekeeper/import-jira")
    assert resp.status_code == 302 and "jira_ok=1" in resp.headers["Location"]

    html = client.get("/ecom-gatekeeper?jira_ok=1&jira_msg=x").get_data(as_text=True)
    assert "S4ECOM-1492" in html
    assert "PCS0001MU01" in html                      # solman id from the summary
    assert "Blocked" in html
    assert "DE Sportscheck ShipfromDC" in html        # description rendered
    assert "TBY_SS_ADE0006955" in html                # order number in the comment
    assert "Jira import" in html                      # result banner


def test_import_error_is_shown_not_raised(client, tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setitem(web_reference._cfg, "jira_gatekeeper_folder", str(empty))
    resp = client.post("/ecom-gatekeeper/import-jira")
    assert "jira_ok=0" in resp.headers["Location"]
