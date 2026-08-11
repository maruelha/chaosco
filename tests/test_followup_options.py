"""Follow-up board: managed pick lists for "With whom" and "Group"
[USER 2026-08-11].

Both fields used to be free text, which produced several spellings of the
same party. They are now picked from a list maintained at the top of the
page: adding, renaming (carries the follow-ups along, merges duplicates)
and removing entries.
"""
import pytest

from app import database
import app.web_planning as web_planning
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "followups.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_planning, "_db_path", db_path, raising=False)
    import app.web_core as web_core
    monkeypatch.setattr(web_core, "_db_path", db_path, raising=False)
    c = app.test_client()
    c.db_path = db_path
    return c


def _conn(client):
    return database.get_connection(client.db_path)


def _values(client, kind):
    conn = _conn(client)
    try:
        return [o["value"] for o in database.list_followup_options(conn, kind)]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def test_add_option_trims_and_ignores_duplicates(client):
    conn = _conn(client)
    try:
        database.add_followup_option(conn, "person", "  DTC O2C  ")
        database.add_followup_option(conn, "person", "DTC O2C")
        database.add_followup_option(conn, "group", "DTC O2C")   # other kind: own entry
        database.add_followup_option(conn, "person", "   ")      # empty: ignored
        assert [o["value"] for o in database.list_followup_options(conn, "person")] == ["DTC O2C"]
        assert [o["value"] for o in database.list_followup_options(conn, "group")] == ["DTC O2C"]
    finally:
        conn.close()


def test_list_reports_how_often_an_entry_is_used(client):
    conn = _conn(client)
    try:
        database.add_followup_option(conn, "person", "Bernd")
        database.add_followup_option(conn, "person", "Unused")
        database.add_followup(conn, "Bernd", "B2B retest", "2026-08-12", None)
        database.add_followup(conn, "Bernd", "voucher chase", "2026-08-13", None)
        counts = {o["value"]: o["use_count"]
                  for o in database.list_followup_options(conn, "person")}
        assert counts == {"Bernd": 2, "Unused": 0}
    finally:
        conn.close()


def test_rename_carries_the_followups_along(client):
    conn = _conn(client)
    try:
        database.add_followup_option(conn, "person", "DTC 02C")     # typo
        fid = database.add_followup(conn, "DTC 02C", "cutover", "2026-08-12", None)
        opt = database.list_followup_options(conn, "person")[0]
        database.rename_followup_option(conn, opt["id"], "DTC O2C")
        assert [o["value"] for o in database.list_followup_options(conn, "person")] == ["DTC O2C"]
        assert database.get_followup_by_id(conn, fid)["with_whom"] == "DTC O2C"
    finally:
        conn.close()


def test_rename_onto_an_existing_entry_merges_them(client):
    conn = _conn(client)
    try:
        for spelling in ("DTC O2C", "dtc o2c team"):
            database.add_followup_option(conn, "group", spelling)
        fid = database.add_followup(conn, "Bernd", "cutover", "2026-08-12", "dtc o2c team")
        dupe = [o for o in database.list_followup_options(conn, "group")
                if o["value"] == "dtc o2c team"][0]
        database.rename_followup_option(conn, dupe["id"], "DTC O2C")
        assert [o["value"] for o in database.list_followup_options(conn, "group")] == ["DTC O2C"]
        assert database.get_followup_by_id(conn, fid)["group_name"] == "DTC O2C"
    finally:
        conn.close()


def test_delete_option_leaves_the_followup_untouched(client):
    conn = _conn(client)
    try:
        database.add_followup_option(conn, "person", "Bernd")
        fid = database.add_followup(conn, "Bernd", "B2B retest", "2026-08-12", None)
        opt = database.list_followup_options(conn, "person")[0]
        database.delete_followup_option(conn, opt["id"])
        assert database.list_followup_options(conn, "person") == []
        assert database.get_followup_by_id(conn, fid)["with_whom"] == "Bernd"
    finally:
        conn.close()


def test_existing_free_text_values_seed_the_lists_once(client, tmp_path):
    """Upgrading a DB that already has follow-ups must not lose any value."""
    conn = _conn(client)
    try:
        database.add_followup(conn, "Bernd", "B2B retest", "2026-08-12", "Sales")
        database.add_followup(conn, "Bernd", "voucher chase", "2026-08-13", None)
        conn.execute("DELETE FROM followup_options")     # pre-migration state
        conn.commit()
    finally:
        conn.close()
    database.init_db(client.db_path).close()             # migration runs here
    assert _values(client, "person") == ["Bernd"]
    assert _values(client, "group") == ["Sales"]
    database.init_db(client.db_path).close()             # re-run is a no-op
    assert _values(client, "person") == ["Bernd"]


# ---------------------------------------------------------------------------
# routes + markup
# ---------------------------------------------------------------------------

def test_option_routes_manage_the_list(client):
    client.post("/followups/options/add", data={"kind": "person", "value": "Bernd"})
    assert _values(client, "person") == ["Bernd"]
    conn = _conn(client)
    try:
        opt_id = database.list_followup_options(conn, "person")[0]["id"]
    finally:
        conn.close()
    client.post(f"/followups/options/{opt_id}/rename", data={"value": "Bernd H."})
    assert _values(client, "person") == ["Bernd H."]
    client.post(f"/followups/options/{opt_id}/delete")
    assert _values(client, "person") == []


def test_add_form_offers_only_the_managed_values(client):
    client.post("/followups/options/add", data={"kind": "person", "value": "Bernd"})
    client.post("/followups/options/add", data={"kind": "group", "value": "Sales"})
    conn = _conn(client)
    try:
        database.add_followup(conn, "Legacy Person", "old row", "2026-08-12", None)
    finally:
        conn.close()
    html = client.get("/followups").get_data(as_text=True)
    assert '<select name="with_whom" required' in html      # not a free-text input
    assert '<option value="Bernd">Bernd</option>' in html
    assert '<option value="Sales">Sales</option>' in html
    # a value only present on an old row is filterable but not offered as a pick
    assert '<option value="Legacy Person">Legacy Person</option>' not in html
    assert 'value="Legacy Person"' in html                  # …the filter dialog has it


def test_status_selects_are_named_so_the_browser_cannot_shift_them(client):
    """Setting a row to done removed it from the list and the browser then
    restored "Done" onto the NEXT row — unnamed controls are restored by
    position on reload [USER 2026-08-11]."""
    conn = _conn(client)
    try:
        ids = [database.add_followup(conn, "Bernd", t, "2026-08-12", None)
               for t in ("FIRST", "SECOND")]
    finally:
        conn.close()
    html = client.get("/followups").get_data(as_text=True)
    for fid in ids:
        assert f'name="fu-status-{fid}"' in html
    assert html.count('autocomplete="off"') >= len(ids)
