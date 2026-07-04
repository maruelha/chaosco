"""Tests for the Topics card (active working topics: steps, workpad, filing)."""
import pytest

from app import database
from app.db import topics as db_topics
import app.web_topics as web_topics
import app.web_notes as web_notes
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "topics.db"
    database.init_db(db_path).close()
    db_topics.init_schema(db_path)
    monkeypatch.setattr(web_topics, "_db_path", db_path)
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _conn(client):
    return database.get_connection(client.db_path)


def test_topic_crud_and_filters(client):
    conn = _conn(client)
    try:
        t1 = db_topics.create_topic(conn, "Sign-off preparation", "Orga", "High")
        db_topics.create_topic(conn, "Voucher edge cases", "Retail", "Low")
        assert [t["title"] for t in db_topics.list_topics(conn)] == \
            ["Sign-off preparation", "Voucher edge cases"]      # High sorts first
        assert [t["title"] for t in db_topics.list_topics(conn, category="Orga")] == \
            ["Sign-off preparation"]
        assert [t["title"] for t in db_topics.list_topics(conn, q="voucher")] == \
            ["Voucher edge cases"]
        # done topics disappear from the default list
        db_topics.update_topic(conn, t1, "Sign-off preparation", "Orga", "High", "done")
        assert len(db_topics.list_topics(conn)) == 1
        assert len(db_topics.list_topics(conn, include_done=True)) == 2
        assert db_topics.count_active_topics(conn) == 1
    finally:
        conn.close()


def test_steps_toggle_and_archive(client):
    conn = _conn(client)
    try:
        tid = db_topics.create_topic(conn, "T")
        s1 = db_topics.add_step(conn, tid, "clarify with IT")
        db_topics.add_step(conn, tid, "write summary")
        db_topics.set_step_done(conn, s1, True)
        steps = db_topics.list_steps(conn, tid)
        assert [s["done"] for s in steps] == [0, 1]          # open first, done archived
        assert steps[1]["done_at"] is not None
        db_topics.set_step_done(conn, s1, False)             # reopen
        assert all(s["done"] == 0 for s in db_topics.list_steps(conn, tid))
    finally:
        conn.close()


def test_workpad_roundtrip_via_route(client):
    conn = _conn(client)
    try:
        tid = db_topics.create_topic(conn, "T")
    finally:
        conn.close()
    html = "<h2>Plan</h2><ul><li><b>bold</b> point</li></ul>"
    r = client.post(f"/topics/{tid}/workpad", data={"workpad": html})
    assert r.get_json()["ok"] is True
    conn = _conn(client)
    try:
        assert db_topics.get_topic(conn, tid)["workpad"] == html
    finally:
        conn.close()
    # detail page renders the stored HTML back into the pad
    page = client.get(f"/topics/{tid}").get_data(as_text=True)
    assert "<h2>Plan</h2>" in page


def test_detail_page_shows_steps_and_notes_module(client):
    conn = _conn(client)
    try:
        tid = db_topics.create_topic(conn, "Big topic", "Orga", "High")
        db_topics.add_step(conn, tid, "first step")
        database.add_note(conn, "topic", str(tid), "note heading", "note body")
    finally:
        conn.close()
    page = client.get(f"/topics/{tid}").get_data(as_text=True)
    assert "first step" in page
    assert "note body" in page                       # shared notes include
    assert f"/n/topic/{tid}/add" in page             # generic note routes wired


def test_inbox_files_into_topic(client):
    conn = _conn(client)
    try:
        tid = db_topics.create_topic(conn, "Voucher edge cases", "Retail")
        note_id = database.add_inbox_item(conn, "observation", "seen in store 12")
        # the filing picker finds active topics by title
        hits = database.search_targets(conn, "topic", "voucher")
        assert hits and hits[0]["value"] == str(tid)
        assert database.file_inbox_item(conn, note_id, "topic", str(tid)) is True
        notes = database.list_notes(conn, "topic", str(tid))
        assert [n["note"] for n in notes] == ["seen in store 12"]
        assert database.count_inbox_items(conn) == 0
    finally:
        conn.close()


def test_delete_topic_cleans_steps_and_notes(client):
    conn = _conn(client)
    try:
        tid = db_topics.create_topic(conn, "temp")
        db_topics.add_step(conn, tid, "s")
        database.add_note(conn, "topic", str(tid), None, "n")
        db_topics.delete_topic(conn, tid)
        assert db_topics.get_topic(conn, tid) is None
        assert db_topics.list_steps(conn, tid) == []
        assert database.list_notes(conn, "topic", str(tid)) == []
    finally:
        conn.close()
