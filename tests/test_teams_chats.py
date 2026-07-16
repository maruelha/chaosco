"""Teams chats & channels registry + per-ticket refs (2026-07-16).

[USER decisions]: one dedicated table (link OR emails per entry), one clean
management UI, one pinned flag for the floating widget, tickets REFERENCE
registry rows (never copy), multiple chats per ticket allowed.
What must hold:
- migration moves 'Teams Channel' links rows into teams_chats (kind
  'channel'), removes them from links, is idempotent — and the ping-page
  channel picker routes still serve them (follow-up flow untouched)
- an entry resolves its URL from the stored link, else builds it from emails
- pinned.json returns only pinned entries; add validates link-or-emails
- attach/detach per entity; chats_by_entity feeds the list-row buttons;
  deleting a registry row also removes its refs
"""
import pytest

from app import database
from app.db import teams_chats as db_tc
import app.web_reference as web_reference
import app.web_teams as web_teams
import app.web_teams_chats as web_tc
from app.web import app

TEAMS = "https://teams.microsoft.com/l/chat/19:abc123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "chats.db"
    database.init_db(db_path).close()
    db_tc.init_schema(db_path)
    monkeypatch.setattr(web_tc, "_db_path", db_path)
    monkeypatch.setattr(web_teams, "_db_path", db_path)
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    return c


def test_channel_links_migrate_and_picker_keeps_working(client):
    conn = database.get_connection(client.db_path)
    try:
        database.create_link(conn, description="DTC O2C Daily",
                             url="https://teams.microsoft.com/l/channel/x",
                             area=None, tool="Teams Channel", tags=None)
        moved = db_tc.migrate_channel_links(conn)
        assert moved == 1
        assert db_tc.migrate_channel_links(conn) == 0        # idempotent
        assert database.list_links(conn, tools=["Teams Channel"]) == []
        chats = db_tc.list_teams_chats(conn)
        assert len(chats) == 1 and chats[0]["kind"] == "channel"
    finally:
        conn.close()

    # follow-up functionality: the ping-page picker routes still serve them
    d = client.get("/teams-ping/channels.json").get_json()
    assert len(d) == 1 and d[0]["name"] == "DTC O2C Daily"
    assert d[0]["url"].startswith("https://teams.microsoft.com/l/channel/")

    d = client.post("/teams-ping/channels/add",
                    data={"name": "Second", "url": TEAMS}).get_json()
    assert d["ok"]
    channels = client.get("/teams-ping/channels.json").get_json()
    assert {c["name"] for c in channels} == {"DTC O2C Daily", "Second"}
    assert client.post(f"/teams-ping/channels/{channels[0]['id']}/delete"
                       ).get_json()["ok"]


def test_url_resolution_link_wins_else_emails():
    assert db_tc.resolve_chat_url({"link": TEAMS, "emails": "a@x.com"}) == TEAMS
    url = db_tc.resolve_chat_url({"link": "", "emails": "a@x.com, b@x.com",
                                  "name": "PL chat"})
    assert url.startswith("https://teams.microsoft.com/l/chat/0/0?users=")
    assert "a@x.com" in url and "b@x.com" in url
    assert db_tc.resolve_chat_url({"link": None, "emails": None}) == ""


def test_add_validation_and_pinned_json(client):
    d = client.post("/teams-chats/add", data={"name": "No target"}).get_json()
    assert not d["ok"]
    d = client.post("/teams-chats/add",
                    data={"name": "X", "link": "https://evil.example.com/x"}).get_json()
    assert not d["ok"]

    d = client.post("/teams-chats/add",
                    data={"name": "PL returns", "emails": "a@x.com",
                          "pinned": "1"}).get_json()
    assert d["ok"] and d["chat"]["url"].startswith("https://teams.microsoft.com/")
    client.post("/teams-chats/add", data={"name": "Unpinned", "link": TEAMS})

    pinned = client.get("/teams-chats/pinned.json").get_json()
    assert [p["name"] for p in pinned] == ["PL returns"]

    html = client.get("/teams-chats/").get_data(as_text=True)
    assert "PL returns" in html and "Unpinned" in html


def test_refs_attach_detach_and_row_map(client):
    conn = database.get_connection(client.db_path)
    try:
        c1 = db_tc.create_teams_chat(conn, "Chat A", link=TEAMS)
        c2 = db_tc.create_teams_chat(conn, "Chat B", emails="b@x.com")
    finally:
        conn.close()

    assert client.post(f"/teams-chats/refs/jira/S4ECOM-1/attach",
                       data={"chat_id": str(c1)}).get_json()["ok"]
    assert client.post(f"/teams-chats/refs/jira/S4ECOM-1/attach",
                       data={"chat_id": str(c2)}).get_json()["ok"]
    # attaching twice is a no-op, unknown chat fails
    assert client.post(f"/teams-chats/refs/jira/S4ECOM-1/attach",
                       data={"chat_id": str(c1)}).get_json()["ok"]
    assert not client.post(f"/teams-chats/refs/jira/S4ECOM-1/attach",
                           data={"chat_id": "999"}).get_json()["ok"]

    refs = client.get("/teams-chats/refs/jira/S4ECOM-1").get_json()
    assert [r["name"] for r in refs] == ["Chat A", "Chat B"]

    conn = database.get_connection(client.db_path)
    try:
        row_map = db_tc.chats_by_entity(conn, "jira")
        assert [c["name"] for c in row_map["S4ECOM-1"]] == ["Chat A", "Chat B"]

        client.post(f"/teams-chats/refs/jira/S4ECOM-1/detach",
                    data={"chat_id": str(c2)})
        # deleting a registry row removes its refs too
        db_tc.delete_teams_chat(conn, c1)
        assert db_tc.list_chat_refs(conn, "jira", "S4ECOM-1") == []
    finally:
        conn.close()
