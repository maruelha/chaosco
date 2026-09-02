"""Inbox → Sustain call-out (planning chat 2026-09-02 [USER]): an inbox
note can be pushed under a call-out — either an EXISTING one (standard
filing picker, target type 'sustain_callout', searched by name or ticket
no) or a NEW one created from the note (small channel/type/name/ticket
picker, name defaulting to the note heading; same shape as file-to-shelf).
Either way the note then shows on the call-out's detail page."""
import pytest

from app import database
from app.db import next_steps as db_ns
from app.db import sustain as db_sustain
from app.db import sustain_callouts as db_sc
import app.web_notes as web_notes
import app.web_reference as web_reference
import app.web_sustain as web_sustain
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "inbox.db"
    database.init_db(db_path).close()
    db_sustain.init_schema(db_path)
    db_sc.init_schema(db_path)
    db_ns.init_schema(db_path)
    for mod in (web_reference, web_sustain):
        monkeypatch.setattr(mod, "_get_conn",
                            lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _inbox_item(client, heading="Adyen payout differs", text="seen on the 1st"):
    conn = database.get_connection(client.db_path)
    try:
        database.add_note(conn, "input", "inbox", heading, text)
        return database.list_inbox_items(conn)[0]["id"]
    finally:
        conn.close()


def _callout(client, name, **kw):
    conn = database.get_connection(client.db_path)
    try:
        return db_sc.create_callout(conn, kw.pop("channel", "retail"),
                                    kw.pop("type_", "Issue"), name, **kw)
    finally:
        conn.close()


def _callout_notes(client, callout_id):
    conn = database.get_connection(client.db_path)
    try:
        return database.list_notes(conn, "sustain_callout", str(callout_id))
    finally:
        conn.close()


def test_targets_search_finds_callouts_by_name_and_ticket(client):
    a = _callout(client, "Settlement mismatch", ticket_no="SUS-017")
    b = _callout(client, "Prices wrong", channel="ecom", type_="MigrIssue")
    conn = database.get_connection(client.db_path)
    try:
        db_sc.set_status(conn, b, "closed")
    finally:
        conn.close()

    by_name = client.get("/inbox/targets?type=sustain_callout&q=settle").get_json()
    assert [r["value"] for r in by_name] == [str(a)]
    assert "SUS-017" in by_name[0]["label"] and "Settlement mismatch" in by_name[0]["label"]

    by_ticket = client.get("/inbox/targets?type=sustain_callout&q=sus-0").get_json()
    assert [r["value"] for r in by_ticket] == [str(a)]

    everything = client.get("/inbox/targets?type=sustain_callout&q=").get_json()
    assert [r["value"] for r in everything] == [str(a), str(b)]   # open first
    assert "closed" in everything[1]["label"]


def test_file_under_existing_callout(client):
    cid = _callout(client, "Settlement mismatch")
    note_id = _inbox_item(client)
    resp = client.post(f"/inbox/{note_id}/file",
                       data={"target_type": "sustain_callout", "target_id": str(cid)})
    assert resp.status_code == 302 and "note_filed=sustain_callout" in resp.headers["Location"]
    notes = _callout_notes(client, cid)
    assert [n["heading"] for n in notes] == ["Adyen payout differs"]
    conn = database.get_connection(client.db_path)
    try:
        assert database.count_inbox_items(conn) == 0
    finally:
        conn.close()
    html = client.get(f"/sustain/callouts/{cid}").get_data(as_text=True)
    assert "seen on the 1st" in html


def test_file_under_unknown_callout_is_refused(client):
    note_id = _inbox_item(client)
    client.post(f"/inbox/{note_id}/file",
                data={"target_type": "sustain_callout", "target_id": "999"})
    conn = database.get_connection(client.db_path)
    try:
        assert database.count_inbox_items(conn) == 1
    finally:
        conn.close()


def test_new_callout_from_note_takes_picker_fields_and_files_the_note(client):
    note_id = _inbox_item(client)
    resp = client.post(f"/inbox/{note_id}/file-to-callout", data={
        "callout_channel": "ecom", "callout_type": "MigrIssue",
        "callout_name": "Adyen payout mismatch", "callout_ticket_no": "SUS-020"})
    assert resp.status_code == 302 and "Sustain" in resp.headers["Location"]
    conn = database.get_connection(client.db_path)
    try:
        items = db_sc.list_callouts(conn)
        assert database.count_inbox_items(conn) == 0
    finally:
        conn.close()
    assert len(items) == 1
    c = items[0]
    assert (c["channel"], c["type"], c["name"], c["ticket_no"]) == \
        ("ecom", "MigrIssue", "Adyen payout mismatch", "SUS-020")
    assert c["topic"] == "Adyen payout mismatch"     # mirrors name until edited
    assert [n["note"] for n in _callout_notes(client, c["id"])] == ["seen on the 1st"]
    html = client.get(f"/sustain/callouts/{c['id']}").get_data(as_text=True)
    assert "seen on the 1st" in html and "SUS-020" in html


def test_new_callout_name_defaults_to_heading_then_first_note_line(client):
    heading_id = _inbox_item(client, heading="From the heading")
    client.post(f"/inbox/{heading_id}/file-to-callout",
                data={"callout_channel": "retail", "callout_type": "Issue"})
    text_only = _inbox_item(client, heading=None, text="first line wins\nsecond line")
    client.post(f"/inbox/{text_only}/file-to-callout",
                data={"callout_channel": "retail", "callout_type": "Issue"})
    conn = database.get_connection(client.db_path)
    try:
        names = sorted(c["name"] for c in db_sc.list_callouts(conn))
    finally:
        conn.close()
    assert names == ["From the heading", "first line wins"]


def test_inbox_page_offers_the_callout_target_and_the_new_callout_form(client):
    note_id = _inbox_item(client, heading="Adyen payout differs")
    html = client.get("/inbox").get_data(as_text=True)
    assert '<option value="sustain_callout">Sustain call-out</option>' in html
    assert f'id="callout-new-{note_id}"' in html
    assert f'action="/inbox/{note_id}/file-to-callout"' in html
    assert 'name="callout_name" class="form-control" value="Adyen payout differs"' in html
    for t in db_sc.CALLOUT_TYPES:
        assert f'<option value="{t}">{t}</option>' in html
