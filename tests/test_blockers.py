"""Blockers (build plan step 7, 2026-08-27): storage (types, clarification
never carries a jira key), list/detail pages, notes thread, and live Jira
status/comments when the blocker's key is already in the shared store."""
import pytest

from app import database
from app.db import blockers as db_blockers
from app.db import jira as db_jira
import app.web_blockers as web_blockers
import app.web_notes as web_notes
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "blockers.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_blockers.init_schema(db_path)
    monkeypatch.setattr(web_blockers, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    return app.test_client(), db_path


# ---------------------------------------------------------------------------
# Storage

def test_create_blocker_strips_jira_key_for_clarification(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.create_blocker(conn, "clarification", "Orders open question",
                                         jira_key="S4ECOM-9999")
        assert row["jira_key"] is None
        defect = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
        assert defect["jira_key"] == "S4DEF-1"
    finally:
        conn.close()


def test_list_blockers_ordered_defect_task_clarification(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        db_blockers.create_blocker(conn, "clarification", "Zeta clarification", None)
        db_blockers.create_blocker(conn, "task", "Alpha task", None)
        db_blockers.create_blocker(conn, "defect", "Beta defect", "S4DEF-1")
        rows = db_blockers.list_blockers(conn)
        assert [r["type"] for r in rows] == ["defect", "task", "clarification"]
    finally:
        conn.close()


def test_list_blocker_jira_keys(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        db_blockers.create_blocker(conn, "defect", "Beta defect", "S4DEF-1")
        db_blockers.create_blocker(conn, "clarification", "No key here", "ignored-anyway")
        assert db_blockers.list_blocker_jira_keys(conn) == {"S4DEF-1"}
    finally:
        conn.close()


def test_list_blocker_jira_keys_tolerates_missing_table(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()  # blockers table never created
    conn = database.get_connection(db_path)
    try:
        assert db_blockers.list_blocker_jira_keys(conn) == set()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Web

def test_list_page_groups_by_type(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
        db_blockers.create_blocker(conn, "task", "Backfill master data", None)
        db_blockers.create_blocker(conn, "clarification", "Orders open question", None)
    finally:
        conn.close()
    html = c.get("/blockers/").get_data(as_text=True)
    assert "Defects" in html and "Tasks" in html and "Business Clarifications" in html
    assert "Pricing bug" in html
    assert "S4DEF-1" in html
    assert "Backfill master data" in html
    assert "Orders open question" in html


def test_add_blocker_via_form(client):
    c, db_path = client
    resp = c.post("/blockers/new", data={
        "type": "defect", "name": "Pricing bug", "jira_key": "S4DEF-1"})
    assert resp.status_code == 302
    conn = database.get_connection(db_path)
    try:
        rows = db_blockers.list_blockers(conn)
    finally:
        conn.close()
    assert len(rows) == 1 and rows[0]["name"] == "Pricing bug"


def test_add_blocker_requires_type_and_name(client):
    c, _db_path = client
    resp = c.post("/blockers/new", data={"type": "", "name": ""})
    assert resp.status_code == 200
    assert "Pick a type and enter a name." in resp.get_data(as_text=True)


def test_edit_blocker(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.create_blocker(conn, "task", "Old name", None)
    finally:
        conn.close()
    resp = c.post(f"/blockers/{row['blocker_id']}", data={
        "type": "task", "name": "New name", "jira_key": ""})
    assert resp.status_code == 302
    conn = database.get_connection(db_path)
    try:
        updated = db_blockers.get_blocker(conn, row["blocker_id"])
    finally:
        conn.close()
    assert updated["name"] == "New name"


def test_detail_404_for_unknown_id(client):
    c, _db_path = client
    assert c.get("/blockers/999").status_code == 404


def test_detail_shows_live_jira_status_and_comments(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": "S4DEF-1", "summary": "Pricing calculates wrong",
            "jira_status": "In Progress", "jira_assignee": "Dev, D.",
            "comments": [{"created": "2026-08-20", "body": "still investigating"}],
        }], seen_in="delegated")
        row = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
    finally:
        conn.close()
    html = c.get(f"/blockers/{row['blocker_id']}").get_data(as_text=True)
    assert "In Progress" in html
    assert "still investigating" in html


def test_detail_shows_hint_when_jira_key_not_in_store_yet(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-9")
    finally:
        conn.close()
    html = c.get(f"/blockers/{row['blocker_id']}").get_data(as_text=True)
    assert "not in the shared Jira store yet" in html


def test_notes_work_via_registry(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.create_blocker(conn, "task", "Backfill master data", None)
    finally:
        conn.close()
    resp = c.post(f"/n/blocker/{row['blocker_id']}/add",
                  data={"heading": "", "note": "waiting on GBS"})
    assert resp.status_code == 302
    html = c.get(f"/blockers/{row['blocker_id']}").get_data(as_text=True)
    assert "waiting on GBS" in html


# ---------------------------------------------------------------------------
# Exclusion from the delegated board (web_delegated._load_issues)

def test_registered_blocker_excluded_from_delegated_board(client, monkeypatch):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        db_jira.upsert_jira_issues(conn, [
            {"jira_key": "S4ECOM-1", "summary": "Normal test ticket",
             "jira_status": "Open", "jira_assignee": "Tester, T."},
            {"jira_key": "S4DEF-1", "summary": "The blocking defect",
             "jira_status": "In Progress", "jira_assignee": "Dev, D."},
        ], seen_in="delegated")
        db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
    finally:
        conn.close()
    import app.web_delegated as web_delegated
    monkeypatch.setattr(web_delegated, "_get_conn",
                        lambda: database.get_connection(db_path))
    html = c.get("/delegated/").get_data(as_text=True)
    assert "S4ECOM-1" in html
    assert "S4DEF-1" not in html


# ---------------------------------------------------------------------------
# Attach to tickets (build plan step 8) — blocker_links picker routes

def test_links_json_lists_linked_and_available(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        b1 = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
        db_blockers.create_blocker(conn, "task", "Backfill master data", None)
        db_blockers.link_blocker(conn, b1["blocker_id"], "S4ECOM-1")
    finally:
        conn.close()
    data = c.get("/blockers/links/S4ECOM-1").get_json()
    assert [b["name"] for b in data["linked"]] == ["Pricing bug"]
    assert [b["name"] for b in data["available"]] == ["Backfill master data"]


def test_attach_and_detach_blocker(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        b1 = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
    finally:
        conn.close()
    resp = c.post("/blockers/links/S4ECOM-1/attach",
                  data={"blocker_id": b1["blocker_id"]})
    data = resp.get_json()
    assert data["ok"] and [b["name"] for b in data["linked"]] == ["Pricing bug"]

    resp = c.post("/blockers/links/S4ECOM-1/detach",
                  data={"blocker_id": b1["blocker_id"]})
    data = resp.get_json()
    assert data["ok"] and data["linked"] == []


def test_quick_create_and_attach(client):
    c, db_path = client
    resp = c.post("/blockers/links/S4ECOM-1/quick-create",
                  data={"type": "defect", "name": "New defect", "jira_key": "S4DEF-9"})
    data = resp.get_json()
    assert data["ok"]
    assert [b["name"] for b in data["linked"]] == ["New defect"]
    conn = database.get_connection(db_path)
    try:
        rows = db_blockers.list_blockers(conn)
    finally:
        conn.close()
    assert len(rows) == 1 and rows[0]["jira_key"] == "S4DEF-9"


def test_quick_create_requires_type_and_name(client):
    c, _db_path = client
    resp = c.post("/blockers/links/S4ECOM-1/quick-create",
                  data={"type": "", "name": ""})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_blocked_ticket_counts(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        b1 = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
        db_blockers.link_blocker(conn, b1["blocker_id"], "S4ECOM-1")
        db_blockers.link_blocker(conn, b1["blocker_id"], "S4ECOM-2")
        assert db_blockers.blocked_ticket_counts(conn) == {b1["blocker_id"]: 2}
    finally:
        conn.close()
