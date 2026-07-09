"""Mailing lists on /email-report (2026-07-09) — named recipient selections.

The rules a bug would silently break:
- saving under an existing name REPLACES the members (update semantics)
- deleting a recipient removes it from every list
- deleting a list never deletes recipients
- the save route refuses an empty name / empty selection with a clear error
"""
import pytest

from app.db import core as db_core
from app.db import email as db_email
import app.web_email as web_email
from app.web import app


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "lists.db"
    db_core.init_db(p).close()
    db_email.init_schema(p)
    return p


@pytest.fixture()
def conn(db_path):
    c = db_core.get_connection(db_path)
    yield c
    c.close()


def _seed(conn):
    db_email.add_recipient(conn, "a@x.com", "A")
    db_email.add_recipient(conn, "b@x.com", "B")
    db_email.add_recipient(conn, "c@x.com", "C")
    return {r["email"]: r["id"] for r in db_email.list_recipients(conn)}


def test_save_replaces_members_under_same_name(conn):
    ids = _seed(conn)
    db_email.save_email_list(conn, "Key users", [ids["a@x.com"], ids["b@x.com"]])
    db_email.save_email_list(conn, "Leads", [ids["c@x.com"]])

    lists = {l["name"]: l for l in db_email.list_email_lists(conn)}
    assert lists["Key users"]["member_ids"] == sorted([ids["a@x.com"], ids["b@x.com"]])
    assert lists["Leads"]["member_ids"] == [ids["c@x.com"]]

    # same name again = replace, not append
    db_email.save_email_list(conn, "Key users", [ids["c@x.com"]])
    lists = {l["name"]: l for l in db_email.list_email_lists(conn)}
    assert lists["Key users"]["member_ids"] == [ids["c@x.com"]]
    assert len(lists) == 2


def test_recipient_delete_cleans_memberships_list_delete_keeps_recipients(conn):
    ids = _seed(conn)
    lid = db_email.save_email_list(conn, "Everyone", list(ids.values()))

    db_email.delete_recipient(conn, ids["b@x.com"])
    lists = db_email.list_email_lists(conn)
    assert ids["b@x.com"] not in lists[0]["member_ids"]
    assert len(lists[0]["member_ids"]) == 2

    db_email.delete_email_list(conn, lid)
    assert db_email.list_email_lists(conn) == []
    assert len(db_email.list_recipients(conn)) == 2   # recipients untouched


def test_routes_roundtrip(db_path, monkeypatch):
    monkeypatch.setattr(web_email, "_db_path", db_path)
    conn = db_core.get_connection(db_path)
    try:
        ids = _seed(conn)
    finally:
        conn.close()
    client = app.test_client()

    # refuse empty name / empty selection
    r = client.post("/email-report/lists/save",
                    data={"list_name": "", "recipients": [str(ids["a@x.com"])]})
    assert "Give+the+mailing+list+a+name" in r.headers["Location"].replace("%20", "+")
    r = client.post("/email-report/lists/save", data={"list_name": "Empty"})
    assert "at+least+one+recipient" in r.headers["Location"].replace("%20", "+")

    # save + render: list chip with member ids appears
    client.post("/email-report/lists/save",
                data={"list_name": "Duo",
                      "recipients": [str(ids["a@x.com"]), str(ids["c@x.com"])]})
    html = client.get("/email-report/").get_data(as_text=True)
    assert "Duo (2)" in html
    assert "Save current selection as list" in html

    # delete
    conn = db_core.get_connection(db_path)
    try:
        lid = db_email.list_email_lists(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/email-report/lists/{lid}/delete")
    html = client.get("/email-report/").get_data(as_text=True)
    assert "Duo (2)" not in html
