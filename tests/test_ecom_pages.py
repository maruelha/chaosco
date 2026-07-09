"""ECOM pages (day plan 05.07 step 8).

What must hold:
- list renders Excel rows + a ✓ chip only for rows present in the Jira store
- detail shows Jira details/comments when the store has the key, and the
  "no Jira data yet" hint when it doesn't
- annotation POST persists (keyed by jira id)
- pull-orders re-points old-gatekeeper order rows with the SAME jira id
- notes registry entry works (add a note via the generic route)
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import jira as db_jira
import app.web_ecom as web_ecom
import app.web_notes as web_notes
from app.web import app


def _ecom_row(jira="S4ECOM-1153", tc="CAN0001MU01", country="Germany (DE)"):
    return {"jira_id": jira, "status": "Not Ready", "assigned_to": "",
            "country": country, "testcase_scenario": "CANCELLATION",
            "test_case_id": tc, "testcase_name": f"{tc}_Web-STH-Zeropick",
            "description_change": "", "execution_started": "",
            "order_number": "", "old_order_numbers": "", "defect_id_ref": "",
            "s4_sales_order": "", "s4_billing_documents": "",
            "s4_journal_invoice_entry": "", "delivery_note": "",
            "reason_for_pass_with_reservation": "", "comment": "",
            "excel_row": 2, "_skip_reason": ""}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ecom_pages.db"
    database.init_db(db_path).close()
    db_ecom.init_schema(db_path)
    db_jira.init_schema(db_path)
    monkeypatch.setattr(web_ecom, "_db_path", db_path)
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        db_ecom.upsert_ecom_rows(conn, [_ecom_row()], "2026-07-09")
        row_id = db_ecom.get_ecom_rows(conn)[0]["ecom_id"]
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    c.row_id = row_id
    return c


def _seed_jira(client):
    conn = database.get_connection(client.db_path)
    try:
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": "S4ECOM-1153", "solman_id": "SM1",
            "summary": "SM1_Zeropick", "epic": "EP-1", "markets": "DE",
            "jira_status": "In Progress", "jira_assignee": "Dev X",
            "type": "Bug", "priority": "High",
            "description": "<p>jira description html</p>",
            "link": "https://jira.example.com/browse/S4ECOM-1153",
            "created": "c", "updated": "u",
            "comments": [{"created": "Mon", "body": "<p>first comment</p>"}],
        }])
    finally:
        conn.close()


def test_list_renders_with_jira_chip_only_when_in_store(client):
    html = client.get("/ecom/").get_data(as_text=True)
    assert "S4ECOM-1153" in html and "CAN0001MU01" in html
    assert "Jira details + comments available" not in html   # store empty

    _seed_jira(client)
    html = client.get("/ecom/").get_data(as_text=True)
    assert "Jira details + comments available" in html


def test_detail_shows_jira_section_or_hint(client):
    url = f"/ecom/{client.row_id}"
    html = client.get(url).get_data(as_text=True)
    assert "No Jira data for" in html

    _seed_jira(client)
    html = client.get(url).get_data(as_text=True)
    assert "jira description html" in html
    assert "first comment" in html
    assert "Open in Jira" in html
    assert "In Progress" in html and "Dev X" in html


def test_annotation_roundtrip_keyed_by_jira_id(client):
    resp = client.post(f"/ecom/{client.row_id}",
                       data={"next_step": "check with key user",
                             "comment_history": "seen once", "action_needed": "1"})
    assert resp.status_code == 302
    conn = database.get_connection(client.db_path)
    try:
        row = db_ecom.get_ecom_by_id(conn, client.row_id)
        assert row["next_step"] == "check with key user"
        assert row["action_needed"] == 1
        key = conn.execute("SELECT jira_id FROM ecom_annotations").fetchone()[0]
        assert key == "S4ECOM-1153"
    finally:
        conn.close()


def test_pull_orders_relinks_gatekeeper_rows_with_same_jira_id(client):
    conn = database.get_connection(client.db_path)
    try:
        gk_id = database.add_ecom_gatekeeper_row(conn)
        conn.execute("UPDATE ecom_gatekeeper SET jira_id='S4ECOM-1153' WHERE id=?",
                     (gk_id,))
        conn.commit()
        detail_id = database.add_order_detail(conn, "ecom_gatekeeper", str(gk_id))
        database.update_order_detail(conn, detail_id, "Sale", "4711", "", docs_in_s4=1)
        # a second gatekeeper row with a DIFFERENT jira id must stay untouched
        other_gk = database.add_ecom_gatekeeper_row(conn)
        conn.execute("UPDATE ecom_gatekeeper SET jira_id='S4ECOM-9999' WHERE id=?",
                     (other_gk,))
        conn.commit()
        database.add_order_detail(conn, "ecom_gatekeeper", str(other_gk))
    finally:
        conn.close()

    resp = client.post(f"/ecom/{client.row_id}/pull-orders")
    assert resp.status_code == 302 and "orders_moved=1" in resp.headers["Location"]

    conn = database.get_connection(client.db_path)
    try:
        moved = database.list_order_details(conn, "ecom", str(client.row_id))
        assert [d["order_number"] for d in moved] == ["4711"]
        assert database.list_order_details(conn, "ecom_gatekeeper", str(other_gk))
        assert database.list_order_details(conn, "ecom_gatekeeper", str(gk_id)) == []
    finally:
        conn.close()


def test_notes_registry_entry_roundtrip(client):
    resp = client.post(f"/n/ecom/{client.row_id}/add",
                       data={"note": "ecom note works"})
    assert resp.status_code == 302
    html = client.get(f"/ecom/{client.row_id}").get_data(as_text=True)
    assert "ecom note works" in html
