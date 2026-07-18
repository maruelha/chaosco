"""Entity connections (2026-07-18) — many-to-many topic ↔ defect / retail /
ecom / spillover links (db/entity_connections.py + /connections routes +
the _connections.html drop-in on the five detail pages).

What must hold:
- one direction-less row per pair: connecting from either side is the
  SAME row (canonical order + UNIQUE), self-connections refused
- list.json returns the OTHER side with a live label and a detail URL
- add validates types and target existence; delete disconnects
- the component renders on topic / defect / retail / ecom / spillover
  detail pages (collapsed markup present)
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import entity_connections as db_cx
from app.db import topics as db_topics
import app.web_connections as web_cx
import app.web_defects as web_defects
import app.web_retail as web_retail
import app.web_spillover as web_spillover
import app.web_ecom as web_ecom
import app.web_topics as web_topics
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cx.db"
    database.init_db(db_path).close()
    db_ecom.init_schema(db_path)
    db_topics.init_schema(db_path)
    db_cx.init_schema(db_path)
    from app.db import jira as db_jira
    db_jira.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        with conn:
            conn.execute("INSERT INTO defects (defect_id, solman_name, first_seen,"
                         " last_seen) VALUES ('D-1', 'Voucher gap', 'd', 'd')")
            conn.execute("INSERT INTO retail (match_key, test_case_id, country)"
                         " VALUES ('t|de', 'RET0001', 'Germany')")
            conn.execute("INSERT INTO spillover (match_key, name, first_seen,"
                         " last_seen) VALUES ('1', 'Spill item', 'd', 'd')")
            conn.execute("INSERT INTO ecom (match_key, jira_id, test_case_id,"
                         " country, first_seen, last_seen)"
                         " VALUES ('s4ecom-1', 'S4ECOM-1', 'TC1', 'DE', 'd', 'd')")
        topic_id = db_topics.create_topic(conn, "SF creation", None, "P2")
        ids = {
            "topic": str(topic_id),
            "retail": str(conn.execute("SELECT retail_id FROM retail").fetchone()[0]),
            "spillover": str(conn.execute("SELECT spillover_id FROM spillover").fetchone()[0]),
            "ecom": str(conn.execute("SELECT ecom_id FROM ecom").fetchone()[0]),
        }
    finally:
        conn.close()
    for mod in (web_cx, web_ecom, web_topics):
        monkeypatch.setattr(mod, "_db_path", db_path)
    for mod in (web_defects, web_retail, web_spillover):
        monkeypatch.setattr(mod, "_get_conn",
                            lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    c.ids = ids
    return c


def test_pair_is_directionless_and_deduped(client):
    tid = client.ids["topic"]
    assert client.post(f"/connections/topic/{tid}/add",
                       data={"target_type": "defect", "target_id": "D-1"}).get_json()["ok"]
    # same pair from the OTHER side -> refused as existing
    d = client.post("/connections/defect/D-1/add",
                    data={"target_type": "topic", "target_id": tid}).get_json()
    assert not d["ok"] and "already connected" in d["error"]
    # self-connection refused
    d = client.post(f"/connections/topic/{tid}/add",
                    data={"target_type": "topic", "target_id": tid}).get_json()
    assert not d["ok"]
    # missing target refused
    d = client.post(f"/connections/topic/{tid}/add",
                    data={"target_type": "defect", "target_id": "NOPE"}).get_json()
    assert "does not exist" in d["error"]


def test_list_shows_other_side_with_label_and_url(client):
    tid = client.ids["topic"]
    for t in ("retail", "spillover", "ecom"):
        client.post(f"/connections/topic/{tid}/add",
                    data={"target_type": t, "target_id": client.ids[t]})
    client.post(f"/connections/topic/{tid}/add",
                data={"target_type": "defect", "target_id": "D-1"})

    items = client.get(f"/connections/topic/{tid}/list.json").get_json()
    assert len(items) == 4
    by_type = {i["type"]: i for i in items}
    assert by_type["defect"]["label"] == "D-1 — Voucher gap"
    assert by_type["defect"]["url"] == "/defects/D-1"
    assert by_type["retail"]["label"] == "RET0001 / Germany"
    assert by_type["retail"]["url"].startswith("/retail/")
    assert by_type["ecom"]["url"].startswith("/ecom/")
    assert by_type["spillover"]["label"] == "Spill item"

    # the defect sees the topic back
    back = client.get("/connections/defect/D-1/list.json").get_json()
    assert back[0]["type"] == "topic" and back[0]["label"] == "SF creation"

    # disconnect removes it for both sides
    client.post(f"/connections/{by_type['defect']['id']}/delete")
    assert client.get("/connections/defect/D-1/list.json").get_json() == []
    assert len(client.get(f"/connections/topic/{tid}/list.json").get_json()) == 3


def test_component_renders_on_all_five_detail_pages(client):
    urls = [f"/topics/{client.ids['topic']}", "/defects/D-1",
            f"/retail/{client.ids['retail']}",
            f"/ecom/{client.ids['ecom']}",
            f"/spillover/{client.ids['spillover']}"]
    for url in urls:
        html = client.get(url).get_data(as_text=True)
        assert 'id="cx-root"' in html, url
        assert "Connected items" in html, url
