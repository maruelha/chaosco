"""The four email-page changes [USER 2026-08-31].

1. the page opens with NOTHING ticked (all-ticked meant unticking eleven boxes
   for a two-report mail); ?reports= still pre-ticks one
2. a GROUP is a whole saved send: recipients + reports + its own subject/text
3. the report list in the mail follows the ticks — POST /email-report/text
   rebuilds subject + body from whatever is ticked right now
4. adding a recipient (or toggling/deleting one, or saving a group) must NOT
   throw away the typed text and the ticked reports: those endpoints answer
   fetch() with JSON so the page never reloads
"""
import pytest

from app import database, emailer
from app.db import email as db_email
import app.web_core as web_core
import app.web_email as web_email
from app.web import app

AJAX = {"X-Requested-With": "fetch"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "email.db"
    database.init_db(db_path).close()
    db_email.init_schema(db_path)
    for module in (web_core, web_email):
        monkeypatch.setattr(module, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _conn(client):
    return database.get_connection(client.db_path)


# ---------------------------------------------------------------- 1. no ticks

def test_page_opens_with_nothing_ticked(client):
    html = client.get("/email-report/").get_data(as_text=True)
    assert 'name="reports" value' in html
    assert 'checked' not in html.split('name="reports"')[1][:80]
    # the quick-select buttons are the way back to "everything"
    assert "reportsSelect('all')" in html and "reportsSelect('none')" in html


def test_query_param_still_pre_ticks_one_report(client):
    html = client.get("/email-report/?reports=retail").get_data(as_text=True)
    block = html.split('value="retail"')[1][:40]
    assert "checked" in block


def test_body_says_so_when_nothing_is_ticked(client):
    html = client.get("/email-report/").get_data(as_text=True)
    assert "(no report selected yet)" in html


# ------------------------------------------------------------------ 2. groups

def test_group_stores_recipients_reports_and_wording(client):
    conn = _conn(client)
    rid = db_email.add_recipient(conn, "a@x.com", "A")
    conn.close()

    resp = client.post("/email-report/lists/save", headers=AJAX, data={
        "list_name": "Management",
        "recipients": [str(rid)],
        "reports": ["retail", "delegated"],
        "subject": "Weekly pack", "body": "Dear management,"})
    group = resp.get_json()["group"]
    assert group["member_ids"] == [rid]
    assert group["report_keys"] == ["delegated", "retail"]
    assert group["subject"] == "Weekly pack"
    assert group["body"] == "Dear management,"

    # the page hands the whole group to the button as JSON
    html = client.get("/email-report/").get_data(as_text=True)
    assert "Management" in html and "js-group" in html


def test_saving_recipients_only_keeps_the_groups_reports(client):
    """A recipient-only save must not silently empty a group's report set."""
    conn = _conn(client)
    rid = db_email.add_recipient(conn, "a@x.com", "A")
    db_email.save_email_list(conn, "Key users", [rid],
                             report_keys=["board"], subject="S", body="B")
    db_email.save_email_list(conn, "Key users", [rid])          # no reports passed
    group = db_email.list_email_lists(conn)[0]
    conn.close()
    assert group["report_keys"] == ["board"]
    assert group["subject"] == "S"


def test_group_name_and_recipients_are_required(client):
    r = client.post("/email-report/lists/save", headers=AJAX,
                    data={"list_name": "", "recipients": ["1"]})
    assert r.status_code == 400 and "name" in r.get_json()["error"]
    r = client.post("/email-report/lists/save", headers=AJAX, data={"list_name": "X"})
    assert r.status_code == 400 and "recipient" in r.get_json()["error"]


# -------------------------------------------------------------- 3. email text

def test_regenerate_text_follows_the_ticked_reports(client):
    r = client.post("/email-report/text", headers=AJAX,
                    data={"date": "2026-09-01", "reports": ["retail", "board"]})
    d = r.get_json()
    assert "2026-09-01" in d["subject"]
    assert "Retail Status Report" in d["body"]
    assert "Retail Requirements Board" in d["body"]
    assert "Spillover Status Report" not in d["body"]      # not ticked → not listed


def test_regenerate_text_with_nothing_ticked(client):
    d = client.post("/email-report/text", headers=AJAX, data={}).get_json()
    assert "(no report selected yet)" in d["body"]


def test_default_texts_distinguishes_not_asked_from_nothing_ticked():
    assert "Retail Status Report" in emailer.default_texts()["body"]        # not asked
    assert "Retail Status Report" not in emailer.default_texts(reports=[])["body"]


# ------------------------------------------------- 4. no reload, nothing lost

def test_recipient_actions_answer_json_for_fetch(client):
    r = client.post("/email-report/recipients/add", headers=AJAX,
                    data={"email": "b@x.com", "name": "B"})
    body = r.get_json()
    assert body["ok"] and body["recipient"]["email"] == "b@x.com"
    rid = body["recipient"]["id"]

    r = client.post(f"/email-report/recipients/{rid}/toggle", headers=AJAX)
    assert r.get_json() == {"ok": True, "id": rid, "active": False}

    r = client.post(f"/email-report/recipients/{rid}/delete", headers=AJAX)
    assert r.get_json()["ok"]
    conn = _conn(client)
    assert db_email.list_recipients(conn) == []
    conn.close()


def test_a_bad_address_is_reported_not_swallowed(client):
    r = client.post("/email-report/recipients/add", headers=AJAX, data={"email": "nope"})
    assert r.status_code == 400 and "valid email" in r.get_json()["error"]


def test_without_the_fetch_header_the_endpoints_still_redirect(client):
    """No-JavaScript fallback: the same routes keep the old behaviour."""
    r = client.post("/email-report/recipients/add", data={"email": "c@x.com"})
    assert r.status_code == 302 and "/email-report/" in r.headers["Location"]
