"""Spillover default filter (2026-07-18): a fresh /spillover open shows the
Status-report "In report" view; an explicit All (in_report= present but
empty) still shows everything — only a MISSING param gets the default.
"""
import pytest

from app import database
import app.web_spillover as web_spillover
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "spill.db"
    database.init_db(db_path).close()
    conn = database.get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO spillover (match_key, name, first_seen, last_seen) VALUES"
                " ('1', 'Picked item', 'd', 'd'), ('2', 'Unpicked item', 'd', 'd')")
            picked = conn.execute(
                "SELECT spillover_id FROM spillover WHERE name='Picked item'").fetchone()[0]
            conn.execute(
                "INSERT INTO spillover_report_selection (spillover_id) VALUES (?)",
                (picked,))
    finally:
        conn.close()
    monkeypatch.setattr(web_spillover, "_get_conn",
                        lambda: database.get_connection(db_path))
    return app.test_client()


def test_fresh_open_defaults_to_in_report(client):
    html = client.get("/spillover").get_data(as_text=True)
    assert "Picked item" in html and "Unpicked item" not in html
    assert 'value="yes" selected' in html                    # select shows it


def test_explicit_all_shows_everything(client):
    html = client.get("/spillover?in_report=").get_data(as_text=True)
    assert "Picked item" in html and "Unpicked item" in html

    html = client.get("/spillover?in_report=no").get_data(as_text=True)
    assert "Unpicked item" in html and "Picked item" not in html
