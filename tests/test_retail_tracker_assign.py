"""Reverse manual pick (coverage check): assign a passed dashboard test to a
still-unresolved requirement. The guard that matters: an already-resolved
requirement is never silently re-linked."""
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


def _get_test_case_id(conn, req_id):
    return conn.execute(
        "SELECT test_case_id FROM retail_requirements WHERE id=?",
        (req_id,)).fetchone()[0]


def test_assign_links_unresolved_requirement(db_path):
    conn = database.get_connection(db_path)
    try:
        db.upsert_requirements(conn, [_req()])
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
        assert db.assign_test_to_unresolved(conn, req_id, "GKPMU0001") is True
        assert _get_test_case_id(conn, req_id) == "GKPMU0001"
    finally:
        conn.close()


def test_assign_refuses_resolved_requirement(db_path):
    conn = database.get_connection(db_path)
    try:
        db.upsert_requirements(conn, [_req(test_case_id="GKPMU0001")])
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
        assert db.assign_test_to_unresolved(conn, req_id, "GKPMU0002") is False
        assert _get_test_case_id(conn, req_id) == "GKPMU0001"
    finally:
        conn.close()


def test_assign_survives_reimport(db_path):
    # the importer's upsert keeps a manually set id when the parse has NULL
    conn = database.get_connection(db_path)
    try:
        db.upsert_requirements(conn, [_req()])
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
        db.assign_test_to_unresolved(conn, req_id, "GKPMU0001")
        db.upsert_requirements(conn, [_req()])          # re-import, unresolved parse
        assert _get_test_case_id(conn, req_id) == "GKPMU0001"
    finally:
        conn.close()


def test_coverage_assign_route(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        db.upsert_requirements(conn, [_req()])
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
    finally:
        conn.close()

    client = app.test_client()
    resp = client.post("/retail-tracker/coverage/assign",
                       data={"req_id": req_id, "test_case_id": "GKPMU0001"})
    assert resp.status_code == 302

    conn = database.get_connection(db_path)
    try:
        assert _get_test_case_id(conn, req_id) == "GKPMU0001"
    finally:
        conn.close()


def test_coverage_assign_route_ignores_empty_pick(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        db.upsert_requirements(conn, [_req()])
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
    finally:
        conn.close()

    client = app.test_client()
    resp = client.post("/retail-tracker/coverage/assign",
                       data={"req_id": "", "test_case_id": "GKPMU0001"})
    assert resp.status_code == 302

    conn = database.get_connection(db_path)
    try:
        assert _get_test_case_id(conn, req_id) is None
    finally:
        conn.close()
