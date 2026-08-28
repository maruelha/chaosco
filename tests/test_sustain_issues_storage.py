"""Sustainphase Issues (build plan step 1, 2026-08-28): storage —
upsert by Defect ID with SUS-nnn placeholder keys for issues not yet in
ASPEN (placeholder stays searchable as former id once the real Defect ID
arrives), plus the authored annotations (call-outs + next step)."""
from app import database
from app.db import sustain_issues as db_si


def _row(defect_id=None, short_description="Settlement file missing",
         **extra):
    row = {
        "defect_id": defect_id, "short_description": short_description,
        "channel": "Retail", "sales_dtc": "DTC", "aspen_status": "Open",
        "description": None, "comment": None, "raised_by": "Marina",
        "order_number": None, "date_reported": "2026-08-28",
        "date_closed": None, "priority": "High", "assigned_to": None,
        "tech_team": None, "country": "France", "scenario": None,
        "affected_testcases": None, "retest_dependency": None,
        "blocks_execution": None, "defect_reason": None, "excel_row": 2,
    }
    row.update(extra)
    return row


def _setup(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_si.init_schema(db_path)
    return database.get_connection(db_path)


def test_upsert_by_defect_id_updates_not_duplicates(tmp_path):
    conn = _setup(tmp_path)
    try:
        counts = db_si.upsert_issues(conn, [
            _row("ASPEN-1", aspen_status="Open")])
        assert counts == {"inserted": 1, "updated": 0, "promoted": 0}
        counts = db_si.upsert_issues(conn, [
            _row("ASPEN-1", aspen_status="Closed",
                 date_closed="2026-08-29")])
        assert counts == {"inserted": 0, "updated": 1, "promoted": 0}
        issues = db_si.list_issues(conn)
        assert len(issues) == 1
        assert issues[0]["issue_key"] == "ASPEN-1"
        assert issues[0]["aspen_status"] == "Closed"
    finally:
        conn.close()


def test_placeholder_assignment_and_stability(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_si.upsert_issues(conn, [
            _row(None, "Settlement file missing"),
            _row(None, "Wrong VAT on invoice"),
        ])
        keys = [i["issue_key"] for i in db_si.list_issues(conn)]
        assert sorted(keys) == ["SUS-001", "SUS-002"]
        # re-upload, still no ASPEN ids -> matched by short description,
        # keys stay stable, nothing duplicated
        counts = db_si.upsert_issues(conn, [
            _row(None, "Settlement file missing", aspen_status="In Progress"),
            _row(None, "  wrong vat on INVOICE "),   # normalized match
        ])
        assert counts == {"inserted": 0, "updated": 2, "promoted": 0}
        assert len(db_si.list_issues(conn)) == 2
    finally:
        conn.close()


def test_aspen_id_arrival_promotes_placeholder(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_si.upsert_issues(conn, [_row(None, "Settlement file missing")])
        db_si.set_sustain_issue_callouts(conn, "SUS-001", "escalated to GBS")
        db_si.set_sustain_issue_next_step(conn, "SUS-001", "chase ASPEN id")

        counts = db_si.upsert_issues(conn, [
            _row("ASPEN-77", "Settlement file missing")])
        assert counts == {"inserted": 0, "updated": 0, "promoted": 1}
        issues = db_si.list_issues(conn)
        assert len(issues) == 1
        issue = issues[0]
        assert issue["issue_key"] == "ASPEN-77"
        assert issue["defect_id"] == "ASPEN-77"
        # the placeholder is no longer the key but stays searchable
        assert issue["former_placeholder"] == "SUS-001"
        # annotations moved along with the key
        anns = db_si.get_sustain_issue_annotations(conn)
        assert anns["ASPEN-77"]["callouts"] == "escalated to GBS"
        assert anns["ASPEN-77"]["next_step"] == "chase ASPEN id"
        assert "SUS-001" not in anns
        # the next new placeholder does NOT reuse SUS-001
        db_si.upsert_issues(conn, [_row(None, "Another new issue")])
        assert [i["issue_key"] for i in db_si.list_issues(conn)
                if i["issue_key"].startswith("SUS-")] == ["SUS-002"]
    finally:
        conn.close()


def test_annotations_upsert_only_their_field(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_si.set_sustain_issue_callouts(conn, "ASPEN-1", "watch this")
        db_si.set_sustain_issue_next_step(conn, "ASPEN-1", "retest FR")
        db_si.set_sustain_issue_callouts(conn, "ASPEN-1", "updated")
        anns = db_si.get_sustain_issue_annotations(conn)
        assert anns["ASPEN-1"] == {"callouts": "updated",
                                   "next_step": "retest FR"}
        assert db_si.get_sustain_issue_next_step(conn, "ASPEN-1") == "retest FR"
        db_si.set_sustain_issue_next_step(conn, "ASPEN-1", "")
        assert db_si.get_sustain_issue_next_step(conn, "ASPEN-1") is None
    finally:
        conn.close()


def test_rows_without_id_and_description_are_skipped(tmp_path):
    conn = _setup(tmp_path)
    try:
        counts = db_si.upsert_issues(conn, [
            _row(None, None), _row(None, "   ")])
        assert counts == {"inserted": 0, "updated": 0, "promoted": 0}
        assert db_si.list_issues(conn) == []
    finally:
        conn.close()


def test_empty_db_is_tolerated(tmp_path):
    db_path = tmp_path / "bare.db"
    database.init_db(db_path).close()   # no sustain_issues init_schema
    conn = database.get_connection(db_path)
    try:
        assert db_si.issue_count(conn) == 0
        assert db_si.list_issues(conn) == []
        assert db_si.get_sustain_issue_annotations(conn) == {}
    finally:
        conn.close()
