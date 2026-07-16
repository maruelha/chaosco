"""Inbox text search (2026-07-16) — live client-side filter.

The filtering itself is JS (verified by eye, per convention); these tests
pin the contract the JS depends on: the search controls render exactly once
and every pending item exposes heading / text / attachment names in the
classes the filter reads.
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


def test_inbox_renders_search_controls_and_filter_hooks(client):
    conn = database.get_connection(client.db_path)
    try:
        database.add_note(conn, "input", "inbox", "SF creation PL", "ask Jose about it")
    finally:
        conn.close()

    html = client.get("/inbox").get_data(as_text=True)
    assert html.count('id="inbox-search"') == 1
    assert html.count('id="inbox-search-clear"') == 1
    assert html.count('id="inbox-count"') == 1
    assert html.count('id="inbox-no-match"') == 1
    # the hooks the JS filter reads
    assert 'class="note-heading"' in html and "SF creation PL" in html
    assert 'class="note-text"' in html and "ask Jose about it" in html


def test_empty_inbox_has_no_search_box(client):
    html = client.get("/inbox").get_data(as_text=True)
    assert 'id="inbox-search"' not in html          # box lives in the items card
    assert "Inbox is empty" in html
