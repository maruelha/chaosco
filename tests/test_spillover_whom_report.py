"""Spillover list: 'With whom' (Sales|MB) + in-report filter (2026-07-09).

The rules a bug would silently break:
- setting with_whom never clobbers the other annotation fields
- the route accepts ONLY Sales / MB / blank
- in_report='yes'/'no' splits exactly along spillover_report_selection
"""
import pytest

from app import database
import app.web_spillover as web_spillover_module  # noqa: F401  (route import)
from app.web import app


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "spill.db"
    database.init_db(p).close()
    return p


@pytest.fixture()
def conn(db_path):
    c = database.get_connection(db_path)
    yield c
    c.close()


def _seed(conn):
    with conn:
        for i, name in enumerate(["Alpha", "Beta", "Gamma"], start=1):
            conn.execute(
                "INSERT INTO spillover (match_key, name, excel_row, first_seen, last_seen)"
                " VALUES (?,?,?, '2026-07-09','2026-07-09')", (name.lower(), name, i))
    return {r["name"]: r["spillover_id"]
            for r in database.get_spillover(conn)}


def test_with_whom_set_and_preserves_other_fields(conn):
    ids = _seed(conn)
    database.upsert_spillover_annotation(
        conn, ids["Alpha"], "high", "chase the SF", "history", "yes", "cmt", "grp")
    database.set_spillover_with_whom(conn, ids["Alpha"], "Sales")

    row = {r["name"]: r for r in database.get_spillover(conn)}["Alpha"]
    assert row["with_whom"] == "Sales"
    assert row["next_step"] == "chase the SF"          # untouched
    assert row["critical_for_signoff"] == "yes"        # untouched

    # row without prior annotation: upsert creates it
    database.set_spillover_with_whom(conn, ids["Beta"], "MB")
    row = {r["name"]: r for r in database.get_spillover(conn)}["Beta"]
    assert row["with_whom"] == "MB"

    # filter
    assert [r["name"] for r in database.get_spillover(conn, with_whom=["Sales"])] == ["Alpha"]
    assert [r["name"] for r in database.get_spillover(conn, with_whom=["Sales", "MB"])] \
        == ["Alpha", "Beta"]


def test_in_report_filter_follows_selection(conn):
    ids = _seed(conn)
    with conn:
        conn.execute("INSERT INTO spillover_report_selection (spillover_id) VALUES (?)",
                     (ids["Beta"],))

    assert [r["name"] for r in database.get_spillover(conn, in_report="yes")] == ["Beta"]
    assert [r["name"] for r in database.get_spillover(conn, in_report="no")] \
        == ["Alpha", "Gamma"]
    flags = {r["name"]: r["in_report"] for r in database.get_spillover(conn)}
    assert flags == {"Alpha": 0, "Beta": 1, "Gamma": 0}


def test_with_whom_route_validates(db_path, monkeypatch):
    import app.web_core as web_core
    monkeypatch.setattr(web_core, "_db_path", db_path)
    # web_spillover imported _get_conn from web_core by name — patch there too
    import app.web_spillover as ws
    monkeypatch.setattr(ws, "_get_conn",
                        lambda: database.get_connection(db_path))
    conn = database.get_connection(db_path)
    try:
        ids = _seed(conn)
    finally:
        conn.close()
    client = app.test_client()

    assert client.post(f"/spillover/{ids['Alpha']}/with-whom",
                       data={"with_whom": "Jose"}).status_code == 400

    d = client.post(f"/spillover/{ids['Alpha']}/with-whom",
                    data={"with_whom": "MB"}).get_json()
    assert d["ok"] and d["with_whom"] == "MB"

    # blank clears
    client.post(f"/spillover/{ids['Alpha']}/with-whom", data={"with_whom": ""})
    conn = database.get_connection(db_path)
    try:
        row = {r["name"]: r for r in database.get_spillover(conn)}["Alpha"]
        assert row["with_whom"] is None
    finally:
        conn.close()
