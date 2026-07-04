"""Tests for the email-reports feature (message assembly, standalone
snapshots, recipients CRUD, send flow with SMTP mocked — nothing is ever
actually sent from tests)."""
from email.message import EmailMessage

import pytest

from app import emailer
from app.db import core as db_core
from app.db import email as db_email


# ---------------------------------------------------------------------------
# message assembly
# ---------------------------------------------------------------------------

def test_build_message_has_recipients_subject_and_attachments():
    msg = emailer.build_message(
        "me@gmx.de", ["a@x.com", "b@x.com"], "UAT status reports — 2026-07-04",
        "Hi all,\n...", [("retail_report_2026-07-04.html", "<html>r</html>")])
    assert msg["From"] == "me@gmx.de"
    assert msg["To"] == "a@x.com, b@x.com"
    assert "2026-07-04" in msg["Subject"]
    atts = [p for p in msg.iter_attachments()]
    assert [a.get_filename() for a in atts] == ["retail_report_2026-07-04.html"]
    assert atts[0].get_content_type() == "text/html"


def test_default_texts_use_date_and_selected_reports():
    t = emailer.default_texts("2026-07-08", ["retail", "board"])
    assert t["subject"] == "UAT status reports — 2026-07-08"
    assert "2026-07-08" in t["body"]
    assert "Retail Status Report" in t["body"]
    assert "Requirements Board" in t["body"]
    assert "Spillover" not in t["body"]        # not selected


# ---------------------------------------------------------------------------
# standalone snapshot
# ---------------------------------------------------------------------------

def test_standalone_html_inlines_css_and_strips_scripts():
    page = ('<html><head><link rel="stylesheet" href="/static/style.css"></head>'
            '<body><details class="ui-section"><summary>s</summary>x</details>'
            '<script src="/static/notes.js"></script>'
            '<script>alert(1)</script></body></html>')
    out = emailer.standalone_html(page)
    assert "<script" not in out
    assert 'rel="stylesheet"' not in out
    assert "<style>" in out and ".stat-card" in out   # css inlined
    assert "<details open" in out                      # sections forced open


# ---------------------------------------------------------------------------
# recipients CRUD (temp DB)
# ---------------------------------------------------------------------------

@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "email.db"
    db_core.init_db(db_path).close()
    db_email.init_schema(db_path)
    c = db_core.get_connection(db_path)
    yield c
    c.close()


def test_recipient_crud_and_active_flag(conn):
    db_email.add_recipient(conn, "one@x.com", "One")
    db_email.add_recipient(conn, "two@x.com", None)
    db_email.add_recipient(conn, "one@x.com", "dup")        # UNIQUE -> ignored
    rows = db_email.list_recipients(conn)
    assert [r["email"] for r in rows] == ["one@x.com", "two@x.com"]

    db_email.set_recipient_active(conn, rows[0]["id"], False)
    assert [r["email"] for r in db_email.list_recipients(conn, active_only=True)] == ["two@x.com"]

    db_email.delete_recipient(conn, rows[1]["id"])
    assert len(db_email.list_recipients(conn)) == 1


# ---------------------------------------------------------------------------
# send flow (SMTP mocked)
# ---------------------------------------------------------------------------

class _FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.auth = (user, password)

    def send_message(self, msg):
        _FakeSMTP.sent.append((self.host, self.port, self.auth, msg))


def test_send_message_uses_configured_smtp(monkeypatch):
    monkeypatch.setattr(emailer.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.sent = []
    settings = {"host": "mail.gmx.net", "port": 587,
                "user": "me@gmx.de", "password": "secret"}
    msg = EmailMessage()
    msg["Subject"] = "t"
    emailer.send_message(settings, msg)
    host, port, auth, sent_msg = _FakeSMTP.sent[0]
    assert (host, port) == ("mail.gmx.net", 587)
    assert auth == ("me@gmx.de", "secret")
    assert sent_msg["Subject"] == "t"


def test_smtp_settings_none_without_credentials():
    assert emailer.smtp_settings({}) is None
    assert emailer.smtp_settings({"email_user": "x"}) is None
    s = emailer.smtp_settings({"email_user": "x@gmx.de", "email_password": "p"})
    assert s == {"host": "mail.gmx.net", "port": 587, "user": "x@gmx.de", "password": "p"}
