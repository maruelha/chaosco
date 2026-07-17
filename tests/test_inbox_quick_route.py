"""Inbox quick route-to combobox (2026-07-18).

Each pending item carries a route-to select directly in its actions row
(POST /inbox/<id>/route) so items can be flagged for the ⚡ Auto-file batch
run without opening the edit form.
"""
import pytest

from app import database
import app.web_reference as web_reference
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "inbox.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    return c


def _add_item(client, heading="Jose from ECOM"):
    conn = database.get_connection(client.db_path)
    try:
        database.add_note(conn, "input", "inbox", heading, "some text")
        return database.list_inbox_items(conn)[0]["id"]
    finally:
        conn.close()


def _route_of(client, note_id):
    conn = database.get_connection(client.db_path)
    try:
        return database.get_inbox_item(conn, note_id)["route_to"]
    finally:
        conn.close()


def test_quick_route_sets_clears_and_rejects_invalid(client):
    note_id = _add_item(client)

    resp = client.post(f"/inbox/{note_id}/route", data={"route_to": "link"})
    assert resp.status_code == 302
    assert _route_of(client, note_id) == "link"

    client.post(f"/inbox/{note_id}/route", data={"route_to": "contact"})
    assert _route_of(client, note_id) == "contact"

    client.post(f"/inbox/{note_id}/route", data={"route_to": "shelf"})
    assert _route_of(client, note_id) is None          # not a route_to module

    client.post(f"/inbox/{note_id}/route", data={"route_to": "followup"})
    client.post(f"/inbox/{note_id}/route", data={"route_to": ""})
    assert _route_of(client, note_id) is None          # empty clears


def test_each_item_renders_quick_route_select(client):
    a = _add_item(client, "first")
    _add_item(client, "second")
    client.post(f"/inbox/{a}/route", data={"route_to": "contact"})

    html = client.get("/inbox").get_data(as_text=True)
    assert html.count('class="form-control quick-route-sel"') == 2
    assert f'action="/inbox/{a}/route"' in html
    assert 'value="contact" selected' in html
