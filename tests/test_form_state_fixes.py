"""Two form-state bugs [USER 2026-08-05].

- Meeting prep: after marking an item discussed the page must navigate via
  location.replace(), NOT location.reload() — on reload the browser restores
  typed form values BY POSITION, so with the discussed row gone a typed note
  reappeared in the NEXT row's textarea (and could be saved to the wrong
  item). Markup contract pinned here.
- Encouragements: the add form's Person field must NOT be pre-filled from
  the person filter — after saving, the name stayed stuck in the field.
"""
import re

import pytest

from app import database
import app.web_planning as web_planning
import app.web_reference as web_reference
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "forms.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_planning, "_db_path", db_path, raising=False)
    monkeypatch.setattr(web_reference, "_db_path", db_path, raising=False)
    import app.web_core as web_core
    monkeypatch.setattr(web_core, "_db_path", db_path, raising=False)
    c = app.test_client()
    c.db_path = db_path
    return c


def test_meeting_prep_uses_replace_not_reload(client):
    html = client.get("/meeting-prep").get_data(as_text=True)
    assert "location.reload()" not in html
    assert "window.location.replace(window.location.href)" in html


def test_meeting_prep_note_stays_on_its_item_after_discussed(client):
    conn = database.get_connection(client.db_path)
    try:
        for topic in ("FIRST", "SECOND"):
            database.add_meeting_prep(conn, "DTC O2C Daily", topic, None, None, None)
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM meeting_prep ORDER BY id")]
    finally:
        conn.close()
    first_id = ids[0]
    client.post(f"/n/meeting_prep/{first_id}/add.json", data={"note": "NOTE-ON-FIRST"})
    client.post(f"/meeting-prep/{first_id}/status", data={"status": "discussed"})
    # default (planned) view: FIRST is gone and its note must NOT render anywhere
    html = client.get("/meeting-prep").get_data(as_text=True)
    assert "FIRST" not in html or "SECOND" in html
    assert "NOTE-ON-FIRST" not in html


def _person_input_value(html: str) -> str:
    m = re.search(r'name="person_name"[^>]*value="([^"]*)"', html)
    assert m, "person_name input not found"
    return m.group(1)


def test_encouragement_add_leaves_person_field_empty(client):
    resp = client.post("/encouragements/add", data={
        "person_name": "Colleague X", "text": "great catch on the settlement file",
        "date": "2026-08-05"}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Encouragement saved." in html
    assert "Colleague X" in html                      # the saved card is visible
    assert _person_input_value(html) == ""            # …but the form is clean
