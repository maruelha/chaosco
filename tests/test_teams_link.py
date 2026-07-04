"""Tests for the Teams deep-link ping (pure link building, contact lookup,
and the /teams-ping page on a temp DB)."""
import pytest

from app import database, teams_link
import app.web_teams as web_teams
from app.web import app


# ---------------------------------------------------------------------------
# link building (pure)
# ---------------------------------------------------------------------------

def test_single_recipient_link_encodes_message():
    url = teams_link.build_chat_link("bernd.h@company.com",
                                     "Hi Bernd, update on 'B2B & retest'?")
    assert url.startswith("https://teams.microsoft.com/l/chat/0/0?users=bernd.h@company.com")
    assert "&message=Hi%20Bernd%2C%20update%20on%20%27B2B%20%26%20retest%27%3F" in url
    assert "topicName" not in url          # 1:1 chats have no topic


def test_group_link_supports_multiple_emails_and_chat_name():
    url = teams_link.build_chat_link(" a@x.com , b@x.com ", "hello",
                                     chat_name="Voucher chase")
    assert "users=a@x.com,b@x.com" in url
    assert "&topicName=Voucher%20chase" in url


def test_default_message_uses_first_name_and_topic():
    msg = teams_link.default_message("Bernd Homner", "B2B retest")
    assert msg == "Hi Bernd, do you have an update on 'B2B retest'?"
    # custom template from config
    msg = teams_link.default_message("Bernd Homner", "B2B retest",
                                     template="Hallo {name}, gibt es Neuigkeiten zu {topic}?")
    assert msg == "Hallo Bernd, gibt es Neuigkeiten zu B2B retest?"


# ---------------------------------------------------------------------------
# contact email lookup + page (temp DB)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "teams.db"
    conn = database.init_db(db_path)
    database.create_contact(conn, name="Bernd Homner",
                            email="bernd.homner@company.com, alt@company.com",
                            area=None, topic=None, comments=None, tags=None)
    fid = database.add_followup(conn, with_whom="Bernd", topic="B2B retest",
                                when_next="2026-07-05", group_name=None)
    conn.close()
    monkeypatch.setattr(web_teams, "_db_path", db_path)
    c = app.test_client()
    c.fid = fid
    c.db_path = db_path
    return c


def test_find_contact_email_matches_partially(client):
    conn = database.get_connection(client.db_path)
    try:
        # follow-up says "Bernd", contact is "Bernd Homner" — must match,
        # and only the FIRST address of a multi-address field is used
        assert database.find_contact_email(conn, "Bernd") == "bernd.homner@company.com"
        assert database.find_contact_email(conn, "nobody") is None
    finally:
        conn.close()


def test_ping_page_prefills_email_and_message(client):
    r = client.get(f"/teams-ping/followup/{client.fid}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'value="bernd.homner@company.com"' in html
    assert "do you have an update on &#39;B2B retest&#39;?" in html


def test_ping_page_404_for_unknown_followup(client):
    assert client.get("/teams-ping/followup/99999").status_code == 404


def test_save_contact_creates_and_updates(client):
    fid = client.fid
    # new name -> created; next ping page pre-fills it
    r = client.post(f"/teams-ping/followup/{fid}/save-contact",
                    data={"contact_name": "Maria Neu", "email": "maria.neu@x.com, extra@x.com"})
    assert "contact_saved=created" in r.headers["Location"]
    conn = database.get_connection(client.db_path)
    try:
        assert database.find_contact_email(conn, "Maria Neu") == "maria.neu@x.com"
        # existing (partial) name -> email updated, no duplicate created
        client.post(f"/teams-ping/followup/{fid}/save-contact",
                    data={"contact_name": "Bernd", "email": "bernd.new@x.com"})
        assert database.find_contact_email(conn, "Bernd") == "bernd.new@x.com"
        names = [c["name"] for c in database.list_contacts(conn)]
        assert names.count("Bernd Homner") == 1 and "Bernd" not in names
    finally:
        conn.close()


def test_save_contact_rejects_invalid_email(client):
    client.post(f"/teams-ping/followup/{client.fid}/save-contact",
                data={"contact_name": "X", "email": "not-an-email"})
    conn = database.get_connection(client.db_path)
    try:
        assert database.find_contact_email(conn, "X") is None
    finally:
        conn.close()
