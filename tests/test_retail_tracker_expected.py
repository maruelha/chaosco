"""Pre-resolved "expected" tests (USER 2026-07-11): a requirement may be
linked to a FUTURE dashboard test id that the retail table does not carry
yet. It counts as resolved (not unresolved), shows an amber pill on the
board, and SELF-HEALS when the import brings the test — no stored state.
"""
import pytest

from app import database
from app import db_retail_tracker as db
import app.web_retail_tracker as web_rt
from app.web import app


def _req(excel_row=1, name="cross store exchange"):
    return {"area": "return", "scenario_label": "3. Exchange", "name": name,
            "excel_test_ref": "GKP1030MU01", "test_name": "x store ex even",
            "test_case_id": None, "sale_test_ref": None,
            "required_raw": "1", "required_dtc": 1, "all_countries": 0,
            "comment": None, "excel_row": excel_row}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "expected.db"
    database.init_db(db_path).close()
    db.init_schema(db_path)
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        db.seed_countries(conn, [("Germany", "DE")])
        db.upsert_requirements(conn, [_req()])
        req_id = conn.execute("SELECT id FROM retail_requirements").fetchone()[0]
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    c.req_id = req_id
    return c


def test_expect_future_id_resolves_and_shows_pill(client):
    # free-text expect via the same resolve route
    resp = client.post(f"/retail-tracker/requirements/{client.req_id}/resolve",
                       data={"test_case_id": "GKPMU000059"})
    assert resp.status_code == 302

    conn = database.get_connection(client.db_path)
    try:
        counts = db.requirement_counts(conn)
        assert counts["unresolved"] == 0          # no longer unresolved
        assert counts["expected"] == 1            # but flagged as expected
    finally:
        conn.close()

    board = client.get("/retail-tracker/board").get_data(as_text=True)
    assert "GKPMU000059" in board
    assert "⏳ expected" in board
    admin = client.get("/retail-tracker/").get_data(as_text=True)
    assert "⏳ Expected" in admin and "Expect" in admin


def test_self_heals_when_import_brings_the_test(client):
    client.post(f"/retail-tracker/requirements/{client.req_id}/resolve",
                data={"test_case_id": "GKPMU000059"})
    conn = database.get_connection(client.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO retail (match_key, test_case_id, testcase_name,"
                " country, status) VALUES ('k', 'GKPMU000059',"
                " 'GKPMU000059_Ex X Store Even', 'Germany', 'Passed')")
        assert db.requirement_counts(conn)["expected"] == 0   # healed
    finally:
        conn.close()

    board = client.get("/retail-tracker/board").get_data(as_text=True)
    assert "⏳ expected" not in board
    assert "Ex X Store Even" in board             # dashboard name took over
    # the pass counts immediately: requirement done 1/1
    assert "✓ 1/1" in board.replace("\n", " ")
