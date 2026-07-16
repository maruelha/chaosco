"""Inbox auto-file + incoming buckets (2026-07-16).

[USER decisions]: fields only (no text scanning) · preview-then-confirm ·
targets = jira tickets AND defects · only unambiguous matches move ·
route_to pushes to (contact|link|followup, 'incoming') — sorted manually.
What must hold:
- precedence route_to > jira_id > solman_id > order_number; the first
  PRESENT field decides, no fall-through when it fails
- solman id matching a jira ticket AND a defect = ambiguous = stays
- items without any field are not part of the preview at all
- apply recomputes server-side and moves only the given ids
- incoming notes list per module; filing is fixed to the note's own module
  and validates the target row; delete removes note + attachment rows
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import inbox_autofile as db_af
from app.db import jira as db_jira
import app.web_planning as web_planning
import app.web_reference as web_reference
from app.web import app

JIRA = "S4ECOM-42"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "autofile.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_ecom.init_schema(db_path)
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_planning, "_get_conn",
                        lambda: database.get_connection(db_path))
    conn = database.get_connection(db_path)
    try:
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": JIRA, "solman_id": "8000123", "summary": "SM_Case",
            "comments": []}])
        with conn:
            conn.execute("INSERT INTO defects (defect_id, solman_name, order_number)"
                         " VALUES ('8000999', 'Broken invoice', 'ORD-777')")
            conn.execute("INSERT INTO defects (defect_id, solman_name)"
                         " VALUES ('8000123', 'Same id as jira solman')")
        database.add_order_detail_full(conn, "jira", JIRA, "Sales order", "ORD-42")
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    return c


def _add(conn, heading, **fields):
    return database.add_inbox_item(conn, heading, "body", **fields)


def test_preview_resolution_rules(client):
    conn = database.get_connection(client.db_path)
    try:
        n_jira    = _add(conn, "via jira", jira_id="s4ecom-42")        # case-insens.
        n_ambig   = _add(conn, "ambiguous solman", solman_id="8000123")  # jira + defect
        n_defect  = _add(conn, "via solman defect", solman_id="8000999")
        n_order   = _add(conn, "via order", order_number="ORD-42")
        n_nofall  = _add(conn, "bad jira no fallthrough",
                         jira_id="NOPE-1", order_number="ORD-42")
        n_route   = _add(conn, "a new contact", route_to="contact",
                         jira_id="s4ecom-42")                          # route wins
        _add(conn, "plain note")                                       # no fields

        d = db_af.preview_autofile(conn)
    finally:
        conn.close()

    by_id = {m["note_id"]: m for m in d["movable"]}
    assert by_id[n_jira]["target_type"] == "jira" and by_id[n_jira]["via"] == "jira_id"
    assert "SM_Case" in by_id[n_jira]["label"]
    assert by_id[n_defect] == {"note_id": n_defect, "heading": "via solman defect",
                               "action": "move", "target_type": "defect",
                               "target_id": "8000999",
                               "label": "8000999 — Broken invoice", "via": "solman_id"}
    assert by_id[n_order]["target_id"] == JIRA and by_id[n_order]["via"] == "order_number"
    assert by_id[n_route]["target_id"] == "incoming" and by_id[n_route]["via"] == "route"

    skipped = {s["note_id"]: s["reason"] for s in d["skipped"]}
    assert "ambiguous — 2 matches" in skipped[n_ambig]
    assert "no match for jira_id" in skipped[n_nofall]     # no fall-through
    # the plain note appears nowhere
    all_ids = set(by_id) | set(skipped)
    assert len(all_ids) == 6


def test_apply_moves_only_selected_and_recomputes(client):
    conn = database.get_connection(client.db_path)
    try:
        n1 = _add(conn, "to jira", jira_id=JIRA)
        n2 = _add(conn, "to contacts", route_to="contact")
        n3 = _add(conn, "stays", jira_id=JIRA)   # not selected
    finally:
        conn.close()

    d = client.post("/inbox/autofile/apply", data={"ids": f"{n1},{n2}"}).get_json()
    assert d["ok"] and d["filed"] == 2 and d["skipped"] == 0

    conn = database.get_connection(client.db_path)
    try:
        assert database.get_note(conn, n1)["entity_type"] == "jira"
        assert database.get_note(conn, n1)["entity_id"] == JIRA
        note2 = database.get_note(conn, n2)
        assert (note2["entity_type"], note2["entity_id"]) == ("contact", "incoming")
        assert database.get_note(conn, n3)["entity_type"] == "input"   # untouched
        assert [i["id"] for i in database.list_inbox_items(conn)] == [n3]
    finally:
        conn.close()


def test_incoming_sorting_and_delete(client):
    conn = database.get_connection(client.db_path)
    try:
        n = _add(conn, "Jose from ECOM", route_to="contact")
        db_af.apply_autofile(conn, [n])
        assert [i["id"] for i in database.list_incoming_notes(conn, "contact")] == [n]
        contact_id = database.create_contact(conn, "Jose", "jose@x.com",
                                             None, None, None, None)["id"]
    finally:
        conn.close()

    # filing is fixed to the note's own module: a wrong/missing target fails
    client.post(f"/incoming-notes/{n}/file", data={"target_id": "99999"})
    conn = database.get_connection(client.db_path)
    try:
        assert database.list_incoming_notes(conn, "contact")  # still incoming
    finally:
        conn.close()

    client.post(f"/incoming-notes/{n}/file", data={"target_id": str(contact_id)})
    conn = database.get_connection(client.db_path)
    try:
        note = database.get_note(conn, n)
        assert (note["entity_type"], note["entity_id"]) == ("contact", str(contact_id))
        assert database.list_incoming_notes(conn, "contact") == []

        n2 = _add(conn, "junk", route_to="link")
        db_af.apply_autofile(conn, [n2])
    finally:
        conn.close()

    client.post(f"/incoming-notes/{n2}/delete")
    conn = database.get_connection(client.db_path)
    try:
        assert database.get_note(conn, n2) is None
    finally:
        conn.close()


def test_pages_render_incoming_sections_and_inbox_fields(client):
    conn = database.get_connection(client.db_path)
    try:
        for route in ("contact", "link", "followup"):
            nid = _add(conn, f"incoming {route}", route_to=route)
            db_af.apply_autofile(conn, [nid])
    finally:
        conn.close()

    for url, marker in (("/contacts", "incoming contact"),
                        ("/links", "incoming link"),
                        ("/followups", "incoming followup")):
        html = client.get(url).get_data(as_text=True)
        assert 'id="incoming-section"' in html and marker in html

    # inbox: fields roundtrip via the add route + chips render
    client.post("/inbox/add", data={"heading": "h", "note": "n",
                                    "jira_id": JIRA, "order_number": "ORD-1",
                                    "solman_id": "S1", "route_to": "followup"})
    html = client.get("/inbox").get_data(as_text=True)
    assert 'id="btn-autofile"' in html and 'id="dlg-autofile"' in html
    assert f"Jira {JIRA}" in html and "Order ORD-1" in html
    assert "SolMan S1" in html and "Follow-ups incoming" in html
