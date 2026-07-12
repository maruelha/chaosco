"""Order-details drop-in component (_order_details.html, day plan step 1).

What must hold after de-duplicating the two inline copies:
- the generic /order-details/... AJAX routes roundtrip for BOTH entity types
- each page renders the shared dialog exactly ONCE (no leftover inline copy)
- the S4 badge helper is generic per entity type; the gatekeeper page shows
  the initial ✓ (the 'free upgrade' from the day plan)
"""
import pytest

from app import database
import app.web_spillover as web_spillover
import app.web_reference as web_reference
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "orders.db"
    database.init_db(db_path).close()
    from app.db import ecom as db_ecom
    from app.db import gatekeeper as db_gk
    from app.db import jira as db_jira
    db_jira.init_schema(db_path)   # gatekeeper page reads the jira store,
    db_gk.init_schema(db_path)     # the gatekeeper annotations,
    db_ecom.init_schema(db_path)   # and the board (on-board state)
    for mod in (web_spillover, web_reference):
        monkeypatch.setattr(mod, "_get_conn",
                            lambda p=db_path: database.get_connection(p))
    c = app.test_client()
    c.db_path = db_path
    return c


@pytest.mark.parametrize("entity_type", ["spillover", "ecom_gatekeeper"])
def test_order_details_roundtrip(client, entity_type):
    # add
    d = client.post(f"/order-details/{entity_type}/7/add").get_json()
    assert d["ok"]
    detail_id = d["id"]

    # update incl. the S4 checkbox
    client.post(f"/order-details/{detail_id}/update",
                data={"order_type": "Return", "order_number": "4711",
                      "comment": "check credit memo", "docs_in_s4": "1"})
    rows = client.get(f"/order-details/{entity_type}/7").get_json()
    assert rows == [{"id": detail_id, "order_type": "Return",
                     "order_number": "4711", "comment": "check credit memo",
                     "docs_in_s4": 1}]

    # S4 helper is generic: flagged under THIS type only
    conn = database.get_connection(client.db_path)
    try:
        assert database.get_docs_s4_entity_ids(conn, entity_type) == {7}
        other = "spillover" if entity_type == "ecom_gatekeeper" else "ecom_gatekeeper"
        assert database.get_docs_s4_entity_ids(conn, other) == set()
    finally:
        conn.close()

    # delete
    client.post(f"/order-details/{detail_id}/delete")
    assert client.get(f"/order-details/{entity_type}/7").get_json() == []


@pytest.mark.parametrize("url", ["/spillover", "/ecom-gatekeeper"])
def test_pages_render_shared_dialog_exactly_once(client, url):
    html = client.get(url).get_data(as_text=True)
    assert html.count('id="dlg-orders"') == 1     # component present, no inline copy
    assert html.count('id="btn-add-order"') == 1
    assert "js-open-orders" in html or url == "/spillover"  # buttons render with rows


def test_gatekeeper_shows_initial_s4_badge(client):
    conn = database.get_connection(client.db_path)
    try:
        row_id = database.add_ecom_gatekeeper_row(conn)
        detail_id = database.add_order_detail(conn, "ecom_gatekeeper", str(row_id))
        database.update_order_detail(conn, detail_id, "Sale", "1", "", docs_in_s4=1)
    finally:
        conn.close()
    html = client.get("/ecom-gatekeeper").get_data(as_text=True)
    assert '<span class="s4-tick"> ✓</span>' in html
