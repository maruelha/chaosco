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
