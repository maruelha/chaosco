"""Sustainphase Issues storage (rewritten 2026-09-03 [USER]): incident
upsert + column-G comment history, next step, solutions/interfaces
replacement, and the COMPUTED totals."""
import pytest

from app import database
from app.db import sustain_issues as db_si


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "si.db"
    database.init_db(db_path).close()
    db_si.init_schema(db_path)
    c = database.get_connection(db_path)
    yield c
    c.close()


def _inc(no, comment=None, **kw):
    return {"incident_number": no, "date": "2026-09-01", "requestor": "Anna",
            "title": f"Title {no}", "status": "Open", "assigned_to": None,
            "latest_comment": comment, "excel_row": 2, **kw}


def test_upsert_keeps_a_comment_history_on_top_and_ignores_same_text(conn):
    counts = db_si.upsert_incidents(conn, [_inc("INC1", "first look"), _inc("INC2")])
    assert counts == {"inserted": 2, "updated": 0, "new_comments": 1}
    # same text (re-wrapped whitespace) → no new entry; changed text → on top
    counts = db_si.upsert_incidents(conn, [_inc("INC1", "first   look", status="In Progress")])
    assert counts == {"inserted": 0, "updated": 1, "new_comments": 0}
    counts = db_si.upsert_incidents(conn, [_inc("INC1", "fixed in AIF")])
    assert counts["new_comments"] == 1
    history = db_si.comments_by_incident(conn)["INC1"]
    assert [h["text"] for h in history] == ["fixed in AIF", "first look"]   # newest first
    assert history[0]["first_seen"]
    assert "INC2" not in db_si.comments_by_incident(conn)               # no comment, no entry
    # going BACK to an older text is a change too (it is a new latest text)
    db_si.upsert_incidents(conn, [_inc("INC1", "first look")])
    assert [h["text"] for h in db_si.comments_by_incident(conn)["INC1"]][0] == "first look"
    assert db_si.get_incident(conn, "INC1")["status"] == "Open"
    assert db_si.incident_count(conn) == 2
    assert [i["incident_number"] for i in db_si.list_incidents(conn)] == ["INC2", "INC1"]


def test_next_step_roundtrip(conn):
    db_si.upsert_incidents(conn, [_inc("INC1")])
    assert db_si.get_sustain_incident_next_step(conn, "INC1") is None
    db_si.set_sustain_incident_next_step(conn, "INC1", "call Tom")
    assert db_si.get_sustain_incident_next_step(conn, "INC1") == "call Tom"
    assert db_si.get_incident_annotations(conn)["INC1"]["next_step"] == "call Tom"
    db_si.set_sustain_incident_next_step(conn, "INC1", "  ")
    assert db_si.get_sustain_incident_next_step(conn, "INC1") is None


def _sol(interface, status="Open", reason="Mapping", **kw):
    return {"owner": "Tom", "interface": interface, "msg": None, "text": "t",
            "external_reference": None, "inc_reference": None, "reason": reason,
            "solution": None, "status": status, "excel_row": 2, **kw}


def test_totals_per_interface_all_and_open_with_extra_rows_and_reasons(conn):
    db_si.replace_interfaces(conn, [
        {"namespace": "/RFMPI", "interface": "SALES"},
        {"namespace": "/SDSLS", "interface": "SO_BULK_I"},
        {"namespace": "ZSD_I", "interface": "SO_MULTI"}])
    db_si.replace_solutions(conn, [
        _sol("SALES"), _sol("sales ", status="Closed"), _sol("SALES", reason="Data"),
        _sol("SO_BULK_I", status="Resolved", reason="Data"),
        _sol("n/a"), _sol("N/A", status="Done", reason=None),
        _sol("ZZ_NEW", reason="Mapping")])
    t = db_si.interface_totals(conn)
    by = {r["interface"]: r for r in t["rows"]}
    assert (by["SALES"]["total_all"], by["SALES"]["total_open"]) == (3, 2)
    assert (by["SO_BULK_I"]["total_all"], by["SO_BULK_I"]["total_open"]) == (1, 0)
    assert (by["SO_MULTI"]["total_all"], by["SO_MULTI"]["total_open"]) == (0, 0)
    # unlisted interfaces get their own rows so the totals add up [USER]
    assert [(e["interface"], e["total_all"], e["total_open"]) for e in t["extra"]] == \
        [("n/a", 2, 1), ("ZZ_NEW", 1, 1)]
    assert t["total_all"] == 7 and t["total_open"] == 4
    assert sum(r["total_all"] for r in t["rows"]) + sum(e["total_all"] for e in t["extra"]) == 7
    reasons = db_si.reason_totals(conn)
    assert [(r["reason"], r["total_all"], r["total_open"]) for r in reasons] == \
        [("Mapping", 4, 3), ("Data", 2, 1), ("(blank)", 1, 0)]
    # replacement is wholesale
    db_si.replace_solutions(conn, [])
    assert db_si.interface_totals(conn)["total_all"] == 0
    assert db_si.list_solutions(conn) == []
