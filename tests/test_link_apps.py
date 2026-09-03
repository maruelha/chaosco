"""Links ↔ mini apps (2026-09-03 [USER]): a Links-card link can be attached
to mini apps (registry app/mini_apps.py, table link_apps); the app's page
header gets a 🔗 Links button that opens the global dialog (base.html) fed
by /links/for/<slug>.json."""
import pytest

from app import database
from app.mini_apps import APPS
import app.web_reference as web_reference
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "links.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    return c


def test_registry_has_the_two_apps_to_start():
    assert set(APPS) == {"delegated", "sustain"}
    for a in APPS.values():
        assert a["title"] and a["home_endpoint"]


def test_storage_roundtrip_filter_and_cascade(client):
    conn = database.get_connection(client.db_path)
    try:
        a = database.create_link(conn, "Sales dashboard", "https://x/a", None, None, None)
        b = database.create_link(conn, "GBS checklist", "https://x/b", None, None, None)
        c = database.create_link(conn, "Nowhere", "https://x/c", None, None, None)
        database.set_link_apps(conn, a["id"], ["delegated", "bogus"])       # unknown dropped
        database.set_link_apps(conn, b["id"], ["sustain", "delegated"])
        assert database.get_link_apps(conn, a["id"]) == ["delegated"]
        assert database.get_link_apps(conn, b["id"]) == ["delegated", "sustain"]
        assert database.link_apps_by_link(conn) == {a["id"]: ["delegated"],
                                                    b["id"]: ["delegated", "sustain"]}
        assert [r["description"] for r in database.list_links_for_app(conn, "delegated")] == \
            ["GBS checklist", "Sales dashboard"]
        assert database.count_links_for_app(conn, "sustain") == 1
        assert [r["id"] for r in database.list_links(conn, apps=["sustain"])] == [b["id"]]
        assert len(database.list_links(conn)) == 3
        # replace, then delete cascades
        database.set_link_apps(conn, b["id"], [])
        assert database.get_link_apps(conn, b["id"]) == []
        database.delete_link(conn, a["id"])
        assert database.link_apps_by_link(conn) == {}
        assert c["id"] in [r["id"] for r in database.list_links(conn)]
    finally:
        conn.close()


def test_link_form_saves_apps_and_list_shows_chips_and_filter(client):
    resp = client.post("/links/new", data={"description": "Sales dashboard",
                                           "url": "https://x/a", "app": ["delegated"]})
    assert resp.status_code == 302
    link_id = int(resp.headers["Location"].rstrip("/").split("/")[-1].split("?")[0])
    client.post("/links/new", data={"description": "Other", "url": "https://x/o"})

    detail = client.get(f"/links/{link_id}").get_data(as_text=True)
    assert 'name="app" value="delegated" checked' in detail
    assert 'name="app" value="sustain" ' in detail and 'value="sustain" checked' not in detail

    # edit: move it to sustain only
    client.post(f"/links/{link_id}", data={"description": "Sales dashboard",
                                           "url": "https://x/a", "app": ["sustain"]})
    conn = database.get_connection(client.db_path)
    try:
        assert database.get_link_apps(conn, link_id) == ["sustain"]
    finally:
        conn.close()

    html = client.get("/links").get_data(as_text=True)
    assert "🔗 Core South Sustainphase Monitoring" in html
    assert "Filter by mini app" in html
    filtered = client.get("/links?app=sustain").get_data(as_text=True)
    assert "Sales dashboard" in filtered and ">Other<" not in filtered
    none = client.get("/links?app=delegated").get_data(as_text=True)
    assert "Sales dashboard" not in none


def test_links_for_app_json_and_unknown_slug(client):
    client.post("/links/new", data={"description": "GBS checklist", "url": "https://x/b",
                                    "app": ["sustain", "delegated"]})
    data = client.get("/links/for/sustain.json").get_json()
    assert data["ok"] and data["app"] == "Core South Sustainphase Monitoring"
    assert [l["description"] for l in data["links"]] == ["GBS checklist"]
    assert data["links"][0]["url"] == "https://x/b"
    assert client.get("/links/for/nope.json").status_code == 404


def test_dialog_is_in_the_base_layout_once(client):
    html = client.get("/links").get_data(as_text=True)
    assert html.count('id="app-links-dialog"') == 1
    assert "/links/for/" in html and "Copy all" in html
