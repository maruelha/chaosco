"""Sustain Call-outs (build plan step 1, 2026-09-01) — own user-authored
table (never touched by the importer), status cycling, and the 'both'
channel showing up in both streams' filtered lists."""
from datetime import date

from app import database
from app.db import sustain_callouts as db_sc


def _setup(tmp_path):
    db_path = tmp_path / "sc.db"
    database.init_db(db_path).close()
    db_sc.init_schema(db_path)
    return database.get_connection(db_path)


def test_create_defaults_open_and_captures_today(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "retail", "Issue", "Something broke",
                                "Marina")
    item = db_sc.get_callout(conn, cid)
    assert item["status"] == "open"
    assert item["date_captured"] == date.today().isoformat()
    assert item["channel"] == "retail"
    assert item["type"] == "Issue"
    assert item["topic"] == "Something broke"
    assert item["responsible"] == "Marina"


def test_create_cleans_unknown_channel_and_type(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "bogus", "Nonsense", "Topic")
    item = db_sc.get_callout(conn, cid)
    assert item["channel"] == db_sc.CALLOUT_CHANNELS[0]
    assert item["type"] == db_sc.CALLOUT_TYPES[0]


def test_cycle_status_open_inprogress_closed_open(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "ecom", "Spotcheck", "Check something")
    assert db_sc.cycle_status(conn, cid) == "in_progress"
    assert db_sc.cycle_status(conn, cid) == "closed"
    assert db_sc.cycle_status(conn, cid) == "open"


def test_cycle_status_unknown_id_returns_none(tmp_path):
    conn = _setup(tmp_path)
    assert db_sc.cycle_status(conn, 999) is None


def test_list_callouts_excludes_closed_by_default(tmp_path):
    conn = _setup(tmp_path)
    open_id = db_sc.create_callout(conn, "retail", "Issue", "Open one")
    closed_id = db_sc.create_callout(conn, "retail", "Issue", "Closed one")
    db_sc.set_status(conn, closed_id, "closed")

    items = db_sc.list_callouts(conn)
    ids = [i["id"] for i in items]
    assert open_id in ids
    assert closed_id not in ids

    items_all = db_sc.list_callouts(conn, include_closed=True)
    ids_all = [i["id"] for i in items_all]
    assert open_id in ids_all
    assert closed_id in ids_all


def test_list_open_for_channel_includes_both(tmp_path):
    conn = _setup(tmp_path)
    retail_id = db_sc.create_callout(conn, "retail", "Issue", "Retail only")
    ecom_id = db_sc.create_callout(conn, "ecom", "Issue", "Ecom only")
    both_id = db_sc.create_callout(conn, "both", "OrgIssue", "Affects both")
    closed_both = db_sc.create_callout(conn, "both", "Question", "Closed both")
    db_sc.set_status(conn, closed_both, "closed")

    retail_ids = {i["id"] for i in db_sc.list_open_for_channel(conn, "retail")}
    ecom_ids = {i["id"] for i in db_sc.list_open_for_channel(conn, "ecom")}

    assert retail_ids == {retail_id, both_id}
    assert ecom_ids == {ecom_id, both_id}
    assert closed_both not in retail_ids
    assert closed_both not in ecom_ids


def test_update_callout_changes_fields(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "retail", "Issue", "Original topic")
    db_sc.update_callout(conn, cid, "ecom", "MigrIssue", "New topic", "Someone")
    item = db_sc.get_callout(conn, cid)
    assert item["channel"] == "ecom"
    assert item["type"] == "MigrIssue"
    assert item["topic"] == "New topic"
    assert item["responsible"] == "Someone"


def test_delete_callout(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "retail", "Issue", "Gone soon")
    db_sc.delete_callout(conn, cid)
    assert db_sc.get_callout(conn, cid) is None


def test_callout_count_excludes_closed(tmp_path):
    conn = _setup(tmp_path)
    db_sc.create_callout(conn, "retail", "Issue", "One")
    closed_id = db_sc.create_callout(conn, "retail", "Issue", "Two")
    db_sc.set_status(conn, closed_id, "closed")
    assert db_sc.callout_count(conn) == 1
