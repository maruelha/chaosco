"""Shared order details per Jira ticket (2026-07-16).

The Gatekeeper Check and the ECOM board read the SAME order rows, addressed
('jira', jira_key) — no copy, no handover step. What must hold:
- migrate_order_details_to_jira re-points existing 'ecom' and
  'ecom_gatekeeper' rows (live AND archived batches) where a jira id is
  known; rows without one keep their address; re-running moves nothing
- the ECOM list/detail and the gatekeeper ticket page address orders by
  ('jira', key); the obsolete "Take over orders" button is gone
- global search resolves order rows under the jira address to the ticket
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import gatekeeper as db_gk
from app.db import jira as db_jira
from app.db import order_archive as db_oa
import app.web_ecom as web_ecom
import app.web_notes as web_notes
import app.web_reference as web_reference
import app.web_search as web_search
import app.web_spillover as web_spillover
from app.web import app

JIRA = "S4ECOM-1153"


def _ecom_row():
    return {"jira_id": JIRA, "status": "Not Ready", "assigned_to": "",
            "country": "Germany (DE)", "testcase_scenario": "CANCELLATION",
            "test_case_id": "CAN0001MU01", "testcase_name": "CAN0001MU01_Web",
            "description_change": "", "execution_started": "",
            "order_number": "", "old_order_numbers": "", "defect_id_ref": "",
            "s4_sales_order": "", "s4_billing_documents": "",
            "s4_journal_invoice_entry": "", "delivery_note": "",
            "reason_for_pass_with_reservation": "", "comment": "",
            "excel_row": 2, "_skip_reason": ""}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "shared_orders.db"
    database.init_db(db_path).close()
    db_ecom.init_schema(db_path)
    db_jira.init_schema(db_path)
    db_gk.init_schema(db_path)
    db_oa.init_schema(db_path)
    monkeypatch.setattr(web_ecom, "_db_path", db_path)
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    monkeypatch.setattr(web_search, "_db_path", db_path)
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_spillover, "_get_conn",
                        lambda: database.get_connection(db_path))
    conn = database.get_connection(db_path)
    try:
        db_ecom.upsert_ecom_rows(conn, [_ecom_row()], "2026-07-16")
        ecom_id = db_ecom.get_ecom_rows(conn)[0]["ecom_id"]
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": JIRA, "solman_id": "SM1", "summary": "SM1_Zeropick",
            "epic": "", "markets": "DE", "jira_status": "In Progress",
            "jira_assignee": "Dev X", "type": "Bug", "priority": "High",
            "description": "", "link": "", "created": "c", "updated": "u",
            "comments": []}])
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    c.ecom_id = ecom_id
    return c


def test_migration_repoints_rows_with_known_jira_id(client):
    conn = database.get_connection(client.db_path)
    try:
        # old-style addresses: one at the ECOM row, one at a gatekeeper row
        # with a jira id, one at a gatekeeper row WITHOUT one
        d1 = database.add_order_detail(conn, "ecom", str(client.ecom_id))
        database.update_order_detail(conn, d1, "Sales order", "111", "", 1)
        gk = database.add_ecom_gatekeeper_row(conn)
        conn.execute("UPDATE ecom_gatekeeper SET jira_id=? WHERE id=?", (JIRA, gk))
        conn.commit()
        d2 = database.add_order_detail(conn, "ecom_gatekeeper", str(gk))
        database.update_order_detail(conn, d2, "Return order", "222", "", 0)
        gk_no_jira = database.add_ecom_gatekeeper_row(conn)
        d3 = database.add_order_detail(conn, "ecom_gatekeeper", str(gk_no_jira))
        # an already-archived batch under the old ECOM address migrates too
        d4 = database.add_order_detail(conn, "ecom", str(client.ecom_id))
        database.update_order_detail(conn, d4, "Exchange order", "333", "", 0)
        db_oa.archive_order_details(conn, "ecom", str(client.ecom_id), [d4], "old chain")

        moved = db_ecom.migrate_order_details_to_jira(conn)
        assert moved["order_details"] == 2 and moved["order_details_history"] == 1

        shared = database.list_order_details(conn, "jira", JIRA)
        assert sorted(r["order_number"] for r in shared) == ["111", "222"]
        # jira-less gatekeeper row keeps its address
        assert database.list_order_details(conn, "ecom_gatekeeper", str(gk_no_jira))
        # archived batch now lives at the jira address as well
        batches = db_oa.list_order_batches(conn, "jira", JIRA)
        assert len(batches) == 1 and batches[0]["label"] == "old chain"
        assert batches[0]["items"][0]["order_number"] == "333"
        # idempotent: second run moves nothing
        again = db_ecom.migrate_order_details_to_jira(conn)
        assert again == {"order_details": 0, "order_details_history": 0}
    finally:
        conn.close()


def test_pages_address_orders_by_jira_key(client):
    html = client.get("/ecom/").get_data(as_text=True)
    assert f'data-entity-type="jira" data-entity-id="{JIRA}"' in html

    html = client.get(f"/ecom/{client.ecom_id}").get_data(as_text=True)
    assert f'data-entity-type="jira" data-entity-id="{JIRA}"' in html
    assert "Take over orders" not in html            # handover button retired

    html = client.get(f"/ecom-gatekeeper/ticket/{JIRA}").get_data(as_text=True)
    assert html.count('id="dlg-orders"') == 1        # component included once
    assert f'data-entity-type="jira" data-entity-id="{JIRA}"' in html


def test_search_resolves_shared_jira_order_rows(client):
    conn = database.get_connection(client.db_path)
    try:
        d = database.add_order_detail(conn, "jira", JIRA)
        database.update_order_detail(conn, d, "Sales order", "9004711", "credit memo", 0)
    finally:
        conn.close()

    data = client.get("/search/orders.json?q=9004711").get_json()
    assert data["ok"]
    od_group = next(g for g in data["groups"] if g["group"] == "Order details")
    hit = od_group["hits"][0]
    assert JIRA in hit["label"] and "SM1_Zeropick" in hit["label"]
    assert hit["url"].endswith(f"/ecom-gatekeeper/ticket/{JIRA}")
