"""Retrofits module [USER 2026-08-10].

What must hold:
- CRUD through the routes; channel/status normalised whatever casing arrives
- Confirmed rows sort before Potential ones (the report reads "is coming"
  before "might still come")
- the channel report sections are strictly per-channel: a Retail retrofit
  never leaks into the ECOM report and vice versa
- the standing caveat ("further retrofits may still be announced") is shown
  even when the list is EMPTY — the section exists to stop the reader
  assuming the list is final
- the optional Topic link resolves to the topic detail page
- the emailed/downloaded Retail report carries the same section
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import retrofits as db_retrofits
from app.db import topics as db_topics
import app.web_core as web_core
import app.web_ecom as web_ecom
import app.web_retrofits as web_retrofits
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "retrofits.db"
    database.init_db(db_path).close()
    db_retrofits.init_schema(db_path)
    db_topics.init_schema(db_path)
    db_ecom.init_schema(db_path)
    monkeypatch.setattr(web_core, "_db_path", db_path)
    monkeypatch.setattr(web_retrofits, "_db_path", db_path)
    monkeypatch.setattr(web_ecom, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _add(client, **fields):
    data = {"channel": "Retail", "title": "A retrofit", "status": "Confirmed"}
    data.update(fields)
    return client.post("/retrofits/add", data=data)


def test_add_list_update_delete(client):
    assert _add(client, title="ZVCH tender type", expected="CW34").status_code == 302

    conn = database.get_connection(client.db_path)
    try:
        rows = db_retrofits.list_retrofits(conn)
        assert len(rows) == 1
        rid = rows[0]["id"]
        assert rows[0]["title"] == "ZVCH tender type"
        assert rows[0]["expected"] == "CW34"
        assert rows[0]["channel"] == "Retail"
    finally:
        conn.close()

    client.post(f"/retrofits/{rid}/update", data={
        "channel": "ECOM", "title": "ZVCH tender type (revised)",
        "status": "Potential", "description": "still under discussion"})
    conn = database.get_connection(client.db_path)
    try:
        row = db_retrofits.get_retrofit(conn, rid)
        assert row["channel"] == "ECOM"
        assert row["status"] == "Potential"
        assert row["description"] == "still under discussion"
    finally:
        conn.close()

    assert client.post(f"/retrofits/{rid}/delete").get_json()["ok"]
    conn = database.get_connection(client.db_path)
    try:
        assert db_retrofits.list_retrofits(conn) == []
    finally:
        conn.close()


def test_blank_title_is_not_created(client):
    _add(client, title="   ")
    conn = database.get_connection(client.db_path)
    try:
        assert db_retrofits.list_retrofits(conn) == []
    finally:
        conn.close()


@pytest.mark.parametrize("given,expected", [
    ("ecom", "ECOM"), ("ECOM", "ECOM"), ("retail", "Retail"),
    ("  Retail ", "Retail"), ("nonsense", "ECOM"), ("", "ECOM"),
])
def test_channel_normalised(client, given, expected):
    conn = database.get_connection(client.db_path)
    try:
        rid = db_retrofits.create_retrofit(conn, given, "t")
        assert db_retrofits.get_retrofit(conn, rid)["channel"] == expected
    finally:
        conn.close()


@pytest.mark.parametrize("given,expected", [
    ("potential", "Potential"), ("CONFIRMED", "Confirmed"),
    ("nonsense", "Confirmed"), ("", "Confirmed"),
])
def test_status_normalised(client, given, expected):
    conn = database.get_connection(client.db_path)
    try:
        rid = db_retrofits.create_retrofit(conn, "Retail", "t", status=given)
        assert db_retrofits.get_retrofit(conn, rid)["status"] == expected
    finally:
        conn.close()


def test_confirmed_sorts_before_potential(client):
    conn = database.get_connection(client.db_path)
    try:
        db_retrofits.create_retrofit(conn, "Retail", "might come", status="Potential")
        db_retrofits.create_retrofit(conn, "Retail", "is coming", status="Confirmed")
        titles = [r["title"] for r in db_retrofits.list_retrofits(conn, channel="Retail")]
        assert titles == ["is coming", "might come"]
    finally:
        conn.close()


def test_channel_filter_and_counts(client):
    _add(client, channel="Retail", title="RetailOnly")
    _add(client, channel="ECOM", title="EcomOnly")

    html = client.get("/retrofits/?channel=ECOM").get_data(as_text=True)
    assert "EcomOnly" in html and "RetailOnly" not in html

    conn = database.get_connection(client.db_path)
    try:
        counts = db_retrofits.retrofit_counts(conn)
        assert counts == {"total": 2, "ECOM": 1, "Retail": 1}
    finally:
        conn.close()


def test_reports_show_only_their_own_channel(client):
    _add(client, channel="Retail", title="RetailRetrofit")
    _add(client, channel="ECOM", title="EcomRetrofit", status="Potential")

    retail = client.get("/retail/report").get_data(as_text=True)
    assert "Retrofits — Retail" in retail
    assert "RetailRetrofit" in retail and "EcomRetrofit" not in retail

    ecom = client.get("/ecom/report").get_data(as_text=True)
    assert "Retrofits — ECOM" in ecom
    assert "EcomRetrofit" in ecom and "RetailRetrofit" not in ecom


def test_caveat_shown_even_with_no_retrofits(client):
    """The section is the reminder — it must not disappear when empty."""
    for url in ("/retail/report", "/ecom/report"):
        html = client.get(url).get_data(as_text=True)
        assert "further retrofits may still be announced" in html
        assert "No retrofits recorded" in html


def test_topic_link_rendered(client):
    conn = database.get_connection(client.db_path)
    try:
        tid = db_topics.create_topic(conn, "Voucher retrofit background")
    finally:
        conn.close()
    _add(client, channel="Retail", title="Linked retrofit", topic_id=str(tid))

    for url in ("/retrofits/", "/retail/report"):
        html = client.get(url).get_data(as_text=True)
        assert "Voucher retrofit background" in html
        assert f"/topics/{tid}" in html


def test_readable_without_the_topics_table(tmp_path):
    """A retrofit must not become unreadable because ANOTHER feature's table
    is missing — the topic title is resolved separately, not via a JOIN."""
    db_path = tmp_path / "no_topics.db"
    database.init_db(db_path).close()
    db_retrofits.init_schema(db_path)      # deliberately no topics schema
    conn = database.get_connection(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS topics")
        conn.commit()
        db_retrofits.create_retrofit(conn, "Retail", "Still listed", topic_id=42)
        rows = db_retrofits.list_retrofits(conn)
        assert [r["title"] for r in rows] == ["Still listed"]
        assert rows[0]["topic_title"] is None      # link simply not shown
    finally:
        conn.close()


def test_bad_topic_id_is_ignored_not_a_crash(client):
    _add(client, title="No topic", topic_id="not-a-number")
    conn = database.get_connection(client.db_path)
    try:
        assert db_retrofits.list_retrofits(conn)[0]["topic_id"] is None
    finally:
        conn.close()


def test_retail_download_and_email_render_carries_retrofits(client):
    _add(client, channel="Retail", title="DownloadableRetrofit")

    html = client.get("/retail/report/download").get_data(as_text=True)
    assert "Retrofits — Retail" in html and "DownloadableRetrofit" in html

    from app import emailer
    conn = database.get_connection(client.db_path)
    try:
        with app.app_context():
            mailed = emailer.render_retail_html(conn, {}, "2026-08-10")
    finally:
        conn.close()
    assert "Retrofits — Retail" in mailed and "DownloadableRetrofit" in mailed


def test_emailed_retail_report_includes_impacted_defects(client):
    """Regression [2026-08-10]: render_retail_html never passed the impacted
    defects, so every emailed Retail report claimed there were none while the
    live page listed them."""
    conn = database.get_connection(client.db_path)
    try:
        conn.execute("INSERT INTO defects (defect_id, solman_name, channel,"
                     " solman_status) VALUES ('DEF-1', 'Broken thing', 'Retail',"
                     " 'In Progress')")
        conn.commit()
        from app import emailer
        with app.app_context():
            html = emailer.render_retail_html(conn, {}, "2026-08-10")
    finally:
        conn.close()
    assert "DEF-1" in html
    assert "No active Retail defects found" not in html
