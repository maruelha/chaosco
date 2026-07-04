"""Functional tests for the generic note routes (refactoring step 3).

Exercises the ONE add/edit/delete route set that serves every entity type,
against a temporary database (web_notes._db_path is monkeypatched, so the
live DB is never touched).
"""
import pytest

from app import database
import app.web_notes as web_notes
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "notes_test.db"
    conn = database.init_db(db_path)
    shelf_id = database.create_shelf_item(conn, heading="Scratch item",
                                          area=None, category=None)
    conn.close()
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    c = app.test_client()
    c.shelf_id = shelf_id
    c.db_path = db_path
    return c


def _notes(db_path):
    conn = database.get_connection(db_path)
    try:
        return database.list_notes(conn, "shelf", "1")
    finally:
        conn.close()


def test_add_form_renders(client):
    r = client.get(f"/n/shelf/{client.shelf_id}/add")
    assert r.status_code == 200
    assert b"Scratch item" in r.data          # entity label from the registry


def test_add_edit_delete_roundtrip(client):
    sid = client.shelf_id
    # add
    r = client.post(f"/n/shelf/{sid}/add", data={"heading": "H1", "note": "first note"})
    assert r.status_code == 302
    assert f"/shelf/{sid}?note_added=1" in r.headers["Location"]
    notes = _notes(client.db_path)
    assert len(notes) == 1 and notes[0]["note"] == "first note"
    note_id = notes[0]["id"]

    # edit
    r = client.post(f"/n/shelf/{sid}/{note_id}/edit",
                    data={"heading": "H1", "note": "edited"})
    assert r.status_code == 302 and "note_saved=1" in r.headers["Location"]
    assert _notes(client.db_path)[0]["note"] == "edited"

    # delete (GET = confirm page, POST = do it)
    assert client.get(f"/n/shelf/{sid}/{note_id}/delete").status_code == 200
    r = client.post(f"/n/shelf/{sid}/{note_id}/delete")
    assert r.status_code == 302 and "note_deleted=1" in r.headers["Location"]
    assert _notes(client.db_path) == []


def test_empty_note_is_rejected_not_silently_dropped(client):
    r = client.post(f"/n/shelf/{client.shelf_id}/add", data={"heading": "", "note": "  "})
    assert r.status_code == 200                       # re-rendered form, no redirect
    assert b"required" in r.data
    assert _notes(client.db_path) == []


def test_quick_add_next_redirect(client):
    # list-page quick-adds pass `next` and land back where they came from
    r = client.post(f"/n/shelf/{client.shelf_id}/add",
                    data={"note": "quick", "next": "/shelf"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/shelf?note_added=1")


def test_unknown_entity_type_404s(client):
    assert client.get("/n/nonsense/1/add").status_code == 404


def test_note_entity_mismatch_404s(client):
    sid = client.shelf_id
    client.post(f"/n/shelf/{sid}/add", data={"note": "mine"})
    note_id = _notes(client.db_path)[0]["id"]
    # the same note id must not be editable through another entity's URL
    assert client.get(f"/n/defect/XYZ/{note_id}/edit").status_code == 404
