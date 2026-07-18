"""Reporter filters + per-reporter Sales report + validation (2026-07-18).

ECOM tickets are raised by a fixed expected reporter set (config
ecom_reporters, default Phalk + Calvin; Jira carries "Lastname,
Firstname" — matched by short-name substring, case-insensitive).
What must hold:
- short_reporter matching contract
- /ecom?reporter=X keeps only rows whose ticket reporter matches (rows
  without Jira data drop out under a filter)
- /ecom-gatekeeper?reporter=X filters the Jira working sections
- /ecom-gatekeeper/sales-report?reporter=X serves ONLY that reporter's
  tickets (server-side — print/download follow); title carries the name
- ecom rows whose ticket has an UNEXPECTED reporter get a ⚠ data-check
  finding; expected or missing reporters do not
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import jira as db_jira
from app.reporters import short_reporter
from app.row_validations import validate_row
import app.web_ecom as web_ecom
import app.web_reference as web_reference
from app.web import app


def test_short_reporter_matching():
    expected = ["Phalk", "Calvin"]
    assert short_reporter("Jindal, Phalk", expected) == "Phalk"
    assert short_reporter("calvin somebody", expected) == "Calvin"
    assert short_reporter("Doe, John", expected) is None
    assert short_reporter("", expected) is None
    assert short_reporter(None, expected) is None


def test_unexpected_reporter_rule():
    base = {"status": "Passed", "reason_for_pass_with_reservation": "",
            "expected_reporters": ["Phalk", "Calvin"]}
    assert validate_row("ecom", dict(base, reporter="Doe, John"))
    assert validate_row("ecom", dict(base, reporter="Jindal, Phalk")) == []
    assert validate_row("ecom", dict(base, reporter=None)) == []      # no ticket yet
    assert validate_row("retail", dict(base, reporter="Doe, John")) == []


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "reporters.db"
    database.init_db(db_path).close()
    db_ecom.init_schema(db_path)
    db_jira.init_schema(db_path)
    from app.db import gatekeeper as db_gk
    db_gk.init_schema(db_path)
    monkeypatch.setattr(web_ecom, "_db_path", db_path)
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    conn = database.get_connection(db_path)
    try:
        db_jira.upsert_jira_issues(conn, [
            {"jira_key": "S4ECOM-1", "summary": "A", "reporter": "Jindal, Phalk",
             "jira_assignee": "Haase, Marina", "jira_status": "Open", "comments": []},
            {"jira_key": "S4ECOM-2", "summary": "B", "reporter": "Smith, Calvin",
             "jira_assignee": "Haase, Marina", "jira_status": "Open", "comments": []},
            {"jira_key": "S4ECOM-3", "summary": "C", "reporter": "Doe, John",
             "jira_assignee": "Haase, Marina", "jira_status": "Open", "comments": []},
        ], seen_in="gatekeeper")
        with conn:
            conn.execute(
                "INSERT INTO ecom (match_key, jira_id, status, test_case_id, country,"
                " first_seen, last_seen) VALUES"
                " ('s4ecom-1', 'S4ECOM-1', 'Passed', 'TC1', 'DE', 'd', 'd'),"
                " ('s4ecom-2', 'S4ECOM-2', 'Passed', 'TC2', 'DE', 'd', 'd'),"
                " ('s4ecom-3', 'S4ECOM-3', 'Passed', 'TC3', 'DE', 'd', 'd'),"
                " ('s4ecom-9', 'S4ECOM-9', 'Passed', 'TC9', 'DE', 'd', 'd')")
    finally:
        conn.close()
    return app.test_client()


def test_ecom_board_reporter_filter(client):
    html = client.get("/ecom/").get_data(as_text=True)
    assert "TC1" in html and "TC2" in html and "TC9" in html

    html = client.get("/ecom/?reporter=Phalk").get_data(as_text=True)
    assert "TC1" in html
    assert "TC2" not in html and "TC3" not in html and "TC9" not in html

    html = client.get("/ecom/?reporter=Calvin").get_data(as_text=True)
    assert "TC2" in html and "TC1" not in html


def test_ecom_unexpected_reporter_gets_data_check(client):
    html = client.get("/ecom/").get_data(as_text=True)
    assert html.count("data-val-name") == 1                 # only the Doe row
    assert 'data-val-name="S4ECOM-3 — TC3 / DE"' in html
    assert "not one of the expected" in html


def test_gatekeeper_page_reporter_filter(client):
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert "S4ECOM-1" in html and "S4ECOM-2" in html

    html = client.get("/ecom-gatekeeper?reporter=Phalk").get_data(as_text=True)
    assert "S4ECOM-1" in html
    assert "S4ECOM-2" not in html and "S4ECOM-3" not in html
    assert 'value="Phalk" selected' in html


def test_sales_report_per_reporter(client):
    html = client.get("/ecom-gatekeeper/sales-report").get_data(as_text=True)
    assert "S4ECOM-1" in html and "S4ECOM-2" in html

    html = client.get("/ecom-gatekeeper/sales-report?reporter=Phalk").get_data(as_text=True)
    assert "ECOM Sales Report — Phalk" in html
    assert "S4ECOM-1" in html
    assert "S4ECOM-2" not in html and "S4ECOM-3" not in html

    html = client.get("/ecom-gatekeeper/sales-report?reporter=Calvin").get_data(as_text=True)
    assert "S4ECOM-2" in html and "S4ECOM-1" not in html
