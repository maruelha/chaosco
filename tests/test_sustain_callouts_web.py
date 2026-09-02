"""Sustain Call-outs (build plan steps 2-3, 2026-09-01): routes + the
card-page section — add, cycling status chip, edit, delete, show/hide
closed, next step (inline save + generic /next-steps archive) and notes
(generic /n/sustain_callout/... routes)."""
import pytest

from app import database
from app.db import next_steps as db_ns
from app.db import sustain as db_sustain
from app.db import sustain_callouts as db_sc
import app.web_next_steps as web_next_steps
import app.web_notes as web_notes
import app.web_sustain as web_sustain
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sc.db"
    database.init_db(db_path).close()
    db_sustain.init_schema(db_path)
    db_sc.init_schema(db_path)
    db_ns.init_schema(db_path)
    monkeypatch.setattr(web_sustain, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_next_steps, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _add(client, **fields):
    data = {"channel": "retail", "type": "Issue", "name": "Something to check"}
    data.update(fields)
    return client.post("/sustain/callouts/add", data=data)


def test_home_shows_call_outs_section(client):
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Call-outs" in html


def test_add_shows_up_on_card(client):
    _add(client, name="Settlement mismatch", responsible="Marina")
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Settlement mismatch" in html
    assert "Marina" in html


def test_add_without_name_is_rejected(client):
    resp = _add(client, name="  ")
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


def _first_id(client, tmp_path):
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        return db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()


def test_update_changes_fields(client, tmp_path):
    """The full-row save lives on the detail page since 2026-09-02 (the
    list's inline edit row is gone)."""
    _add(client, name="Original")
    cid = _first_id(client, tmp_path)
    resp = client.post(f"/sustain/callouts/{cid}", data={
        "channel": "ecom", "type": "MigrIssue", "name": "Updated name",
        "topic": "The long story", "ticket_no": "SUS-003",
        "impact": "Refunds delayed", "responsible": "Someone",
    })
    assert resp.status_code == 302 and "saved=1" in resp.headers["Location"]
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Updated name" in html
    assert "Original" not in html
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        item = db_sc.get_callout(conn, cid)
    finally:
        conn.close()
    assert item["topic"] == "The long story"
    assert item["ticket_no"] == "SUS-003"
    assert item["impact"] == "Refunds delayed"
    assert item["responsible"] == "Someone"


# ---------------------------------------------------------------------------
# Detail page (planning chat 2026-09-02): topic / ticket no / impact live
# here, list shows only the short name

def test_add_form_asks_for_name_and_ticket_and_the_list_shows_the_ticket(client, tmp_path):
    """Step 3 (2026-09-02): the quick-add form on the list takes name +
    ticket no (topic/impact live on the detail page); the list gets a
    Ticket column and the name links to the detail page."""
    _add(client, name="Settlement mismatch", ticket_no="SUS-042")
    cid = _first_id(client, tmp_path)
    html = client.get("/sustain/").get_data(as_text=True)
    assert 'name="name"' in html and 'name="ticket_no"' in html
    assert 'name="topic"' not in html
    assert "<th>Name</th><th>Ticket</th>" in html
    assert "SUS-042" in html
    assert f'<a href="/sustain/callouts/{cid}">Settlement mismatch</a>' in html
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        item = db_sc.get_callout(conn, cid)
    finally:
        conn.close()
    assert item["ticket_no"] == "SUS-042"
    assert item["topic"] == "Settlement mismatch"     # mirrors name until edited


def test_filter_bar_renders_with_type_checkboxes_and_rows_carry_filter_data(client, tmp_path):
    """Step 4 (2026-09-02): client-side filter bar — channel/status
    selects, one checkbox per type (combinable), text over name + ticket.
    Rows expose the filter keys as data-* attributes."""
    _add(client, name="Settlement mismatch", ticket_no="SUS-042",
         channel="ecom", type="MigrIssue")
    cid = _first_id(client, tmp_path)
    html = client.get("/sustain/").get_data(as_text=True)
    assert 'id="sc-filter-channel"' in html
    assert 'id="sc-filter-status"' in html
    assert 'id="sc-filter-text"' in html
    for t in db_sc.CALLOUT_TYPES:
        assert f'<input type="checkbox" name="sc-filter-type" value="{t}"' in html
    import re
    row = re.search(rf'<tr class="sc-row" data-id="{cid}"[^>]*>', html, re.S).group()
    assert 'data-channel="ecom"' in row
    assert 'data-type="MigrIssue"' in row
    assert 'data-status="open"' in row
    assert 'data-search="settlement mismatch sus-042"' in row


def test_list_links_to_the_detail_page_and_has_no_inline_edit(client, tmp_path):
    _add(client, name="Settlement mismatch")
    cid = _first_id(client, tmp_path)
    html = client.get("/sustain/").get_data(as_text=True)
    assert f'href="/sustain/callouts/{cid}"' in html
    assert "sc-edit-row" not in html
    assert "/update" not in html


def test_detail_page_shows_every_field_and_the_notes_component(client, tmp_path):
    _add(client, name="Settlement mismatch", responsible="Marina")
    cid = _first_id(client, tmp_path)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        db_sc.update_callout(conn, cid, "ecom", "MigrIssue", "Settlement mismatch",
                             "Marina", topic="Adyen payout differs from SAP",
                             ticket_no="SUS-001", impact="Finance cannot reconcile")
        db_sc.set_callout_next_step(conn, cid, "ask Adyen for the report")
    finally:
        conn.close()
    client.post(f"/n/sustain_callout/{cid}/add.json", data={"note": "phoned Adyen"})

    resp = client.get(f"/sustain/callouts/{cid}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    for text in ("Settlement mismatch", "Adyen payout differs from SAP", "SUS-001",
                 "Finance cannot reconcile", "Marina", "ask Adyen for the report",
                 "phoned Adyen", "Add screenshot", f'id="notes-sustain_callout-{cid}"'):
        assert text in html, text
    assert 'name="ticket_no"' in html and 'name="impact"' in html
    assert 'name="topic"' in html
    assert 'data-entity-type="sustain_callout"' in html     # next-step ↻ / 🕘


def test_detail_page_404s_for_unknown_id(client):
    assert client.get("/sustain/callouts/9999").status_code == 404


def test_detail_save_without_name_is_rejected(client, tmp_path):
    _add(client, name="Keep me")
    cid = _first_id(client, tmp_path)
    resp = client.post(f"/sustain/callouts/{cid}", data={
        "channel": "retail", "type": "Issue", "name": "   ", "topic": "x"})
    assert resp.status_code == 200
    assert "required" in resp.get_data(as_text=True)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        assert db_sc.get_callout(conn, cid)["name"] == "Keep me"
    finally:
        conn.close()


def test_note_added_from_the_detail_page_comes_back_to_it(client, tmp_path):
    _add(client, name="Settlement mismatch")
    cid = _first_id(client, tmp_path)
    resp = client.post(f"/n/sustain_callout/{cid}/add",
                       data={"heading": "Vendor call", "note": "Confirmed by phone"})
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith(f"/sustain/callouts/{cid}?")
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Confirmed by phone" in html and "Note added." in html


def test_note_form_breadcrumb_names_the_callout(client, tmp_path):
    _add(client, name="Settlement mismatch")
    cid = _first_id(client, tmp_path)
    html = client.get(f"/n/sustain_callout/{cid}/add").get_data(as_text=True)
    assert "Settlement mismatch" in html


def test_delete_removes_it(client, tmp_path):
    _add(client, name="Gone soon")
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
    _add(client, name="Will be closed")
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


# ---------------------------------------------------------------------------
# Next step (build plan step 3): inline save, generic /next-steps archive

def test_next_step_save_shows_on_card(client, tmp_path):
    _add(client)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    resp = client.post(f"/sustain/callouts/{cid}/next-step",
                       json={"next_step": "Follow up with the provider"})
    assert resp.get_json() == {"ok": True}
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Follow up with the provider" in html


def test_next_step_archives_via_generic_endpoint(client, tmp_path):
    _add(client)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/sustain/callouts/{cid}/next-step",
               json={"next_step": "Original step"})
    resp = client.post(f"/next-steps/sustain_callout/{cid}/archive")
    assert resp.get_json()["ok"] is True
    assert resp.get_json()["archived"] == "Original step"

    conn = database.get_connection(tmp_path / "sc.db")
    try:
        assert db_sc.get_callout_next_step(conn, cid) is None
    finally:
        conn.close()

    resp = client.get(f"/next-steps/sustain_callout/{cid}/list.json")
    data = resp.get_json()
    assert data["count"] == 1
    assert data["items"][0]["next_step"] == "Original step"


# ---------------------------------------------------------------------------
# Notes (build plan step 3): generic /n/sustain_callout/... JSON endpoints

def test_notes_add_and_list(client, tmp_path):
    _add(client)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()

    resp = client.get(f"/n/sustain_callout/{cid}/list.json")
    assert resp.get_json() == []

    resp = client.post(f"/n/sustain_callout/{cid}/add.json",
                       data={"note": "Checked with the vendor"})
    data = resp.get_json()
    assert data["ok"] is True
    assert len(data["notes"]) == 1
    assert data["notes"][0]["note"] == "Checked with the vendor"

    resp = client.get(f"/n/sustain_callout/{cid}/list.json")
    assert len(resp.get_json()) == 1


def test_note_count_shown_on_card(client, tmp_path):
    _add(client)
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/n/sustain_callout/{cid}/add.json", data={"note": "note one"})
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Notes (1)" in html


def test_board_renders_the_full_shared_notes_component_per_callout(client, tmp_path):
    """2026-09-01 fix: the board used to render a bespoke plain-textarea
    widget with no heading and no attachments — replaced with the SAME
    shared _notes_section.html every other entity uses, one instance per
    call-out row."""
    _add(client, name="Settlement mismatch")
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = db_sc.list_callouts(conn)[0]["id"]
    finally:
        conn.close()
    client.post(f"/n/sustain_callout/{cid}/add.json",
               data={"note": "a note taken before the fix"})

    html = client.get("/sustain/").get_data(as_text=True)
    # the pre-existing note (added via the old quick-add path) survives —
    # nothing is lost by the swap
    assert "a note taken before the fix" in html
    # the full component's markup is present: a heading field on Add, and
    # per-note attachment upload buttons — neither existed in the old widget
    assert f'/n/sustain_callout/{cid}/add' in html
    assert "Add screenshot" in html
    assert "Attach file" in html
    assert f'id="notes-sustain_callout-{cid}"' in html


def test_note_added_via_full_form_shows_up_and_reopens_its_row(client, tmp_path):
    """Adding a note through the real /n/.../add form (heading + text, the
    path that also unlocks attachments) redirects back to the board with
    note_entity=<id> so only THAT call-out's row reopens and shows the
    banner — not every row on the page."""
    _add(client, name="Settlement mismatch")
    _add(client, name="A second, unrelated call-out")
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        ids = [c["id"] for c in db_sc.list_callouts(conn)]
    finally:
        conn.close()
    target_id = ids[0]

    # the list page's "+ Add note" link carries return_to=list (the
    # include's notes_return_to) — without it the add form would land on
    # the call-out's detail page, which exists since 2026-09-02
    list_html = client.get("/sustain/").get_data(as_text=True)
    assert f"/n/sustain_callout/{target_id}/add?return_to=list" in list_html
    resp = client.post(f"/n/sustain_callout/{target_id}/add",
                       data={"heading": "Vendor call", "note": "Confirmed by phone",
                             "return_to": "list"})
    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert location.startswith("/sustain/?")
    assert "note_added=1" in location
    assert f"note_entity={target_id}" in location

    html = client.get(location).get_data(as_text=True)
    assert "Confirmed by phone" in html
    assert "Vendor call" in html          # heading now shown, unlike the old widget
    assert "Note added." in html
    # only the touched row is expanded, the other call-out's row stays closed
    other_id = ids[1]
    import re
    target_row = re.search(rf'<tr class="sc-notes-row" data-id="{target_id}"[^>]*>', html)
    other_row = re.search(rf'<tr class="sc-notes-row" data-id="{other_id}"[^>]*>', html)
    assert "display:none" not in target_row.group()
    assert "display:none" in other_row.group()


# ---------------------------------------------------------------------------
# Management summary (build plan step 4): per-stream Call-outs block

def _import_day(client, day="2026-09-01"):
    """Minimal (day, stream) import via storage — a full workbook parse
    isn't needed, just enough for db_sustain.overview() to return a row
    per stream so the summary page renders its per-stream sections."""
    conn = database.get_connection(client.db_path)
    try:
        for stream in ("Retail", "eCom"):
            db_sustain.replace_day_stream(conn, day, stream, [{
                "excel_row": 1, "task_id": "1", "taxonomy": "Tax",
                "process": "Proc", "cadence": "Daily", "due_today": "No",
                "country": None, "provider": "Adyen",
                "result_fr": None, "result_it": None, "result_pt": None,
                "result_es": None, "overall": None, "details": [],
            }])
    finally:
        conn.close()


def test_summary_shows_open_callouts_for_the_stream(client):
    _import_day(client)
    _add(client, channel="retail", name="Retail-only topic")
    html = client.get("/sustain/summary/2026-09-01").get_data(as_text=True)
    assert "Retail-only topic" in html


def test_summary_channel_both_appears_in_both_streams(client):
    _import_day(client)
    _add(client, channel="both", name="Affects both streams")
    html = client.get("/sustain/summary/2026-09-01").get_data(as_text=True)
    assert html.count("Affects both streams") == 2


def test_summary_hides_closed_and_other_channel_callouts(client, tmp_path):
    _import_day(client)
    _add(client, channel="retail", name="Retail closed one")
    _add(client, channel="ecom", name="Ecom-only topic")
    conn = database.get_connection(tmp_path / "sc.db")
    try:
        cid = [c for c in db_sc.list_callouts(conn)
              if c["topic"] == "Retail closed one"][0]["id"]
    finally:
        conn.close()
    client.post(f"/sustain/callouts/{cid}/status")  # -> in_progress
    client.post(f"/sustain/callouts/{cid}/status")  # -> closed

    html = client.get("/sustain/summary/2026-09-01").get_data(as_text=True)
    assert "Retail closed one" not in html
    # eCom's own topic must not leak into the Retail section
    retail_section = html.split("Retail — 2026-09-01")[1].split("eCom — 2026-09-01")[0]
    assert "Ecom-only topic" not in retail_section
