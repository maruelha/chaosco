"""Meeting prep reports [USER 2026-08-10].

What must hold:
- every meeting type can be reported on, not just DTC O2C Daily
- the agenda + DTC O2C reports use BULLETS, never numbering
- the worksheet is a genuinely self-contained document: it carries the topics,
  one comment box each, and the save/load-JSON + download-HTML logic inline,
  so it still works after being saved to disk (no server, no CDN)
- the worksheet's comment boxes carry the topic id, which is what the JSON
  round-trip matches on
"""
from html import escape

import pytest

from app import database
from app.db import planning as db_planning
import app.web_core as web_core
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "meetings.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_core, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _topic(client, meeting, topic, overall_topic=None, status="planned"):
    conn = database.get_connection(client.db_path)
    try:
        database.add_meeting_prep(conn, meeting, topic, None, None, overall_topic)
        row = database.get_meeting_prep(conn, meeting=meeting)[0]
        if status != "planned":
            database.set_meeting_prep_status(conn, row["id"], status)
        return row["id"]
    finally:
        conn.close()


def test_every_meeting_type_has_report_buttons(client):
    """A report link per meeting — not only the DTC O2C Daily special."""
    html = client.get("/meeting-prep").get_data(as_text=True)
    for meeting in db_planning.MEETING_OPTIONS:
        assert f"meeting={meeting.replace(' ', '+').replace('&', '%26')}" in html \
            or meeting in html, meeting
    # both report kinds are offered per meeting
    assert html.count("Agenda") >= len(db_planning.MEETING_OPTIONS)
    assert html.count("Worksheet") >= len(db_planning.MEETING_OPTIONS)


@pytest.mark.parametrize("meeting", db_planning.MEETING_OPTIONS)
def test_agenda_and_worksheet_render_for_each_meeting(client, meeting):
    # escaped compare: "Sync&Solve" renders as "Sync&amp;Solve"
    topic = f"Topic for {meeting}"
    _topic(client, meeting, topic, "CS Retail")
    for path in ("/meeting-prep/agenda", "/meeting-prep/worksheet"):
        resp = client.get(path, query_string={"meeting": meeting, "status": "planned"})
        assert resp.status_code == 200
        assert escape(topic) in resp.get_data(as_text=True)


def test_agenda_has_no_follow_ups_or_defects(client):
    """The plain report is JUST the sorted topic list."""
    _topic(client, "GPO", "Only a topic", "Orga")
    html = client.get("/meeting-prep/agenda?meeting=GPO").get_data(as_text=True)
    assert "Only a topic" in html
    assert "Defects to Discuss" not in html
    assert "Follow-ups" not in html


def test_reports_use_bullets_not_numbers(client):
    _topic(client, "DTC O2C Daily", "First topic", "CS ECOM")
    _topic(client, "DTC O2C Daily", "Second topic", "CS ECOM")

    for url in ("/meeting-prep/agenda?meeting=DTC+O2C+Daily",
                "/meeting-prep/dtco2c-daily",
                "/meeting-prep/worksheet?meeting=DTC+O2C+Daily"):
        html = client.get(url).get_data(as_text=True)
        assert "bullet" in html, url          # bullet markup present
        assert 'class="item-n"' not in html, url   # the old numbering is gone


def test_clipboard_copy_uses_bullets(client):
    _topic(client, "GPO", "Some topic", "Orga")
    html = client.get("/meeting-prep").get_data(as_text=True)
    assert "'- ' + r.topic" in html            # bullet, not "idx + '. '"
    assert "idx + '. '" not in html


def test_worksheet_is_self_contained_and_has_comment_boxes(client):
    tid = _topic(client, "Balazs", "Discuss the retrofit", "ROE Retail")
    html = client.get("/meeting-prep/worksheet?meeting=Balazs").get_data(as_text=True)

    # one comment box per topic, carrying the id the JSON matches on
    assert 'class="ws-comment"' in html
    assert f'data-id="{tid}"' in html
    assert "Discuss the retrofit" in html

    # save / load / download all implemented inline
    for fn in ("function wsSaveJson", "function wsLoadJson", "function wsDownloadHtml"):
        assert fn in html
    # …and nothing is fetched from outside (it must work off a local file)
    assert "fetch(" not in html
    assert "http://" not in html and "https://" not in html


def test_worksheet_respects_meeting_and_status_filters(client):
    _topic(client, "GPO", "Planned one", "Orga")
    _topic(client, "GPO", "Parked one", "Orga", status="future")
    _topic(client, "Balazs", "Other meeting topic", "Orga")

    html = client.get("/meeting-prep/worksheet?meeting=GPO&status=planned").get_data(as_text=True)
    assert "Planned one" in html
    assert "Parked one" not in html
    assert "Other meeting topic" not in html


def test_worksheet_groups_by_overall_topic(client):
    _topic(client, "GPO", "Retail thing", "CS Retail")
    _topic(client, "GPO", "Orga thing", "Orga")
    html = client.get("/meeting-prep/worksheet?meeting=GPO").get_data(as_text=True)
    # section headers exist and CS Retail comes before Orga (registry order)
    assert html.index("CS Retail") < html.index("Orga")


def test_worksheet_with_no_items_still_renders(client):
    resp = client.get("/meeting-prep/worksheet?meeting=GPO")
    assert resp.status_code == 200
    assert "No items match" in resp.get_data(as_text=True)
