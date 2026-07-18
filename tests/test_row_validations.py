"""Row validations (2026-07-18) — registry in app/row_validations.py.

What must hold:
- rule: status "conditionally passed" (any casing) with a blank
  "reason for pass with reservation" flags the row; filled reason or any
  other status does not; rule runs on retail AND ecom, not elsewhere
- validate_rows keys findings by the given id field, clean rows omitted
- boards render the red ⚠ button ONLY for flagged rows + the shared
  dialog (_row_validation_dialog.html) exactly once
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import jira as db_jira
from app.row_validations import validate_row, validate_rows
import app.web_retail as web_retail
import app.web_ecom as web_ecom
from app.web import app


def test_conditional_pass_needs_reason():
    bad = {"status": "conditionally passed", "reason_for_pass_with_reservation": ""}
    assert len(validate_row("retail", bad)) == 1
    assert len(validate_row("ecom", bad)) == 1
    assert validate_row("spillover", bad) == []          # rule not registered there

    assert validate_row("retail", {"status": "Conditionally Passed",
                                   "reason_for_pass_with_reservation": None})  # casing
    assert validate_row("retail", {"status": "conditionally passed",
                                   "reason_for_pass_with_reservation": "known tax gap"}) == []
    assert validate_row("retail", {"status": "Passed",
                                   "reason_for_pass_with_reservation": ""}) == []


def test_validate_rows_keys_by_id_and_omits_clean():
    rows = [
        {"retail_id": 1, "status": "conditionally passed",
         "reason_for_pass_with_reservation": ""},
        {"retail_id": 2, "status": "Passed",
         "reason_for_pass_with_reservation": ""},
    ]
    result = validate_rows("retail", rows, "retail_id")
    assert list(result) == [1] and len(result[1]) == 1


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "rowval.db"
    database.init_db(db_path).close()
    db_ecom.init_schema(db_path)
    db_jira.init_schema(db_path)
    monkeypatch.setattr(web_retail, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_ecom, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def test_retail_board_flags_only_violating_row(client):
    conn = database.get_connection(client.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO retail (match_key, test_case_id, country, status,"
                " reason_for_pass_with_reservation) VALUES"
                " ('a|de', 'RET0001', 'Germany', 'conditionally passed', ''),"
                " ('b|de', 'RET0002', 'Germany', 'conditionally passed', 'known gap'),"
                " ('c|de', 'RET0003', 'Germany', 'Passed', '')")
    finally:
        conn.close()

    html = client.get("/retail").get_data(as_text=True)
    assert html.count("js-open-val") >= 1
    assert html.count("data-val-name") == 1              # exactly one flagged row
    assert 'data-val-name="RET0001 / Germany"' in html
    assert html.count('id="dlg-rowval"') == 1
    assert "reservation&#34; is empty" in html or "reservation\\" in html or "is empty" in html


def test_ecom_board_flags_only_violating_row(client):
    conn = database.get_connection(client.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO ecom (match_key, jira_id, status, test_case_id, country,"
                " reason_for_pass_with_reservation, first_seen, last_seen) VALUES"
                " ('s4ecom-1', 'S4ECOM-1', 'conditionally passed', 'TC1', 'DE', '', 'd', 'd'),"
                " ('s4ecom-2', 'S4ECOM-2', 'Passed', 'TC2', 'DE', '', 'd', 'd')")
    finally:
        conn.close()

    html = client.get("/ecom/").get_data(as_text=True)
    assert html.count("data-val-name") == 1
    assert 'data-val-name="S4ECOM-1 — TC1 / DE"' in html
    assert html.count('id="dlg-rowval"') == 1
