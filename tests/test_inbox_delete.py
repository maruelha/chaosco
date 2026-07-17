"""Inbox delete — pins behavior that already shipped with the inbox module.

Deleting an inbox item removes the note row, its attachment rows AND the
uploaded picture files on disk; the per-attachment ✕ removes just that
attachment (row + file) and keeps the note.
"""
import pytest

from app import database
import app.web_home as web_home
import app.web_reference as web_reference
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "inbox.db"
    database.init_db(db_path).close()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    for mod in (web_home, web_reference):
        monkeypatch.setattr(mod, "_get_conn",
                            lambda: database.get_connection(db_path))
        monkeypatch.setattr(mod, "_UPLOAD_FOLDER", uploads)
    c = app.test_client()
    c.db_path = db_path
    c.uploads = uploads
    return c


def _add_item_with_picture(client, heading="broken order"):
    conn = database.get_connection(client.db_path)
    try:
        database.add_note(conn, "input", "inbox", heading, "see screenshot")
        note_id = database.list_inbox_items(conn)[0]["id"]
        att = database.add_attachment(conn, note_id, "shot1.png", "shot1.png")
    finally:
        conn.close()
    (client.uploads / "shot1.png").write_bytes(b"fake png")
    return note_id, att["id"]


def test_delete_inbox_item_removes_note_attachments_and_files(client):
    note_id, _ = _add_item_with_picture(client)

    resp = client.post(f"/inbox/{note_id}/delete")
    assert resp.status_code == 302

    conn = database.get_connection(client.db_path)
    try:
        assert database.list_inbox_items(conn) == []
        assert database.get_attachments_for_notes(conn, [note_id]) == {note_id: []}
    finally:
        conn.close()
    assert not (client.uploads / "shot1.png").exists()


def test_delete_single_attachment_keeps_the_note(client):
    note_id, att_id = _add_item_with_picture(client)

    resp = client.post(f"/notes/{note_id}/attachments/{att_id}/delete")
    assert resp.status_code == 200 and resp.get_json()["ok"] is True

    conn = database.get_connection(client.db_path)
    try:
        assert len(database.list_inbox_items(conn)) == 1
        assert database.get_attachments_for_notes(conn, [note_id]) == {note_id: []}
    finally:
        conn.close()
    assert not (client.uploads / "shot1.png").exists()
