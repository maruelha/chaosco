"""Global search — the 2026-08-28 sources: Sustainphase Issues (incl.
incident number + title since 2026-09-03), Smoke scenarios (name + ASPEN ticket) and
the dedicated Delegated Testing group."""
import pytest

from app import database
from app.db import delegated as db_delegated
from app.db import ecom as db_ecom
from app.db import jira as db_jira
from app.db import smoke as db_smoke
from app.db import sustain_issues as db_si
import app.web_search as web_search
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "search2.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_ecom.init_schema(db_path)
    db_delegated.init_schema(db_path)
    db_smoke.init_schema(db_path)
    db_si.init_schema(db_path)
    monkeypatch.setattr(web_search, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        db_si.upsert_incidents(conn, [{
            "incident_number": "INC001", "title": "Invoice missing",
            "status": "Open"}])
        db_smoke.replace_all(conn, [{
            "row_id": 100, "ws": "eCOM", "package": "Click & Collect",
            "scenario": "Fulfill Click and Collect order",
            "steps": [{"row_id": 101, "step": "x",
                       "aspen_ticket": "ASPEN-555"}]}])
        with conn:
            conn.execute(
                "INSERT INTO jira_issues (jira_key, summary,"
                " jira_status, seen_in_delegated, first_seen, last_seen)"
                " VALUES ('S4DTC-42', 'Create test orders FR', 'Blocked',"
                " 1, 'd', 'd')")
    finally:
        conn.close()
    return app.test_client()


def _groups(client, q):
    data = client.get(f"/search/orders.json?q={q}").get_json()
    assert data["ok"]
    return {g["group"]: g["hits"] for g in data["groups"]}


def test_sustain_incident_found_by_number_and_title(client):
    by_no = _groups(client, "inc00")["Sustainphase Issues"]
    assert by_no[0]["label"].startswith("INC001")
    assert "/sustain-issues/" in by_no[0]["url"]
    by_title = _groups(client, "invoice missing")["Sustainphase Issues"]
    assert by_title[0]["label"] == "INC001 — Invoice missing"


def test_smoke_scenarios_found_by_name_and_aspen_ticket(client):
    by_name = _groups(client, "click and collect")["Smoke scenarios"]
    assert by_name[0]["label"] == "Fulfill Click and Collect order"
    assert by_name[0]["url"].endswith("/smoke/ecom")
    by_ticket = _groups(client, "ASPEN-555")["Smoke scenarios"]
    assert by_ticket[0]["match"] == "ASPEN ASPEN-555"


def test_delegated_group_links_to_delegated_detail(client):
    hits = _groups(client, "test orders")["Delegated Testing"]
    assert hits[0]["label"] == "S4DTC-42 — Create test orders FR"
    assert "/delegated/ticket/S4DTC-42" in hits[0]["url"]
    # also findable by key
    assert "Delegated Testing" in _groups(client, "S4DTC-42")
