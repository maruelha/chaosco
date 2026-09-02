"""Working-notes pages (2026-09-01 [USER: "another page like the ways of
working ... can we build so we dont duplicate"]): singleton notes pages
from ONE registry (app/note_pages.PAGES) — generic route pair, shared
notes component, one inbox target type, dated download. Adding a page is
a registry entry + a button, nothing else."""
import pytest

from app import database
from app.note_pages import PAGES
import app.web_core as web_core
import app.web_note_pages as web_note_pages
import app.web_notes as web_notes
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "np.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_note_pages, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    monkeypatch.setattr(web_core, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def test_registry_serves_every_page(client):
    for slug, page in PAGES.items():
        html = client.get(f"/notes-page/{slug}").get_data(as_text=True)
        assert page["title"] in html
        assert page["subtitle"].split(" — ")[0][:30] in html


def test_unknown_slug_404s(client):
    assert client.get("/notes-page/nonsense").status_code == 404
    assert client.get("/notes-page/nonsense/download").status_code == 404
    # the generic notes routes 404 on an unknown page too
    assert client.post("/n/note_page/nonsense/add",
                       data={"note": "x"}).status_code == 404


def test_notes_roundtrip_stays_on_its_page(client):
    resp = client.post("/n/note_page/testing_insights/add", data={
        "heading": "Settlement quirk",
        "note": "Batch runs only pick up orders saved before 16:00."})
    assert resp.status_code == 302
    assert "/notes-page/testing_insights" in resp.headers["Location"]

    html = client.get("/notes-page/testing_insights").get_data(as_text=True)
    assert "Settlement quirk" in html and "before 16:00" in html
    # pages are separate threads — the note does NOT bleed into WoW
    html = client.get("/notes-page/delegated_wow").get_data(as_text=True)
    assert "Settlement quirk" not in html


def test_download_is_a_dated_standalone_snapshot(client):
    client.post("/n/note_page/testing_insights/add",
                data={"heading": "H", "note": "insight body"})
    resp = client.get("/notes-page/testing_insights/download")
    assert resp.status_code == 200
    assert 'attachment; filename="testing_insights_' \
        in resp.headers["Content-Disposition"]
    snap = resp.get_data(as_text=True)
    assert "insight body" in snap


def test_wow_notes_migrate_from_the_old_entity(client, tmp_path):
    """The stand-alone /delegated/wow page's notes lived at
    ('delegated_wow','main'); the db/core migration moves them to
    ('note_page','delegated_wow') so nothing is lost."""
    conn = database.get_connection(client.db_path)
    try:
        conn.execute(
            "INSERT INTO notes (entity_type, entity_id, heading, note, created_at)"
            " VALUES ('delegated_wow', 'main', 'Daily 2026-09-01',"
            " 'Orders are always tagged with the market.', '2026-09-01T09:00:00')")
        conn.commit()
    finally:
        conn.close()
    database.init_db(client.db_path).close()   # migrations re-run, idempotent
    html = client.get("/notes-page/delegated_wow").get_data(as_text=True)
    assert "Daily 2026-09-01" in html
    assert "tagged with the market" in html


def test_pages_are_one_inbox_filing_target(client):
    conn = database.get_connection(client.db_path)
    try:
        # the picker's search lists every page on an empty query
        targets = database.search_targets(conn, "note_page", "")
        assert {t["value"] for t in targets} == set(PAGES)
        # and narrows by title
        targets = database.search_targets(conn, "note_page", "insight")
        assert [t["value"] for t in targets] == ["testing_insights"]

        note_id = database.add_inbox_item(
            conn, "Observed while testing", "returns need the R-flag")
        assert database.file_inbox_item(
            conn, note_id, "note_page", "nonsense") is False
        assert database.file_inbox_item(
            conn, note_id, "note_page", "testing_insights") is True
        assert database.count_inbox_items(conn) == 0   # moved, not copied
        database.add_inbox_item(conn, "still unfiled", "second item")
    finally:
        conn.close()
    html = client.get("/notes-page/testing_insights").get_data(as_text=True)
    assert "Observed while testing" in html
    # the inbox type picker offers the ONE type (no per-page options)
    inbox = client.get("/inbox").get_data(as_text=True)
    assert 'value="note_page"' in inbox
    assert 'value="delegated_wow"' not in inbox


# ---------------------------------------------------------------------------
# Sustain Meeting Summaries (2026-09-01 [USER]): heading_mode='date' — the
# heading is ONLY a date picker (prefilled with today), notes sort by that
# date (newest first), and same-date-twice is fine.

def test_meeting_summaries_button_on_sustain_card(client, monkeypatch):
    import app.web_sustain as web_sustain
    monkeypatch.setattr(web_sustain, "_get_conn",
                        lambda: database.get_connection(client.db_path))
    from app.db import sustain as db_sustain
    from app.db import sustain_callouts as db_sc
    db_sustain.init_schema(client.db_path)
    db_sc.init_schema(client.db_path)
    html = client.get("/sustain/").get_data(as_text=True)
    assert "Meeting summaries" in html
    assert "/notes-page/sustain_meeting_summaries" in html
    # [USER 2026-09-02] the sustain Ways of Working page — free-text headings
    assert "/notes-page/sustain_wow" in html
    page = client.get("/notes-page/sustain_wow").get_data(as_text=True)
    assert "Ways of Working" in page and "Core South Sustainphase Monitoring" in page


def test_add_form_shows_a_date_picker_prefilled_with_today(client):
    from datetime import date
    html = client.get("/n/note_page/sustain_meeting_summaries/add").get_data(as_text=True)
    assert 'type="date"' in html
    assert f'value="{date.today().isoformat()}"' in html
    assert 'name="heading"' in html
    # the free-text heading path is untouched for a non-date page
    html = client.get("/n/note_page/testing_insights/add").get_data(as_text=True)
    assert 'type="date"' not in html


def test_add_and_edit_roundtrip_with_a_chosen_date(client, tmp_path):
    resp = client.post("/n/note_page/sustain_meeting_summaries/add", data={
        "heading": "2026-08-15", "note": "Discussed the France returns backlog."})
    assert resp.status_code == 302
    html = client.get("/notes-page/sustain_meeting_summaries").get_data(as_text=True)
    assert "2026-08-15" in html and "France returns backlog" in html

    conn = database.get_connection(client.db_path)
    try:
        note_id = conn.execute(
            "SELECT id FROM notes WHERE entity_type='note_page'"
            " AND entity_id='sustain_meeting_summaries'").fetchone()[0]
    finally:
        conn.close()
    edit_html = client.get(
        f"/n/note_page/sustain_meeting_summaries/{note_id}/edit").get_data(as_text=True)
    assert 'type="date"' in edit_html
    assert 'value="2026-08-15"' in edit_html    # the CHOSEN date, not today


def test_same_date_twice_is_fine_and_sorts_newest_meeting_first(client):
    client.post("/n/note_page/sustain_meeting_summaries/add",
               data={"heading": "2026-08-10", "note": "Older meeting."})
    client.post("/n/note_page/sustain_meeting_summaries/add",
               data={"heading": "2026-08-20", "note": "Newer meeting, pasted first."})
    client.post("/n/note_page/sustain_meeting_summaries/add",
               data={"heading": "2026-08-20", "note": "Second meeting the same day."})
    html = client.get("/notes-page/sustain_meeting_summaries").get_data(as_text=True)
    # sorted by the DATE in the heading, not by save order: 08-20 notes first
    pos_10 = html.index("Older meeting")
    pos_20a = html.index("Newer meeting, pasted first")
    pos_20b = html.index("Second meeting the same day")
    assert pos_20a < pos_10 and pos_20b < pos_10
    # both same-date notes are present — a duplicate date is not rejected
    assert "Newer meeting, pasted first" in html
    assert "Second meeting the same day" in html


def test_note_page_shows_a_keyword_filter_box(client):
    client.post("/n/note_page/testing_insights/add",
               data={"heading": "H", "note": "settlement retry logic"})
    html = client.get("/notes-page/testing_insights").get_data(as_text=True)
    assert 'id="note-filter-input"' in html
    assert 'id="note-filter-count"' in html
    # no notes yet on a fresh page -> no filter box (nothing to search)
    html = client.get("/notes-page/delegated_wow").get_data(as_text=True)
    assert 'id="note-filter-input"' not in html
