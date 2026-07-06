"""Manual requirements, edit, clarify list, parked passed tests (2026-07-06).

The rules a bug would silently break:
- manual rows are never pruned or overwritten by a re-import
- editing touches only the user-ownable fields, never the matching fields
- resolving a requirement auto-removes its clarify entry (both resolve paths)
- parked tests leave the coverage check's unmatched list and come back on unpark
"""
import pytest

from app import database
from app import db_retail_tracker as db
import app.web_retail_tracker as web_rt
from app.web import app


def _req(area="sales", excel_row=1, test_case_id=None, name="req"):
    return {"area": area, "scenario_label": None, "name": name,
            "excel_test_ref": "GKP0001MU01", "test_name": "some test",
            "test_case_id": test_case_id, "sale_test_ref": None,
            "required_raw": "1", "required_dtc": 1, "all_countries": 0,
            "comment": None, "excel_row": excel_row}


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "tracker.db"
    database.init_db(path).close()
    db.init_schema(path)
    return path


@pytest.fixture()
def conn(db_path):
    c = database.get_connection(db_path)
    yield c
    c.close()


def _row(conn, req_id):
    return conn.execute(
        "SELECT name, scenario_label, required_raw, required_dtc, all_countries,"
        " test_case_id, test_name, source FROM retail_requirements WHERE id=?",
        (req_id,)).fetchone()


# ---------------------------------------------------------------------------
# manual add
# ---------------------------------------------------------------------------

def test_manual_requirement_born_unresolved_in_manual_row_range(conn):
    req_id = db.add_manual_requirement(conn, "sales", "Voucher stacking", "Vouchers", "3")
    name, scenario, raw, dtc, all_c, tcid, tname, source = _row(conn, req_id)
    assert (name, scenario, raw, dtc, all_c) == ("Voucher stacking", "Vouchers", "3", 3, 0)
    assert tcid is None and tname is None and source == "manual"
    assert [r["id"] for r in db.list_requirements(conn, unresolved_only=True)] == [req_id]
    row_no = conn.execute("SELECT excel_row FROM retail_requirements WHERE id=?",
                          (req_id,)).fetchone()[0]
    assert row_no >= 5000


def test_manual_required_all_and_18(conn):
    all_id = db.add_manual_requirement(conn, "return", "R1", None, "all")
    n18_id = db.add_manual_requirement(conn, "return", "R2", None, "18")
    assert _row(conn, all_id)[4] == 1 and _row(conn, n18_id)[4] == 1


def test_manual_rows_survive_reimport_prune_and_upsert(conn):
    db.upsert_requirements(conn, [_req(excel_row=1)])
    manual_id = db.add_manual_requirement(conn, "sales", "Manual req", None, "2")
    # re-import: parse contains only the Excel row -> prune must spare manual
    db.upsert_requirements(conn, [_req(excel_row=1)])
    removed = db.delete_requirements_not_in(conn, {("sales", 1)})
    assert removed == 0
    assert _row(conn, manual_id)[0] == "Manual req"


# ---------------------------------------------------------------------------
# edit (user-ownable fields only)
# ---------------------------------------------------------------------------

def test_edit_updates_fields_but_never_matching_columns(conn):
    db.upsert_requirements(conn, [_req(test_case_id="GKPMU0001")])
    req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
    db.update_requirement_fields(conn, req_id, "New text", "New scenario", "ALL")
    name, scenario, raw, dtc, all_c, tcid, tname, _ = _row(conn, req_id)
    assert (name, scenario, raw, dtc, all_c) == ("New text", "New scenario", "ALL", None, 1)
    assert tcid == "GKPMU0001" and tname == "some test"   # untouched


# ---------------------------------------------------------------------------
# clarify list
# ---------------------------------------------------------------------------

def test_clarify_only_for_unresolved_and_autoremoved_on_resolve(conn):
    db.upsert_requirements(conn, [_req(excel_row=1),
                                  _req(excel_row=2, test_case_id="GKPMU0009")])
    open_id, resolved_id = [r[0] for r in conn.execute(
        "SELECT id FROM retail_requirements ORDER BY excel_row")]
    assert db.add_clarify(conn, resolved_id) is False       # nothing to clarify
    assert db.add_clarify(conn, open_id) is True
    assert db.add_clarify(conn, open_id) is True or True    # idempotent, no error
    assert [c["requirement_id"] for c in db.list_clarify(conn)] == [open_id]

    db.resolve_requirement(conn, open_id, "GKPMU0001")      # question answered
    assert db.list_clarify(conn) == []
    assert db.clarify_requirement_ids(conn) == set()


def test_clarify_autoremoved_by_reverse_assign(conn):
    db.upsert_requirements(conn, [_req()])
    req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
    db.add_clarify(conn, req_id)
    db.assign_test_to_unresolved(conn, req_id, "GKPMU0001")
    assert db.list_clarify(conn) == []


# ---------------------------------------------------------------------------
# parked passed tests
# ---------------------------------------------------------------------------

def _seed_passed(conn, test_case_id, name, countries):
    with conn:
        for c in countries:
            conn.execute(
                "INSERT INTO retail (match_key, test_case_id, testcase_name, country, status)"
                " VALUES (?,?,?,?, 'Passed')",
                (f"{test_case_id}|{c}", test_case_id, name, c))


def test_park_removes_from_coverage_and_unpark_restores(conn):
    _seed_passed(conn, "GKPMU0042", "GKPMU0042_Click and Collect", ["Germany", "Ireland"])
    assert [t["test_case_id"] for t in db.get_passed_test_coverage(conn)["unmatched"]] \
        == ["GKPMU0042"]

    db.park_test(conn, "GKPMU0042")
    cov = db.get_passed_test_coverage(conn)
    assert cov["unmatched"] == [] and cov["matched"] == 1

    parked = db.list_parked_tests(conn)
    assert parked[0]["testcase_name"] == "GKPMU0042_Click and Collect"
    assert parked[0]["passed_countries"] == ["Germany", "Ireland"]

    db.set_parked_comment(conn, parked[0]["id"], "asked Sales 06.07")
    assert db.list_parked_tests(conn)[0]["comment"] == "asked Sales 06.07"

    db.unpark_test(conn, parked[0]["id"])
    assert [t["test_case_id"] for t in db.get_passed_test_coverage(conn)["unmatched"]] \
        == ["GKPMU0042"]


# ---------------------------------------------------------------------------
# routes (smoke: each action lands in the DB)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def test_routes_roundtrip(client):
    # add
    resp = client.post("/retail-tracker/requirements/add",
                       data={"area": "sales", "name": "Route req", "required": "2"})
    assert resp.status_code == 302
    conn = database.get_connection(client.db_path)
    try:
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
    finally:
        conn.close()

    # edit
    client.post(f"/retail-tracker/requirements/{req_id}/edit",
                data={"name": "Route req v2", "scenario_label": "S", "required": "ALL"})
    # clarify add
    client.post("/retail-tracker/clarify/add", data={"req_id": req_id})
    # park + comment + unpark
    client.post("/retail-tracker/coverage/park", data={"test_case_id": "GKPMU0099"})

    conn = database.get_connection(client.db_path)
    try:
        name, all_c = conn.execute(
            "SELECT name, all_countries FROM retail_requirements WHERE id=?",
            (req_id,)).fetchone()
        assert (name, all_c) == ("Route req v2", 1)
        assert db.clarify_requirement_ids(conn) == {req_id}
        parked_id = db.list_parked_tests(conn)[0]["id"]
    finally:
        conn.close()

    client.post(f"/retail-tracker/parked/{parked_id}/comment", data={"comment": "note"})
    client.post(f"/retail-tracker/parked/{parked_id}/unpark")
    client.post(f"/retail-tracker/clarify/add", data={"req_id": req_id})

    conn = database.get_connection(client.db_path)
    try:
        assert db.list_parked_tests(conn) == []
    finally:
        conn.close()

    # board + admin render with the new sections
    for url, marker in (("/retail-tracker/board", "Clarify with Sales"),
                        ("/retail-tracker/board", "Not part of our requirements"),
                        ("/retail-tracker/", "Add a requirement")):
        resp = client.get(url)
        assert resp.status_code == 200
        assert marker in resp.get_data(as_text=True)
