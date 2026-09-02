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
    assert item["name"] == "New topic"
    assert item["topic"] == "New topic"      # no topic given -> mirrors name
    assert item["responsible"] == "Someone"


# --- name / ticket_no / impact (planning chat 2026-09-02) -----------------

def test_create_name_is_the_short_line_and_topic_mirrors_it(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "retail", "Issue", "  Short line  ")
    item = db_sc.get_callout(conn, cid)
    assert item["name"] == "Short line"
    assert item["topic"] == "Short line"
    assert item["ticket_no"] is None
    assert item["impact"] is None


def test_create_with_detail_fields(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(
        conn, "ecom", "MigrIssue", "Prices wrong", "Marina",
        topic="Migrated prices differ from legacy for DE web orders",
        ticket_no="SUS-017", impact="Customers see old prices at checkout")
    item = db_sc.get_callout(conn, cid)
    assert item["name"] == "Prices wrong"
    assert item["topic"].startswith("Migrated prices differ")
    assert item["ticket_no"] == "SUS-017"
    assert item["impact"].startswith("Customers see")


def test_update_sets_detail_fields_and_blanks_clear_them(tmp_path):
    conn = _setup(tmp_path)
    cid = db_sc.create_callout(conn, "retail", "Issue", "Name",
                                ticket_no="ASPEN-1", impact="big")
    db_sc.update_callout(conn, cid, "retail", "Issue", "New name", None,
                         topic="Long topic text", ticket_no="ASPEN-2",
                         impact="")
    item = db_sc.get_callout(conn, cid)
    assert item["name"] == "New name"
    assert item["topic"] == "Long topic text"
    assert item["ticket_no"] == "ASPEN-2"
    assert item["impact"] is None            # blank clears


def test_init_schema_backfills_name_from_topic_on_old_dbs(tmp_path):
    """A DB from before 2026-09-02 has topic but no name column: the
    guarded ALTERs add the columns and every old row's short line becomes
    its topic (so the list never shows an empty name)."""
    db_path = tmp_path / "old.db"
    database.init_db(db_path).close()
    conn = database.get_connection(db_path)
    with conn:
        conn.execute("DROP TABLE IF EXISTS sustain_callouts")
        conn.execute("""
            CREATE TABLE sustain_callouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL, type TEXT NOT NULL,
                topic TEXT NOT NULL, responsible TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                date_captured TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO sustain_callouts (channel, type, topic,"
            " date_captured, created_at, updated_at)"
            " VALUES ('retail', 'Issue', 'Old row topic', '2026-09-01',"
            " 'x', 'x')")
    conn.close()

    db_sc.init_schema(db_path)
    db_sc.init_schema(db_path)               # re-run is harmless

    conn = database.get_connection(db_path)
    item = db_sc.list_callouts(conn)[0]
    assert item["name"] == "Old row topic"
    assert item["topic"] == "Old row topic"
    assert item["ticket_no"] is None
    assert item["impact"] is None
    assert item["next_step"] is None


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
