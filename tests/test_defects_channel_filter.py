"""Defects channel filter (2026-07-18).

The Excel carries mixed channel casings ("ecom", "Ecom", "Retail" …).
The filter dropdown must collapse them to ONE uppercase entry per channel
and the filter itself must match case-insensitively.
"""
import pytest

from app import database
import app.web_defects as web_defects
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "defects.db"
    database.init_db(db_path).close()
    conn = database.get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO defects (defect_id, channel, first_seen, last_seen) VALUES"
                " ('8000001', 'ecom', 'd', 'd'),"
                " ('8000002', 'Ecom', 'd', 'd'),"
                " ('8000003', 'Retail', 'd', 'd'),"
                " ('8000004', 'RETAIL ', 'd', 'd')")
    finally:
        conn.close()
    monkeypatch.setattr(web_defects, "_get_conn",
                        lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    return c


def test_filter_options_collapse_channel_casings(client):
    conn = database.get_connection(client.db_path)
    try:
        options = database.get_filter_options(conn)
    finally:
        conn.close()
    assert options["channels"] == ["ECOM", "RETAIL"]


def test_channel_filter_matches_case_insensitively(client):
    conn = database.get_connection(client.db_path)
    try:
        ecom = database.list_defects(conn, channel="ECOM")
        retail = database.list_defects(conn, channel="retail")
    finally:
        conn.close()
    assert sorted(d["defect_id"] for d in ecom) == ["8000001", "8000002"]
    assert sorted(d["defect_id"] for d in retail) == ["8000003", "8000004"]


def test_defects_page_renders_collapsed_dropdown(client):
    html = client.get("/defects?channel=ECOM").get_data(as_text=True)
    assert html.count('<option value="ECOM"') == 1
    assert html.count('<option value="RETAIL"') == 1
    assert 'value="Ecom"' not in html and 'value="ecom"' not in html
    assert '<option value="ECOM" selected' in html
    assert "8000001" in html and "8000002" in html and "8000003" not in html
