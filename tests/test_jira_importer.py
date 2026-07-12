"""Shared Jira store + XML importer (day plan 05.07 step 2).

Fixture modeled on the real export (Jira RSS, DC 10.3): the bare-& quirk,
HTML descriptions, an empty description, a comment thread without usable
authors, epic/markets as custom fields. The rules a bug would silently
break:
- bare & in summaries/descriptions must not kill the parse
- solman_id = summary before the first "_" (None without underscore)
- re-import refreshes ONLY jira_status / jira_assignee / comments;
  everything else keeps its first-import value
- comments are REPLACED per import, never appended
- newest .xml per folder wins, filenames irrelevant
"""
import time

import pytest

from app import database
from app.db import jira as db_jira
from app.jira_importer import (
    newest_xml,
    parse_jira_xml,
    run_jira_import,
)

XML_V1 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="0.92">
<channel>
  <title>XML Export</title>
  <item>
    <title>[GK-101] SM1234_Blind Return DE & AT</title>
    <link>https://jira.example.com/browse/GK-101</link>
    <key id="10001">GK-101</key>
    <summary>SM1234_Blind Return DE & AT</summary>
    <type id="1">Bug</type>
    <priority id="3">Medium</priority>
    <status id="3">Open</status>
    <assignee username="JIRAUSER123">Marina H.</assignee>
    <created>Mon, 30 Jun 2026 10:00:00 +0200</created>
    <updated>Tue, 1 Jul 2026 09:00:00 +0200</updated>
    <description>&lt;p&gt;Return fails for DE &amp; AT orders&lt;/p&gt;</description>
    <comments>
      <comment id="1" author="JIRAUSER123" created="Mon, 30 Jun 2026 11:00:00 +0200">&lt;p&gt;First look — SF &amp; order check needed&lt;/p&gt;</comment>
      <comment id="2" author="JIRAUSER456" created="Mon, 30 Jun 2026 12:00:00 +0200">&lt;p&gt;Reproduced&lt;/p&gt;</comment>
    </comments>
    <customfields>
      <customfield id="customfield_10014" key="com.pyxis.greenhopper.jira:gh-epic-link">
        <customfieldname>Epic Link</customfieldname>
        <customfieldvalues><customfieldvalue>GK-EPIC-7</customfieldvalue></customfieldvalues>
      </customfield>
      <customfield id="customfield_20001" key="com.atlassian.jira.plugin:select">
        <customfieldname>Markets</customfieldname>
        <customfieldvalues>
          <customfieldvalue>DE</customfieldvalue>
          <customfieldvalue>AT</customfieldvalue>
        </customfieldvalues>
      </customfield>
    </customfields>
  </item>
  <item>
    <title>[GK-102] Voucher edge case</title>
    <link>https://jira.example.com/browse/GK-102</link>
    <key id="10002">GK-102</key>
    <summary>Voucher edge case</summary>
    <type id="1">Bug</type>
    <priority id="2">High</priority>
    <status id="1">In Progress</status>
    <assignee username="JIRAUSER456">JIRAUSER456</assignee>
    <description></description>
  </item>
</channel>
</rss>
"""

# second export: GK-101 got a new status/assignee/comments AND a changed
# summary+epic (which must NOT overwrite), GK-103 is new
XML_V2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="0.92">
<channel>
  <item>
    <key id="10001">GK-101</key>
    <summary>SM9999_RENAMED summary</summary>
    <status id="5">Resolved</status>
    <assignee username="JIRAUSER456">Someone Else</assignee>
    <description>&lt;p&gt;rewritten&lt;/p&gt;</description>
    <comments>
      <comment id="3" created="Wed, 2 Jul 2026 08:00:00 +0200">&lt;p&gt;Fixed in build 42&lt;/p&gt;</comment>
    </comments>
    <customfields>
      <customfield id="customfield_10014">
        <customfieldname>Epic Link</customfieldname>
        <customfieldvalues><customfieldvalue>OTHER-EPIC</customfieldvalue></customfieldvalues>
      </customfield>
    </customfields>
  </item>
  <item>
    <key id="10003">GK-103</key>
    <summary>SM7777_New ticket</summary>
    <status id="3">Open</status>
  </item>
</channel>
</rss>
"""


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

@pytest.fixture()
def xml_v1(tmp_path):
    p = tmp_path / "export1.xml"
    p.write_text(XML_V1, encoding="utf-8")
    return p


def test_parse_survives_bare_ampersands_and_reads_fields(xml_v1):
    issues = {i["jira_key"]: i for i in parse_jira_xml(xml_v1)}
    assert set(issues) == {"GK-101", "GK-102"}

    i = issues["GK-101"]
    assert i["summary"] == "SM1234_Blind Return DE & AT"
    assert i["solman_id"] == "SM1234"
    assert i["epic"] == "GK-EPIC-7"
    assert i["markets"] == "DE, AT"
    assert i["jira_status"] == "Open"
    assert i["jira_assignee"] == "Marina H."
    assert i["type"] == "Bug" and i["priority"] == "Medium"
    assert i["description"] == "<p>Return fails for DE & AT orders</p>"
    assert i["link"] == "https://jira.example.com/browse/GK-101"
    assert [c["body"] for c in i["comments"]] == [
        "<p>First look — SF & order check needed</p>", "<p>Reproduced</p>"]
    assert i["comments"][0]["created"] == "Mon, 30 Jun 2026 11:00:00 +0200"


def test_parse_empty_description_and_no_comments(xml_v1):
    i = {x["jira_key"]: x for x in parse_jira_xml(xml_v1)}["GK-102"]
    assert i["description"] is None
    assert i["comments"] == []
    assert i["solman_id"] is None          # no underscore in the summary
    # username fallback when the element text is just the JIRAUSER key
    assert i["jira_assignee"] == "JIRAUSER456"


# ---------------------------------------------------------------------------
# store + re-import rules
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "jira.db"
    database.init_db(p).close()
    db_jira.init_schema(p)
    return p


def test_reimport_refreshes_only_status_assignee_comments(db_path, tmp_path):
    v1 = tmp_path / "v1.xml"; v1.write_text(XML_V1, encoding="utf-8")
    v2 = tmp_path / "v2.xml"; v2.write_text(XML_V2, encoding="utf-8")

    conn = database.get_connection(db_path)
    try:
        r1 = db_jira.upsert_jira_issues(conn, parse_jira_xml(v1))
        assert (r1["inserted"], r1["updated"], r1["comments"]) == (2, 0, 2)
        first_seen = db_jira.get_jira_issue(conn, "GK-101")["first_seen"]

        r2 = db_jira.upsert_jira_issues(conn, parse_jira_xml(v2))
        assert (r2["inserted"], r2["updated"]) == (1, 1)

        i = db_jira.get_jira_issue(conn, "GK-101")
        # refreshed:
        assert i["jira_status"] == "Resolved"
        assert i["jira_assignee"] == "Someone Else"
        # kept from first import:
        assert i["summary"] == "SM1234_Blind Return DE & AT"
        assert i["solman_id"] == "SM1234"
        assert i["epic"] == "GK-EPIC-7"
        assert i["description"] == "<p>Return fails for DE & AT orders</p>"
        assert i["first_seen"] == first_seen
        # comments REPLACED, not appended:
        assert [c["body"] for c in db_jira.list_jira_comments(conn, "GK-101")] \
            == ["<p>Fixed in build 42</p>"]
        # untouched issue keeps everything:
        assert db_jira.get_jira_issue(conn, "GK-102")["jira_status"] == "In Progress"
        assert db_jira.get_jira_issue(conn, "GK-103")["solman_id"] == "SM7777"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# folder rule + end-to-end
# ---------------------------------------------------------------------------

def test_newest_xml_wins_regardless_of_name(tmp_path):
    old = tmp_path / "zzz_last_alphabetically.xml"
    old.write_text(XML_V1, encoding="utf-8")
    new = tmp_path / "aaa.xml"
    new.write_text(XML_V2, encoding="utf-8")
    past = time.time() - 3600
    import os
    os.utime(old, (past, past))
    assert newest_xml(tmp_path) == new


def test_run_jira_import_end_to_end(db_path, tmp_path):
    folder = tmp_path / "gk"
    folder.mkdir()
    (folder / "export.xml").write_text(XML_V1, encoding="utf-8")
    cfg = {"database_path": str(db_path), "jira_gatekeeper_folder": str(folder)}

    result = run_jira_import(cfg, "gatekeeper")
    assert result["ok"], result["error"]
    assert result["parsed"] == 2 and result["inserted"] == 2
    conn = database.get_connection(db_path)
    try:
        assert len(db_jira.list_jira_issues(conn)) == 2
    finally:
        conn.close()


def test_gatekeeper_import_accepts_only_my_tickets(db_path, tmp_path):
    """[USER 2026-07-12] gatekeeper sense check: only tickets assigned to me
    enter the store; the export may be as broad as convenient."""
    folder = tmp_path / "gk"
    folder.mkdir()
    (folder / "export.xml").write_text(XML_V1, encoding="utf-8")
    cfg = {"database_path": str(db_path), "jira_gatekeeper_folder": str(folder),
           "jira_gatekeeper_assignee": "Marina"}

    r = run_jira_import(cfg, "gatekeeper")
    assert r["ok"]
    assert r["parsed"] == 2 and r["relevant"] == 1
    assert r["skipped_other_assignee"] == 1        # GK-102 belongs to JIRAUSER456

    conn = database.get_connection(db_path)
    try:
        gk = db_jira.list_jira_issues(conn, seen_in="gatekeeper")
        assert [i["jira_key"] for i in gk] == ["GK-101"]
        assert db_jira.list_jira_issues(conn) == gk   # nothing else imported
    finally:
        conn.close()


def test_ecom_import_accepts_only_board_tickets(db_path, tmp_path):
    """[USER 2026-07-12] ECOM filter: only tickets whose key is on the ECOM
    board (ecom.jira_id) enter the store — 200 irrelevant tickets in the
    export cost nothing."""
    from app.db import ecom as db_ecom
    db_ecom.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        with conn:
            conn.execute("INSERT INTO ecom (match_key, jira_id, created_at,"
                         " first_seen, last_seen) VALUES ('k', 'gk-102', 'n', 'd', 'd')"
                         if False else
                         "INSERT INTO ecom (match_key, jira_id, first_seen, last_seen)"
                         " VALUES ('k', 'GK-102', 'd', 'd')")
    finally:
        conn.close()

    folder = tmp_path / "ecom"
    folder.mkdir()
    (folder / "export.xml").write_text(XML_V1, encoding="utf-8")
    cfg = {"database_path": str(db_path), "jira_ecom_folder": str(folder)}

    r = run_jira_import(cfg, "ecom")
    assert r["ok"]
    assert r["parsed"] == 2 and r["relevant"] == 1
    assert r["skipped_not_on_board"] == 1          # GK-101 is not on the board

    conn = database.get_connection(db_path)
    try:
        assert [i["jira_key"] for i in db_jira.list_jira_issues(conn, seen_in="ecom")] \
            == ["GK-102"]
        # the gatekeeper view stays untouched by an ecom import
        assert db_jira.list_jira_issues(conn, seen_in="gatekeeper") == []
    finally:
        conn.close()


def test_run_jira_import_clear_errors(db_path, tmp_path):
    cfg = {"database_path": str(db_path),
           "jira_gatekeeper_folder": str(tmp_path / "missing")}
    assert "folder not found" in run_jira_import(cfg, "gatekeeper")["error"]

    empty = tmp_path / "empty"; empty.mkdir()
    cfg["jira_gatekeeper_folder"] = str(empty)
    assert "no .xml file" in run_jira_import(cfg, "gatekeeper")["error"]

    assert "unknown source" in run_jira_import(cfg, "nope")["error"]
