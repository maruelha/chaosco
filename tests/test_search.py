"""Global order-number search (2026-07-10) — source registry + widget.

What must hold:
- one query hits ALL the places an order number lives: order_details lines
  (with the pinned entity resolved) + the imported cells of spillover,
  retail, ecom, defects
- every hit maps to a working detail URL; orphaned order_details lines are
  dropped, never 500
- queries under 3 characters are refused
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import search as db_search
import app.web_search as web_search
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "search.db"
    database.init_db(db_path).close()
    db_ecom.init_schema(db_path)
    monkeypatch.setattr(web_search, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        with conn:
            conn.execute("INSERT INTO spillover (match_key, name, order_numbers,"
                         " first_seen, last_seen) VALUES ('a', 'Spill A',"
                         " '102-4711/102-4712', 'd', 'd')")
            conn.execute("INSERT INTO retail (match_key, test_case_id, country,"
                         " order_number) VALUES ('t1|de', 'T1', 'Germany', '102-4711')")
            conn.execute("INSERT INTO defects (defect_id, channel, solman_name,"
                         " order_number) VALUES ('D-1', 'Retail', 'Broken thing',"
                         " '102-4711/126')")
        db_ecom.upsert_ecom_rows(conn, [{
            "jira_id": "S4ECOM-1", "status": "", "assigned_to": "", "country": "DE",
            "testcase_scenario": "", "test_case_id": "TC1", "testcase_name": "TC1_x",
            "description_change": "", "execution_started": "",
            "order_number": "555-000", "old_order_numbers": "102-4711",
            "defect_id_ref": "", "s4_sales_order": "", "s4_billing_documents": "",
            "s4_journal_invoice_entry": "", "delivery_note": "",
            "reason_for_pass_with_reservation": "", "comment": "", "excel_row": 2,
            "_skip_reason": ""}], "2026-07-10")
        sid = conn.execute("SELECT spillover_id FROM spillover").fetchone()[0]
        detail_id = database.add_order_detail(conn, "spillover", str(sid))
        database.update_order_detail(conn, detail_id, "Return", "102-4711",
                                     "credit memo check", docs_in_s4=1)
        # orphaned line: entity gone -> must be skipped silently
        database.add_order_detail(conn, "ecom_gatekeeper", "424242")
        orphan = database.list_order_details(conn, "ecom_gatekeeper", "424242")[0]
        database.update_order_detail(conn, orphan["id"], "", "102-4711", "")
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    return c


def test_search_hits_every_source(client):
    conn = database.get_connection(client.db_path)
    try:
        groups = {g["group"]: g["hits"] for g in
                  db_search.search_order_number(conn, "102-4711")}
    finally:
        conn.close()
    assert set(groups) == {"Order details", "Spillover", "Retail", "ECOM", "Defects"}
    assert groups["Order details"][0]["label"] == "Spill A"
    assert "[Return] 102-4711 — credit memo check" == groups["Order details"][0]["match"]
    assert groups["Retail"][0]["label"] == "T1 / Germany"
    assert groups["ECOM"][0]["match"] == "555-000 · 102-4711"
    assert groups["Defects"][0]["label"].startswith("D-1")


def test_route_returns_urls_and_min_length(client):
    d = client.get("/search/orders.json?q=10").get_json()
    assert not d["ok"] and "3 characters" in d["error"]

    d = client.get("/search/orders.json?q=102-4711").get_json()
    assert d["ok"]
    by_group = {g["group"]: g["hits"] for g in d["groups"]}
    assert by_group["Retail"][0]["url"].startswith("/retail/")
    assert by_group["Defects"][0]["url"] == "/defects/D-1"
    assert by_group["Spillover"][0]["url"].startswith("/spillover/")
    assert by_group["ECOM"][0]["url"].startswith("/ecom/")

    d = client.get("/search/orders.json?q=zzz-nothing").get_json()
    assert d["ok"] and d["groups"] == []


def test_widget_renders_on_every_page(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="search-widget"' in html
    assert "/search/orders.json" in html
