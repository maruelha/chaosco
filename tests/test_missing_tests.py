"""Missing Test Cases mini app [USER 2026-08-30].

What must hold:
- the list is the SINGLE source: the Retail status report and the Retail
  Requirements board both render it, so the two can no longer drift apart
- the board's quick-add and its ✕ write to THIS module, not to the old
  tracker_missing_tests table
- the one-time seed picks up both old places (the config bullet list and the
  board's table) and never runs twice — an emptied list stays empty
- retrofits are mirrored read-only, with our own coverage note per retrofit;
  the note is stored here because the retrofit module has no note field
- status travels with a retrofit everywhere it is shown [USER 2026-08-30]:
  Confirmed vs Potential ("not confirmed yet")
- the report downloads as standalone HTML and is selectable in the email app
- the email text is plain text, with the details under each entry
"""
import pytest

from app import database, db_retail_tracker, emailer
from app.db import missing_tests as db_missing
from app.db import retrofits as db_retrofits
import app.web_core as web_core
import app.web_missing_tests as web_missing
import app.web_retail_tracker as web_tracker
from app.web import app


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "missing.db"
    database.init_db(path).close()
    db_missing.init_schema(path)
    db_retrofits.init_schema(path)
    db_retail_tracker.init_schema(path)   # the board renders our list
    return path


@pytest.fixture()
def client(db_path, monkeypatch):
    # web_retail routes use the shared _get_conn from web_core
    for module in (web_core, web_missing, web_tracker):
        monkeypatch.setattr(module, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _conn(db_path):
    return database.get_connection(db_path)


# ---------------------------------------------------------------- storage

def test_crud_and_ordering(db_path):
    conn = _conn(db_path)
    first = db_missing.create_missing_test(conn, "  Event store  ", " no test yet ")
    db_missing.create_missing_test(conn, "100% voucher cases")
    items = db_missing.list_missing_tests(conn)
    assert [i["title"] for i in items] == ["Event store", "100% voucher cases"]
    assert items[0]["details"] == "no test yet"        # trimmed
    assert items[1]["details"] is None                 # empty stays NULL

    db_missing.update_missing_test(conn, first, "Event store", "Sales must confirm")
    assert db_missing.get_missing_test(conn, first)["details"] == "Sales must confirm"

    db_missing.delete_missing_test(conn, first)
    assert db_missing.missing_test_count(conn) == 1
    conn.close()


def test_seed_runs_once_and_takes_both_old_lists(db_path):
    conn = _conn(db_path)
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS tracker_missing_tests ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, created_at TEXT);")
    conn.execute("INSERT INTO tracker_missing_tests (text, created_at)"
                 " VALUES ('Exchange Even Plus 1', '2026-08-01T09:00:00')")
    # a title that exists in BOTH old places must not be seeded twice
    conn.execute("INSERT INTO tracker_missing_tests (text, created_at)"
                 " VALUES ('event store', '2026-08-02T09:00:00')")
    conn.commit()
    conn.close()

    written = db_missing.seed_once(db_path, ["Manual test cases", "Event store"])
    assert written == 3
    conn = _conn(db_path)
    titles = [i["title"] for i in db_missing.list_missing_tests(conn)]
    assert titles == ["Manual test cases", "Event store", "Exchange Even Plus 1"]
    conn.close()

    # second run does nothing, and an emptied list stays empty
    assert db_missing.seed_once(db_path, ["Manual test cases"]) == 0
    conn = _conn(db_path)
    for item in db_missing.list_missing_tests(conn):
        db_missing.delete_missing_test(conn, item["id"])
    conn.close()
    assert db_missing.seed_once(db_path, ["Manual test cases"]) == 0
    conn = _conn(db_path)
    assert db_missing.list_missing_tests(conn) == []
    conn.close()


def test_retrofit_mirror_carries_status_and_note(db_path):
    conn = _conn(db_path)
    keep = db_retrofits.create_retrofit(conn, "Retail", "New return flow",
                                        status="Potential", expected="CW40")
    db_retrofits.create_retrofit(conn, "ECOM & Retail", "Payment provider swap")
    db_retrofits.create_retrofit(conn, "ECOM", "ECOM only change")

    db_missing.set_retrofit_note(conn, keep, "  no test case yet  ")
    mirrored = db_missing.list_retrofits_with_notes(conn)
    titles = [r["title"] for r in mirrored]
    assert "ECOM only change" not in titles          # Retail (+ shared) only
    assert "Payment provider swap" in titles
    by_title = {r["title"]: r for r in mirrored}
    assert by_title["New return flow"]["status"] == "Potential"
    assert by_title["New return flow"]["coverage_note"] == "no test case yet"
    assert by_title["Payment provider swap"]["coverage_note"] is None

    # emptying the note deletes the row instead of storing ''
    db_missing.set_retrofit_note(conn, keep, "   ")
    assert db_missing.get_retrofit_notes(conn) == {}
    conn.close()


def test_email_text_has_details_and_retrofit_status(db_path):
    conn = _conn(db_path)
    db_missing.create_missing_test(conn, "Event store", "Sales must confirm")
    rid = db_retrofits.create_retrofit(conn, "Retail", "New return flow",
                                       status="Potential", expected="CW40")
    db_missing.set_retrofit_note(conn, rid, "no test case yet")
    text = db_missing.email_text(db_missing.list_missing_tests(conn),
                                 db_missing.list_retrofits_with_notes(conn),
                                 day="2026-08-30")
    conn.close()
    assert "Missing test cases (as of 2026-08-30)" in text
    assert "1. Event store" in text
    assert "Sales must confirm" in text
    assert "New return flow (not confirmed, expected CW40)" in text
    assert "no test case yet" in text


def test_list_for_report_survives_a_db_without_the_table(tmp_path):
    path = tmp_path / "bare.db"
    database.init_db(path).close()
    conn = database.get_connection(path)
    assert db_missing.list_for_report(conn) == []
    assert db_missing.missing_test_count(conn) == 0
    conn.close()


# ---------------------------------------------------------------- web

def test_page_add_update_delete_and_note(client):
    client.post("/missing-tests/add",
                data={"title": "Event store", "details": "no test yet"})
    page = client.get("/missing-tests/").get_data(as_text=True)
    assert "Event store" in page and "no test yet" in page

    conn = _conn(client.db_path)
    item_id = db_missing.list_missing_tests(conn)[0]["id"]
    rid = db_retrofits.create_retrofit(conn, "Retail", "New return flow",
                                       status="Potential")
    conn.close()

    client.post(f"/missing-tests/{item_id}/update",
                data={"title": "Event store", "details": "Sales must confirm"})
    client.post(f"/missing-tests/retrofit/{rid}/note", data={"note": "no test case"})
    page = client.get("/missing-tests/").get_data(as_text=True)
    assert "Sales must confirm" in page
    assert "no test case" in page
    assert "not confirmed yet" in page          # the Potential status shows

    assert client.post(f"/missing-tests/{item_id}/delete").get_json()["ok"]
    conn = _conn(client.db_path)
    assert db_missing.list_missing_tests(conn) == []
    conn.close()


def test_report_and_download(client):
    conn = _conn(client.db_path)
    db_missing.create_missing_test(conn, "Event store", "Sales must confirm")
    rid = db_retrofits.create_retrofit(conn, "Retail", "New return flow",
                                       status="Potential")
    db_missing.set_retrofit_note(conn, rid, "no test case yet")
    conn.close()

    report = client.get("/missing-tests/report").get_data(as_text=True)
    assert "Missing Test Cases" in report
    assert "Sales must confirm" in report
    assert "not confirmed yet" in report
    assert "no test case yet" in report

    resp = client.get("/missing-tests/report/download")
    assert "attachment; filename=\"missing_test_cases_" in \
        resp.headers["Content-Disposition"]
    html = resp.get_data(as_text=True)
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "Download HTML" not in html          # toolbar dropped in the download


def test_it_is_an_email_report_choice():
    assert ("missing_tests", "Missing Test Cases (Retail)") in emailer.REPORT_CHOICES


def test_board_quick_add_writes_to_the_shared_list(client):
    client.post("/retail-tracker/missing/add", data={"text": "Exchange Even Plus 1"})
    conn = _conn(client.db_path)
    items = db_missing.list_missing_tests(conn)
    conn.close()
    assert [i["title"] for i in items] == ["Exchange Even Plus 1"]

    board = client.get("/retail-tracker/board").get_data(as_text=True)
    assert "Exchange Even Plus 1" in board

    client.post(f"/retail-tracker/missing/{items[0]['id']}/delete")
    conn = _conn(client.db_path)
    assert db_missing.list_missing_tests(conn) == []
    conn.close()


def test_retail_report_renders_the_same_list(client):
    conn = _conn(client.db_path)
    db_missing.create_missing_test(conn, "Event store", "Sales must confirm")
    conn.close()
    for url in ("/retail/report", "/retail/report/download"):
        html = client.get(url).get_data(as_text=True)
        assert "Event store" in html, url
