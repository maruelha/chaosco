"""Deadlines & Burning [USER 2026-08-11].

What must hold:
- three categories, kept apart on the page: deadline / burning / uncomfortable
- overdue is computed against TODAY and drives the red treatment; an item
  without a date is never overdue, and a DONE item never nags
- open items sort dated-before-undated, earliest first — the nag list must
  lead with what is closest to blowing up
- the dashboard popup appears only while something is open, lists those items
  and can tick them off; the card counts match
- a junk date is dropped rather than stored (it would sort and compare wrongly)
"""
from datetime import date, timedelta

import pytest

from app import database
from app.db import urgent as db_urgent
import app.web_core as web_core
import app.web_urgent as web_urgent
from app.web import app


def _d(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "urgent.db"
    database.init_db(db_path).close()
    db_urgent.init_schema(db_path)
    # the dashboard also reads the tracker, topics and retrofits
    from app import db_retail_tracker
    from app.db import retrofits as db_retrofits
    from app.db import topics as db_topics
    db_retail_tracker.init_schema(db_path)
    db_retrofits.init_schema(db_path)
    db_topics.init_schema(db_path)
    monkeypatch.setattr(web_core, "_db_path", db_path)
    monkeypatch.setattr(web_urgent, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _add(client, **fields):
    data = {"category": "deadline", "title": "Something"}
    data.update(fields)
    return client.post("/urgent/add", data=data)


def _conn(client):
    return database.get_connection(client.db_path)


def test_add_and_list_by_category(client):
    _add(client, category="deadline", title="Sign-off pack", due_date=_d(3))
    _add(client, category="burning", title="Voucher bug")
    _add(client, category="uncomfortable", title="Promised Jose the list")

    conn = _conn(client)
    try:
        grouped = db_urgent.list_by_category(conn)
    finally:
        conn.close()
    assert [i["title"] for i in grouped["deadline"]] == ["Sign-off pack"]
    assert [i["title"] for i in grouped["burning"]] == ["Voucher bug"]
    assert [i["title"] for i in grouped["uncomfortable"]] == ["Promised Jose the list"]

    html = client.get("/urgent/").get_data(as_text=True)
    for label in ("Deadline", "Burning", "Uncomfortable"):
        assert label in html


def test_blank_title_is_not_added(client):
    _add(client, title="   ")
    conn = _conn(client)
    try:
        assert db_urgent.list_urgent(conn) == []
    finally:
        conn.close()


@pytest.mark.parametrize("given,expected", [
    ("deadline", "deadline"), ("BURNING", "burning"),
    ("Uncomfortable", "uncomfortable"), ("nonsense", "deadline"), ("", "deadline"),
])
def test_category_normalised(client, given, expected):
    conn = _conn(client)
    try:
        rid = db_urgent.create_urgent(conn, given, "t")
        assert db_urgent.get_urgent(conn, rid)["category"] == expected
    finally:
        conn.close()


def test_junk_date_is_dropped_not_stored(client):
    conn = _conn(client)
    try:
        rid = db_urgent.create_urgent(conn, "deadline", "t", due_date="next tuesday")
        assert db_urgent.get_urgent(conn, rid)["due_date"] is None
        rid2 = db_urgent.create_urgent(conn, "deadline", "t2", due_date="2026-09-01")
        assert db_urgent.get_urgent(conn, rid2)["due_date"] == "2026-09-01"
    finally:
        conn.close()


def test_overdue_due_today_and_undated(client):
    _add(client, title="Late", due_date=_d(-3))
    _add(client, title="Today", due_date=_d(0))
    _add(client, title="Later", due_date=_d(5))
    _add(client, title="No date")

    conn = _conn(client)
    try:
        by_title = {i["title"]: i for i in db_urgent.list_urgent(conn)}
        counts = db_urgent.urgent_counts(conn)
    finally:
        conn.close()

    assert by_title["Late"]["overdue"] and by_title["Late"]["days_left"] == -3
    assert by_title["Today"]["due_today"] and not by_title["Today"]["overdue"]
    assert not by_title["Later"]["overdue"] and by_title["Later"]["days_left"] == 5
    assert by_title["No date"]["days_left"] is None
    assert not by_title["No date"]["overdue"]

    assert counts == {"open": 4, "overdue": 1, "due_today": 1,
                      "deadline": 4, "burning": 0, "uncomfortable": 0}


def test_open_items_sort_most_urgent_first(client):
    _add(client, title="No date")
    _add(client, title="Later", due_date=_d(9))
    _add(client, title="Late", due_date=_d(-2))
    conn = _conn(client)
    try:
        titles = [i["title"] for i in db_urgent.list_urgent(conn)]
    finally:
        conn.close()
    assert titles == ["Late", "Later", "No date"]


def test_done_item_stops_nagging_and_can_reopen(client):
    _add(client, title="Late", due_date=_d(-2))
    conn = _conn(client)
    try:
        item_id = db_urgent.list_urgent(conn)[0]["id"]
    finally:
        conn.close()

    resp = client.post(f"/urgent/{item_id}/done", data={"done": "1"})
    body = resp.get_json()
    assert body["ok"] and body["counts"]["open"] == 0 and body["counts"]["overdue"] == 0

    conn = _conn(client)
    try:
        assert db_urgent.list_urgent(conn) == []
        done = [i for i in db_urgent.list_urgent(conn, include_done=True) if i["done"]]
        assert len(done) == 1
        assert done[0]["done_at"]
        assert not done[0]["overdue"]        # done never counts as overdue
    finally:
        conn.close()

    client.post(f"/urgent/{item_id}/done", data={"done": "0"})
    conn = _conn(client)
    try:
        reopened = db_urgent.list_urgent(conn)
        assert len(reopened) == 1 and reopened[0]["overdue"]
    finally:
        conn.close()


def test_update_and_delete(client):
    _add(client, title="Draft", due_date=_d(1))
    conn = _conn(client)
    try:
        item_id = db_urgent.list_urgent(conn)[0]["id"]
    finally:
        conn.close()

    client.post(f"/urgent/{item_id}/update", data={
        "category": "uncomfortable", "title": "Reworded", "due_date": "", "note": "why"})
    conn = _conn(client)
    try:
        item = db_urgent.get_urgent(conn, item_id)
        assert item["category"] == "uncomfortable"
        assert item["title"] == "Reworded"
        assert item["due_date"] is None and item["note"] == "why"
    finally:
        conn.close()

    assert client.post(f"/urgent/{item_id}/delete").get_json()["ok"]
    conn = _conn(client)
    try:
        assert db_urgent.get_urgent(conn, item_id) is None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dashboard card + popup
# ---------------------------------------------------------------------------

def test_no_popup_when_nothing_is_open(client):
    resp = client.get("/")
    assert resp.status_code == 200          # not a 500 that trivially lacks it
    assert "urgent-popup" not in resp.get_data(as_text=True)


def test_popup_lists_open_items_and_card_shows_counts(client):
    _add(client, title="Sign-off pack", due_date=_d(-1))
    _add(client, category="burning", title="Voucher bug")

    html = client.get("/").get_data(as_text=True)
    assert "urgent-popup" in html
    assert "Sign-off pack" in html and "Voucher bug" in html
    assert "action-card--urgent" in html          # the red card
    assert "1 overdue" in html                     # popup subtitle
    assert "1d over" in html


def test_popup_disappears_once_everything_is_done(client):
    _add(client, title="Only thing")
    conn = _conn(client)
    try:
        item_id = db_urgent.list_urgent(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/urgent/{item_id}/done", data={"done": "1"})
    assert "urgent-popup" not in client.get("/").get_data(as_text=True)


def test_popup_is_dismissed_once_per_day(client):
    """The dismissal is remembered per DAY, so it nags again tomorrow but not
    on every dashboard visit — pin the contract the JS relies on."""
    _add(client, title="Something")
    html = client.get("/").get_data(as_text=True)
    assert "urgent-popup-seen" in html
    assert f'"{date.today().isoformat()}"' in html
