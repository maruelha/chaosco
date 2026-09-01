"""Blockers (build plan step 7, 2026-08-27): storage (types, clarification
never carries a jira key), list/detail pages, notes thread, and live Jira
status/comments when the blocker's key is already in the shared store."""
import pytest

from app import database
from app.db import blockers as db_blockers
from app.db import jira as db_jira
from app.db import next_steps as db_ns
import app.web_blockers as web_blockers
import app.web_next_steps as web_next_steps
import app.web_notes as web_notes
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "blockers.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_blockers.init_schema(db_path)
    db_ns.init_schema(db_path)
    monkeypatch.setattr(web_blockers, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_notes, "_db_path", db_path)
    monkeypatch.setattr(web_next_steps, "_db_path", db_path)
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


def test_picker_available_excludes_closed_blockers(client):
    """[USER 2026-09-01] A closed blocker (manually closed OR its Jira
    ticket done) must not be offered when attaching to a blocked ticket;
    one that is already attached stays visible in `linked` so its chip
    can still be seen and detached."""
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        open_b = db_blockers.create_blocker(conn, "defect", "Still blocking", None)
        manual = db_blockers.create_blocker(conn, "defect", "Manually closed", None)
        db_blockers.set_blocker_closed(conn, manual["blocker_id"], True)
        jira_done = db_blockers.create_blocker(conn, "defect", "Done in Jira", "S4DEF-77")
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": "S4DEF-77", "summary": "S77_done defect",
            "jira_status": "Resolved"}])
        linked_closed = db_blockers.create_blocker(conn, "task", "Attached then closed", None)
        db_blockers.set_blocker_closed(conn, linked_closed["blocker_id"], True)
        db_blockers.link_blocker(conn, linked_closed["blocker_id"], "S4ECOM-1")
    finally:
        conn.close()
    data = c.get("/blockers/links/S4ECOM-1").get_json()
    assert [b["name"] for b in data["available"]] == ["Still blocking"]
    assert [b["name"] for b in data["linked"]] == ["Attached then closed"]


def test_list_page_inline_fields_opt_out_of_browser_restore(client):
    """[USER 2026-09-01 bug] Closing a blocker shifted every Team/Next step
    value one row down: the browser restores form values BY POSITION on
    reload, and the closed row's removal re-aligned them all. The inline
    controls carry autocomplete=off (and the script navigates fresh instead
    of reloading) so restoration can never cross rows again."""
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
    finally:
        conn.close()
    html = c.get("/blockers/").get_data(as_text=True)
    for marker in ('class="blk-team"', 'blk-impact"', 'blk-ns"'):
        control = html.split(marker, 1)[1][:300]
        assert 'autocomplete="off"' in control, marker
    assert "window.location.reload()" not in html
    assert "location.replace" in html


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


# ---------------------------------------------------------------------------
# 2026-08-27 batch: comment/impact/solman fields, BC ids, open/closed split,
# next-step component, id-only picker labels

def test_comment_impact_solman_round_trip_via_form(client):
    c, db_path = client
    resp = c.post("/blockers/new", data={
        "type": "defect", "name": "Pricing bug", "jira_key": "S4DEF-1",
        "solman_id": "SM12345", "impact": "Blocks all settlement tests",
        "comment": "raised with vendor"})
    assert resp.status_code == 302
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.list_blockers(conn)[0]
        assert row["solman_id"] == "SM12345"
        assert row["impact"] == "Blocks all settlement tests"
        assert row["comment"] == "raised with vendor"
        # edit keeps them updatable
        c.post(f"/blockers/{row['blocker_id']}", data={
            "type": "defect", "name": "Pricing bug", "jira_key": "S4DEF-1",
            "solman_id": "SM99999", "impact": "narrower now", "comment": ""})
        row2 = db_blockers.get_blocker(conn, row["blocker_id"])
        assert row2["solman_id"] == "SM99999"
        assert row2["impact"] == "narrower now"
        assert row2["comment"] is None
    finally:
        conn.close()


def test_solman_stripped_for_clarifications(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.create_blocker(conn, "clarification", "Open question",
                                         None, solman_id="SM123")
        assert row["solman_id"] is None
    finally:
        conn.close()


def test_bc_id_assigned_to_clarifications(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        c1 = db_blockers.create_blocker(conn, "clarification", "First question", None)
        d1 = db_blockers.create_blocker(conn, "defect", "A defect", "S4DEF-1")
        c2 = db_blockers.create_blocker(conn, "clarification", "Second question", None)
        assert c1["display_id"] == "BC-001"
        assert d1["display_id"] is None
        assert c2["display_id"] == "BC-002"
        # a row edited INTO a clarification gets its id
        db_blockers.update_blocker(conn, d1["blocker_id"], "clarification",
                                   "A defect no more", None)
        assert db_blockers.get_blocker(conn, d1["blocker_id"])["display_id"] == "BC-003"
        # ...and keeps it on later edits
        db_blockers.update_blocker(conn, d1["blocker_id"], "clarification",
                                   "renamed", None)
        assert db_blockers.get_blocker(conn, d1["blocker_id"])["display_id"] == "BC-003"
    finally:
        conn.close()


def test_bc_backfill_for_existing_clarifications(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO blockers (type, name, created_at, updated_at, display_id)"
            " VALUES ('clarification', 'Legacy question', '2026-08-26T10:00:00',"
            " '2026-08-26T10:00:00', NULL)")
        conn.commit()
    finally:
        conn.close()
    db_blockers.init_schema(db_path)  # re-run migrations = app startup
    conn = database.get_connection(db_path)
    try:
        row = db_blockers.list_blockers(conn)[0]
        assert row["display_id"] == "BC-001"
    finally:
        conn.close()


def test_chip_label_prefers_jira_then_bc_then_name():
    assert db_blockers.chip_label({"jira_key": "S4DEF-1", "display_id": None,
                                   "name": "Pricing"}) == "S4DEF-1"
    assert db_blockers.chip_label({"jira_key": None, "display_id": "BC-001",
                                   "name": "Question"}) == "BC-001"
    assert db_blockers.chip_label({"jira_key": None, "display_id": None,
                                   "name": "Task w/o key"}) == "Task w/o key"


def test_picker_payload_carries_id_labels(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        b = db_blockers.create_blocker(conn, "clarification", "Long clarification name", None)
        db_blockers.link_blocker(conn, b["blocker_id"], "S4ECOM-1")
    finally:
        conn.close()
    data = c.get("/blockers/links/S4ECOM-1").get_json()
    assert data["linked"][0]["label"] == "BC-001"
    assert data["linked"][0]["name"] == "Long clarification name"


def test_open_closed_split_manual_and_auto(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        manual = db_blockers.create_blocker(conn, "task", "ManualClose task", None)
        db_blockers.create_blocker(conn, "defect", "StillOpen defect", "S4DEF-77")
        auto = db_blockers.create_blocker(conn, "defect", "JiraDone defect", "S4ECOM-1")
        # put S4ECOM-1 into the store with a done-family status
        conn.execute(
            "INSERT INTO jira_issues (jira_key, jira_status, first_seen, last_seen)"
            " VALUES ('S4ECOM-1', 'Resolved', '2026-08-27T10:00:00', '2026-08-27T10:00:00')")
        conn.commit()
        db_blockers.set_blocker_closed(conn, manual["blocker_id"], True)
    finally:
        conn.close()
    html = c.get("/blockers/").get_data(as_text=True)
    open_part, closed_part = html.split("✔ Closed")
    assert "StillOpen defect" in open_part
    assert "ManualClose task" not in open_part and "ManualClose task" in closed_part
    assert "JiraDone defect" not in open_part and "JiraDone defect" in closed_part
    assert "↺ Reopen" in closed_part          # manual close can be reopened
    assert "(closed in Jira)" in closed_part  # auto close cannot
    # reopen the manual one
    resp = c.post(f"/blockers/{manual['blocker_id']}/close", data={"value": "0"})
    assert resp.get_json()["ok"]
    html = c.get("/blockers/").get_data(as_text=True)
    open_part, closed_part = html.split("✔ Closed")
    assert "ManualClose task" in open_part


def test_next_step_save_and_archive(client):
    c, db_path = client
    conn = database.get_connection(db_path)
    try:
        b = db_blockers.create_blocker(conn, "defect", "Pricing bug", "S4DEF-1")
    finally:
        conn.close()
    bid = b["blocker_id"]
    assert c.post(f"/blockers/{bid}/next-step",
                  data={"next_step": "chase vendor Friday"}).get_json()["ok"]
    conn = database.get_connection(db_path)
    try:
        assert db_blockers.get_blocker_next_step(conn, bid) == "chase vendor Friday"
    finally:
        conn.close()
    # archive via the generic next-steps component (registry entity 'blocker')
    resp = c.post(f"/next-steps/blocker/{bid}/archive")
    data = resp.get_json()
    assert data["ok"] and data["archived"] == "chase vendor Friday"
    conn = database.get_connection(db_path)
    try:
        assert db_blockers.get_blocker_next_step(conn, bid) is None
    finally:
        conn.close()
    hist = c.get(f"/next-steps/blocker/{bid}/list.json").get_json()
    assert hist["count"] == 1
