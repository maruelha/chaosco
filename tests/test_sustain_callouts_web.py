"""Sustain Call-outs (build plan step 2, 2026-09-01): routes + the card-page
section — add, cycling status chip, edit, delete, show/hide closed."""
import pytest

from app import database
from app.db import sustain as db_sustain
from app.db import sustain_callouts as db_sc
import app.web_sustain as web_sustain
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sc.db"
    database.init_db(db_path).close()
    db_sustain.init_schema(db_path)
    db_sc.init_schema(db_path)
    monkeypatch.setattr(web_sustain, "_get_conn",
                        lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    return c


def _add(client, **fields):
    data = {"channel": "retail", "type": "Issue", "topic": "Something to check"}
    data.update(fields)
    return client.post("/sustain/callouts/add", data=data)


def test_home_shows_call_outs_section(client):
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Call-outs" in html


def test_add_shows_up_on_card(client):
    _add(client, topic="Settlement mismatch", responsible="Marina")
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Settlement mismatch" in html
    assert "Marina" in html


def test_add_without_topic_is_rejected(client):
    resp = _add(client, topic="  ")
    assert resp.status_code == 302
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Nothing to review" in html


def test_status_cycles_and_saves(client, tmp_path):
    _add(client)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    resp = client.post(f"/sustain/callouts/{cid}/status")
    assert resp.get_json() == {"ok": True, "status": "in_progress",
                                "label": "In Progress"}
    resp = client.post(f"/sustain/callouts/{cid}/status")
    assert resp.get_json()["status"] == "closed"
    resp = client.post(f"/sustain/callouts/{cid}/status")
    assert resp.get_json()["status"] == "open"


def test_status_unknown_id_404s(client):
    resp = client.post("/sustain/callouts/999/status")
    assert resp.status_code == 404


def test_update_changes_fields(client, tmp_path):
    _add(client, topic="Original")
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/sustain/callouts/{cid}/update", data={
        "channel": "ecom", "type": "MigrIssue", "topic": "Updated topic",
        "responsible": "Someone",
    })
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Updated topic" in html
    assert "Original" not in html


def test_delete_removes_it(client, tmp_path):
    _add(client, topic="Gone soon")
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    resp = client.post(f"/sustain/callouts/{cid}/delete")
    assert resp.get_json() == {"ok": True}
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Gone soon" not in html


def test_closed_hidden_by_default_and_shown_with_toggle(client, tmp_path):
    _add(client, topic="Will be closed")
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/sustain/callouts/{cid}/status")  # -> in_progress
    client.post(f"/sustain/callouts/{cid}/status")  # -> closed

    html = client.get("/sustain/").get_data(as_text=True)
    assert "Will be closed" not in html
    assert 'href="/sustain/?show_closed=1"' in html

    html = client.get("/sustain/?show_closed=1").get_data(as_text=True)
    assert "Will be closed" in html
