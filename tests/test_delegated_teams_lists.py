"""The two Teams-paste list reports (2026-09-02 [USER]):
- /delegated/dtc-o2c-blockers — open blockers with team DTC O2C, each with
  the test cases it blocks (Jira id + latest-comment orders, NO names)
- /delegated/settlement — tickets in "Settlement file to be created"
Both: Copy-for-Teams button on screen only, dated download, Email Reports
attachment (and NOT on the Export Reports card)."""
from app import web_delegated
from app.db import blockers as db_blockers
from app.emailer import REPORT_CHOICES, gather_attachments
from tests.test_delegated_web import XML, _upload, client  # noqa: F401 (fixture)


def _blocker(conn, name, team, key=None, link_to=()):
    b = db_blockers.create_blocker(conn, "defect", name, key, team=team)
    for jira_key in link_to:
        db_blockers.link_blocker(conn, b["blocker_id"], jira_key)
    return b


def test_dtc_blockers_lists_open_dtc_o2c_blockers_with_their_tickets(client):
    _upload(client)
    conn = web_delegated._get_conn()
    try:
        _blocker(conn, "Pricing wrong on returns", "DTC O2C", "S4DEF-9001",
                 link_to=["S4ECOM-2001", "S4ECOM-2002"])
        _blocker(conn, "Lonely clarification", "dtc  o2c")      # no ticket, odd spelling
        _blocker(conn, "Kibana index missing", "Kibana", "S4DEF-9002",
                 link_to=["S4ECOM-2001"])                       # other team
        closed = _blocker(conn, "Already fixed", "DTC O2C", "S4DEF-9003",
                          link_to=["S4ECOM-2001"])
        db_blockers.set_blocker_closed(conn, closed["blocker_id"], True)
        ctx = web_delegated.dtc_blockers_context(conn)
    finally:
        conn.close()
    # list_blockers order: defects → tasks → clarifications, then name
    names = [b["name"] for b in ctx["blocks"]]
    assert names == ["Lonely clarification", "Pricing wrong on returns"]
    pricing = ctx["blocks"][1]
    assert pricing["label"] == "S4DEF-9001"
    assert [t["jira_key"] for t in pricing["tickets"]] == ["S4ECOM-2001", "S4ECOM-2002"]
    assert pricing["tickets"][0]["orders"] == "Return Order: 6000084252"   # latest comment
    assert pricing["tickets"][0]["link"] == "https://jira.example.com/browse/S4ECOM-2001"
    assert pricing["tickets"][1]["orders"] == ""                           # no comment
    assert ctx["blocks"][0]["tickets"] == []
    assert ctx["total_tickets"] == 2

    html = client.get("/delegated/dtc-o2c-blockers").get_data(as_text=True)
    paste = html.split('id="teams-copy"')[1].split("</div>")[0]
    assert "S4DEF-9001 · Pricing wrong on returns" in paste
    assert 'href="https://jira.example.com/browse/S4ECOM-2001">S4ECOM-2001</a> — Return Order: 6000084252' in paste
    assert "<li>S4ECOM-2002 — no order number yet" in paste       # no <link> in the export → plain id
    assert "no test case attached" in paste
    assert "Kibana index missing" not in html and "Already fixed" not in html
    assert "SM2001_Blocked settlement case" not in html            # no test case NAMES [USER]
    assert "Copy for Teams" in html and "teamsCopy" in html


def test_settlement_list_is_the_in_verification_bucket_without_backlog(client):
    from app.db import delegated as db_delegated
    xml = (XML.replace(">In Progress<", ">In Verification<")     # S4ECOM-2002
              .replace(">Accepted<", ">In Verification<"))       # S4ECOM-2003
    _upload(client, xml)
    conn = web_delegated._get_conn()
    try:
        db_delegated.set_delegated_backlog(conn, "S4ECOM-2003", True)   # parked → out
        ctx = web_delegated.settlement_context(conn)
    finally:
        conn.close()
    assert [t["jira_key"] for t in ctx["tickets"]] == ["S4ECOM-2002"]

    html = client.get("/delegated/settlement").get_data(as_text=True)
    assert "Settlement file to be created (" in html
    assert "S4ECOM-2002" in html and "S4ECOM-2003" not in html
    assert "no order number yet" in html


def test_downloads_are_dated_attachments_without_the_copy_button(client):
    _upload(client)
    for path, stem, title in (
            ("/delegated/dtc-o2c-blockers/download", "delegated_dtc_o2c_blockers", "team DTC O2C"),
            ("/delegated/settlement/download", "delegated_settlement", "Waiting for settlement file")):
        resp = client.get(path)
        assert resp.status_code == 200
        assert f'attachment; filename="{stem}_' in resp.headers["Content-Disposition"]
        html = resp.get_data(as_text=True)
        assert title in html
        assert "teamsCopy" not in html and "Copy for Teams" not in html


def test_both_lists_are_email_report_choices_only(client, monkeypatch):
    keys = [k for k, _ in REPORT_CHOICES]
    assert "delegated_dtc_blockers" in keys and "delegated_settlement" in keys
    _upload(client)
    from app import web_core
    conn = web_delegated._get_conn()
    try:
        out = gather_attachments(conn, {}, web_core.app,
                                 ["delegated_dtc_blockers", "delegated_settlement"],
                                 "2026-09-02")
    finally:
        conn.close()
    names = [n for n, _html in out]
    assert names == ["delegated_dtc_o2c_blockers_2026-09-02.html",
                     "delegated_settlement_2026-09-02.html"]
    assert "team DTC O2C" in out[0][1]
    # NOT on the Export Reports card [USER: "email reports only"]
    from app import report_exporter
    src = open(report_exporter.__file__, encoding="utf-8").read()
    assert "dtc_blockers_context" not in src and "settlement_context" not in src


def test_board_header_links_to_both_lists(client):
    _upload(client)
    html = client.get("/delegated/").get_data(as_text=True)
    assert "/delegated/dtc-o2c-blockers" in html
    assert "/delegated/settlement" in html
