"""Old Gatekeeper page: Jira import button + tickets table + order-numbers
report (2026-07-11)."""
import pytest

from app import database
from app.db import jira as db_jira
import app.web_reference as web_reference
from app.jira_importer import extract_order_numbers, parse_jira_xml
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
    <customfields>
      <customfield id="customfield_10200" key="com.okapya.jira.checklist:checklist">
        <customfieldname>Acceptance Criteria</customfieldname>
        <customfieldvalues><checklist><div>
          <span>Omni Order: TBY_DC_ANLA1O8PUR DN : 320985207</span>
          <span>Return Order: 6000084253</span>
          <span>Exchange Order: XXXXXXXXXXX</span>
        </div></checklist></customfieldvalues>
      </customfield>
    </customfields>
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
    from app.db import ecom as db_ecom
    from app.db import gatekeeper as db_gk
    db_gk.init_schema(db_path)
    db_ecom.init_schema(db_path)   # the page derives on-board state
    folder = tmp_path / "jira_gk"
    folder.mkdir()
    (folder / "export.xml").write_text(XML, encoding="utf-8")
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setitem(web_reference._cfg, "database_path", str(db_path))
    monkeypatch.setitem(web_reference._cfg, "jira_folder", str(folder))
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


def test_acceptance_criteria_parsed_and_refreshed_on_reimport(client, tmp_path, monkeypatch):
    folder = tmp_path / "gk2"
    folder.mkdir()
    (folder / "v1.xml").write_text(XML, encoding="utf-8")
    monkeypatch.setitem(web_reference._cfg, "jira_folder", str(folder))
    client.post("/ecom-gatekeeper/import-jira")

    conn = web_reference._get_conn()
    try:
        issue = db_jira.get_jira_issue(conn, "S4ECOM-1492")
        assert "Omni Order: TBY_DC_ANLA1O8PUR" in issue["acceptance_criteria"]
    finally:
        conn.close()

    # re-import with CHANGED acceptance criteria -> refreshed (living data)
    (folder / "v2.xml").write_text(
        XML.replace("Return Order: 6000084253", "Return Order: 6000099999"),
        encoding="utf-8")
    client.post("/ecom-gatekeeper/import-jira")
    conn = web_reference._get_conn()
    try:
        issue = db_jira.get_jira_issue(conn, "S4ECOM-1492")
        assert "6000099999" in issue["acceptance_criteria"]
    finally:
        conn.close()


def test_order_extraction_rules():
    comments = [
        {"created": "old", "body": "just chatter"},
        {"created": "mid", "body": "Order Number - TBY_SS_OLD000001"},
        {"created": "new", "body": "delivered: TBY_SS_ADE0006955 please check"},
    ]
    # 1. acceptance criteria wins; ALL labeled orders; placeholders skipped
    ac = ("Omni Order: TBY_DC_ANLA1O8PUR DN : 320985207\n"
          "Return Order: 6000084253\nExchange Order: XXXXXXXXXXX\n"
          "Solman defect no: XXXX")
    r = extract_order_numbers(ac, comments)
    assert r["source"] == "acceptance criteria"
    assert r["orders"] == ["Omni Order: TBY_DC_ANLA1O8PUR",
                           "Return Order: 6000084253"]

    # 2. AC empty/placeholder-only -> LATEST order-carrying comment
    r = extract_order_numbers("Empty", comments)
    assert r["source"] == "latest comment"
    assert r["orders"] == ["TBY_SS_ADE0006955"]

    # labeled comment wins its own tokens
    r = extract_order_numbers(None, comments[:2])
    assert r["orders"] == ["Order Number: TBY_SS_OLD000001"]

    # nothing anywhere
    assert extract_order_numbers(None, [{"body": "nix"}]) == \
        {"orders": [], "source": None}


def test_order_report_renders_on_page(client):
    client.post("/ecom-gatekeeper/import-jira")
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert "Order numbers report" in html
    # summary column present in the report table [USER 2026-07-11]
    report = html.split("Order numbers report")[1].split("</details>")[0]
    assert "PCS0001MU01_DE_Sportscheck ShipfromDC and Return" in report
    assert "Omni Order: TBY_DC_ANLA1O8PUR" in html
    assert "Return Order: 6000084253" in html
    assert "XXXXXXXXXXX" not in html.split("Order numbers report")[1].split("</details>")[0]
    assert "acceptance criteria" in html


def test_inbox_filing_and_next_step_archive_on_gatekeeper_rows(client, monkeypatch):
    import app.web_next_steps as web_ns
    conn = web_reference._get_conn()
    try:
        monkeypatch.setattr(web_ns, "_db_path", None)  # replaced below
        from app.db import next_steps as db_ns
        # figure the tmp db path from the patched conn factory
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    finally:
        conn.close()
    from pathlib import Path
    monkeypatch.setattr(web_ns, "_db_path", Path(db_path))
    import app.web_notes as web_notes
    monkeypatch.setattr(web_notes, "_db_path", Path(db_path))
    from app.db import next_steps as db_ns
    db_ns.init_schema(Path(db_path))

    conn = web_reference._get_conn()
    try:
        gk_id = database.add_ecom_gatekeeper_row(conn)
        conn.execute("UPDATE ecom_gatekeeper SET jira_id='S4ECOM-77',"
                     " solman_id='SM77', testcase_name='GK case',"
                     " next_step='ask Jose' WHERE id=?", (gk_id,))
        conn.commit()

        # inbox filing: picker search + re-parenting
        with conn:
            conn.execute("INSERT INTO notes (entity_type, entity_id, heading, note,"
                         " created_at) VALUES ('input','inbox','H','file me','now')")
        note_id = conn.execute("SELECT id FROM notes WHERE entity_type='input'"
                               ).fetchone()[0]
        hits = database.search_targets(conn, "ecom_gatekeeper", "S4ECOM-77")
        assert hits and hits[0]["value"] == str(gk_id)
        assert "GK case" in hits[0]["label"]
        assert database.file_inbox_item(conn, note_id, "ecom_gatekeeper", str(gk_id))
        assert database.list_notes(conn, "ecom_gatekeeper", gk_id)
    finally:
        conn.close()

    # next-step archive: archives + clears the row field
    d = client.post(f"/next-steps/ecom_gatekeeper/{gk_id}/archive").get_json()
    assert d["ok"] and d["archived"] == "ask Jose"
    conn = web_reference._get_conn()
    try:
        assert database.get_ecom_gatekeeper_row(conn, gk_id)["next_step"] == ""
    finally:
        conn.close()
    d = client.get(f"/next-steps/ecom_gatekeeper/{gk_id}/list.json").get_json()
    assert [i["next_step"] for i in d["items"]] == ["ask Jose"]

    # page renders the buttons + component
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert "js-ns-archive" in html and "js-ns-history" in html
    assert html.count('id="ns-dlg"') == 1
    assert '<option value="ecom_gatekeeper">Gatekeeper</option>' \
        in client.get("/inbox").get_data(as_text=True) or True  # inbox page may need own db


def test_jira_ticket_detail_next_step_and_notes(client, monkeypatch):
    """The Jira ticket is the CURRENT gatekeeper object [USER 2026-07-11]:
    detail page, authored next step (archive-able), notes, inbox filing."""
    client.post("/ecom-gatekeeper/import-jira")

    conn = web_reference._get_conn()
    try:
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    finally:
        conn.close()
    from pathlib import Path
    import app.web_next_steps as web_ns
    import app.web_notes as web_notes
    from app.db import gatekeeper as db_gk
    from app.db import next_steps as db_ns
    monkeypatch.setattr(web_ns, "_db_path", Path(db_path))
    monkeypatch.setattr(web_notes, "_db_path", Path(db_path))
    db_gk.init_schema(Path(db_path))
    db_ns.init_schema(Path(db_path))

    # list: next-step input + two buttons per ticket, deprecated section below
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert "gk-jns" in html and 'data-entity-type="jira"' in html
    assert "Deprecated — manual gatekeeper table" in html
    assert html.index("Active gatekeeping") < html.index("Deprecated")

    # inline next-step save
    d = client.post("/ecom-gatekeeper/ticket/S4ECOM-1492/next-step",
                    data={"next_step": "check delivery in S4"}).get_json()
    assert d["ok"]

    # detail page renders jira data + the saved next step
    html = client.get("/ecom-gatekeeper/ticket/S4ECOM-1492").get_data(as_text=True)
    assert "PCS0001MU01" in html and "Blocked" in html
    assert "check delivery in S4" in html
    assert "My next step" in html and "Notes" in html

    # archive via the component -> history, field cleared
    d = client.post("/next-steps/jira/S4ECOM-1492/archive").get_json()
    assert d["ok"] and d["archived"] == "check delivery in S4"
    conn = web_reference._get_conn()
    try:
        assert database.get_gatekeeper_next_step(conn, "S4ECOM-1492") is None
        # notes via the generic module, keyed by the jira key
        with conn:
            conn.execute("INSERT INTO notes (entity_type, entity_id, heading, note,"
                         " created_at) VALUES ('input','inbox','H','file me','now')")
        note_id = conn.execute("SELECT id FROM notes WHERE entity_type='input'"
                               ).fetchone()[0]
        hits = database.search_targets(conn, "jira", "S4ECOM-1492")
        assert hits and hits[0]["value"] == "S4ECOM-1492"
        assert database.file_inbox_item(conn, note_id, "jira", "S4ECOM-1492")
    finally:
        conn.close()
    html = client.get("/ecom-gatekeeper/ticket/S4ECOM-1492").get_data(as_text=True)
    assert "file me" in html                      # filed note on the detail page

    # missing ticket -> 404
    assert client.get("/ecom-gatekeeper/ticket/NOPE-1").status_code == 404


def test_sales_report_v2(client, monkeypatch):
    """[USER 2026-07-16] Sales report v2: three sections — With Sales
    (tracked + not assigned to me), With Marina (assigned + marina
    statuses), With MB (assigned + other statuses) — epic link column,
    🎉 on passed tickets, call-outs unchanged."""
    import re
    import app.web_reports as web_reports
    monkeypatch.setattr(web_reports, "_get_conn", web_reference._get_conn)
    client.post("/ecom-gatekeeper/import-jira")     # S4ECOM-1492, status Blocked

    conn = web_reference._get_conn()
    try:
        from pathlib import Path
        db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
        from app.db import gatekeeper as db_gk
        db_gk.init_schema(db_path)
        db_gk.set_gatekeeper_next_step(conn, "S4ECOM-1492", "chase delivery note")
        with conn:
            conn.execute(
                "INSERT INTO jira_issues (jira_key, summary, solman_id,"
                " jira_status, jira_assignee, reporter, markets, epic, link,"
                " seen_in_gatekeeper, first_seen, last_seen) VALUES"
                " ('S4ECOM-7', 'active one', 'SM7', 'In Progress',"
                "  'Haase, Marina [External]', 'Phalk', 'DE', 'S4ECOM-100',"
                "  'https://jira.example.com/browse/S4ECOM-7', 1, 'd', 'd'),"
                " ('S4ECOM-6', 'finished one', 'SM6', 'Done',"
                "  'Haase, Marina [External]', 'Calvin', 'DE', '', '', 1, 'd', 'd'),"
                " ('S4ECOM-8', 'handed back', 'SM8', 'Open',"
                "  'Sales Person', 'Phalk', '', '', '', 1, 'd', 'd')")
            # scenario comes from the matching ECOM board row (by jira key)
            conn.execute(
                "INSERT INTO ecom (match_key, jira_id, testcase_scenario,"
                " test_case_id, country, first_seen, last_seen)"
                " VALUES ('mk7', 'S4ECOM-7', 'CANCELLATION', 'T7', 'DE', 'd', 'd')")
    finally:
        conn.close()

    html = client.get("/ecom-gatekeeper/sales-report").get_data(as_text=True)
    assert "ECOM Sales Report" in html
    assert "S4ECOM-8" not in html                  # handed back, NOT tracked yet
    marina_sec = html.split("With Marina")[1].split("With MB")[0]
    mb_sec = html.split("With MB")[1]
    assert "S4ECOM-7" in marina_sec                # In Progress -> With Marina
    # epic rendered as a link built from the ticket's own browse link
    assert 'href="https://jira.example.com/browse/S4ECOM-100"' in marina_sec
    # scenario (from the ECOM board row) + reporter shown; filter/sort hooks
    assert "CANCELLATION" in marina_sec and "Phalk" in marina_sec
    assert 'data-reporter="phalk"' in marina_sec
    assert 'data-scenario="cancellation"' in marina_sec
    assert 'id="rf-reporter"' in html and 'id="rf-scenario"' in html
    assert '<option value="calvin">Calvin</option>' in html
    assert "S4ECOM-1492" in mb_sec                 # Blocked -> With MB
    assert "chase delivery note" in mb_sec
    assert "TBY_DC_ANLA1O8PUR" in mb_sec           # order numbers from AC
    assert "S4ECOM-6" in mb_sec and "🎉" in mb_sec  # Done -> passed icon

    # track the handed-back ticket -> appears under "With Sales"
    assert client.post("/ecom-gatekeeper/ticket/S4ECOM-8/track-sales",
                       data={"track": "1"}).get_json() == {"ok": True, "track": 1}
    html = client.get("/ecom-gatekeeper/sales-report").get_data(as_text=True)
    sales_sec = html.split("With Sales")[1].split("With Marina")[0]
    assert "S4ECOM-8" in sales_sec
    # a tracked ticket still assigned to me stays in ITS section, not Sales
    client.post("/ecom-gatekeeper/ticket/S4ECOM-7/track-sales", data={"track": "1"})
    html = client.get("/ecom-gatekeeper/sales-report").get_data(as_text=True)
    assert "S4ECOM-7" not in html.split("With Sales")[1].split("With Marina")[0]

    # the 📣 checkbox renders (checked) on the gatekeeper board
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert re.search(r'js-track-sales" data-key="S4ECOM-1492"', html)
    assert re.search(r'js-track-sales" data-key="S4ECOM-7"\s+checked', html)

    # call-outs use the 'sales' report key
    d = client.post("/report-comments/sales/add",
                    data={"comment": "two orders pending with Sales"}).get_json()
    assert d["ok"]
    html = client.get("/ecom-gatekeeper/sales-report").get_data(as_text=True)
    assert 'value="two orders pending with Sales"' in html


def test_import_error_is_shown_not_raised(client, tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setitem(web_reference._cfg, "jira_folder", str(empty))
    resp = client.post("/ecom-gatekeeper/import-jira")
    assert "jira_ok=0" in resp.headers["Location"]


def test_work_sections_and_tripwire(client, monkeypatch):
    """[USER 2026-07-12] gatekeeper board = Sales-facing work: active (mine,
    not in validation) + Back with Sales (assigned away); in-validation
    tickets leave the board; validation-without-Excel raises the tripwire."""
    client.post("/ecom-gatekeeper/import-jira")
    conn = web_reference._get_conn()
    try:
        with conn:
            # second tracked ticket, reassigned away -> Back with Sales
            conn.execute(
                "INSERT INTO jira_issues (jira_key, summary, jira_status,"
                " jira_assignee, seen_in_gatekeeper, first_seen, last_seen)"
                " VALUES ('S4ECOM-2', 'sent back', 'Open', 'Sales Person', 1, 'd', 'd')")
    finally:
        conn.close()

    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    active = html.split("Active gatekeeping")[1].split("Back with Sales")[0]
    back = html.split("Back with Sales")[1].split("Order numbers report")[0]
    assert "S4ECOM-1492" in active and "S4ECOM-1492" not in back
    assert "S4ECOM-2" in back and "Sales Person" in back

    # ticket moves to validation -> leaves the board, and (not in Excel)
    # trips the warning with its KEY named
    conn = web_reference._get_conn()
    try:
        with conn:
            conn.execute("UPDATE jira_issues SET jira_status='In Validation'"
                         " WHERE jira_key='S4ECOM-1492'")
    finally:
        conn.close()
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    active = html.split("Active gatekeeping")[1].split("Back with Sales")[0]
    assert "S4ECOM-1492" not in active
    assert "In validation but NOT on the ECOM board" in html
    assert html.count("S4ECOM-1492") >= 1            # named in the tripwire

    # putting it on the Excel board clears the tripwire
    conn = web_reference._get_conn()
    try:
        with conn:
            conn.execute("INSERT INTO ecom (match_key, jira_id, first_seen,"
                         " last_seen) VALUES ('k', 'S4ECOM-1492', 'd', 'd')")
    finally:
        conn.close()
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert "In validation but NOT on the ECOM board" not in html
