"""Order-details archive (2026-07-16) — grouped history batches.

The rules a bug would silently break:
- archiving copies ONLY the selected rows, as ONE batch (shared batch_id,
  archived_at, label), and removes exactly those rows from the live table
- ids belonging to another entity are ignored (no cross-entity theft)
- batches list newest first, items keep their live order
- deleting a batch removes all its rows and nothing else
"""
import pytest

from app import database
from app.db import order_archive as db_oa
import app.web_spillover as web_spillover
from app.web import app


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "oa.db"
    database.init_db(p).close()
    db_oa.init_schema(p)
    return p


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setattr(web_spillover, "_get_conn",
                        lambda: database.get_connection(db_path))
    c = app.test_client()
    c.db_path = db_path
    return c


def _add_order(conn, entity_type, entity_id, order_type, number, comment="", s4=0):
    detail_id = database.add_order_detail(conn, entity_type, entity_id)
    database.update_order_detail(conn, detail_id, order_type, number, comment, s4)
    return detail_id


def test_archive_selected_rows_as_one_batch(client):
    conn = database.get_connection(client.db_path)
    try:
        i1 = _add_order(conn, "spillover", "7", "Sales order", "4711", s4=1)
        i2 = _add_order(conn, "spillover", "7", "Return order", "4712")
        i3 = _add_order(conn, "spillover", "7", "Unrelated", "9999")
    finally:
        conn.close()

    d = client.post("/order-details/spillover/7/archive",
                    data={"ids": f"{i1},{i2}", "label": "PL run 1"}).get_json()
    assert d["ok"] and d["count"] == 2

    conn = database.get_connection(client.db_path)
    try:
        live = database.list_order_details(conn, "spillover", "7")
        assert [r["id"] for r in live] == [i3]          # only unselected row left

        batches = db_oa.list_order_batches(conn, "spillover", "7")
        assert len(batches) == 1
        b = batches[0]
        assert b["label"] == "PL run 1" and b["archived_at"]
        assert [(i["order_type"], i["order_number"]) for i in b["items"]] == [
            ("Sales order", "4711"), ("Return order", "4712")]
        assert b["items"][0]["docs_in_s4"] == 1          # S4 tick preserved
    finally:
        conn.close()


def test_batches_are_separate_and_newest_first(client):
    conn = database.get_connection(client.db_path)
    try:
        a = _add_order(conn, "ecom_gatekeeper", "3", "Sales order", "111")
        first = db_oa.archive_order_details(conn, "ecom_gatekeeper", "3", [a])
        b = _add_order(conn, "ecom_gatekeeper", "3", "Sales order", "222")
        second = db_oa.archive_order_details(conn, "ecom_gatekeeper", "3", [b])
        assert second["batch_id"] > first["batch_id"]

        batches = db_oa.list_order_batches(conn, "ecom_gatekeeper", "3")
        assert [x["items"][0]["order_number"] for x in batches] == ["222", "111"]
    finally:
        conn.close()

    d = client.get("/order-details/ecom_gatekeeper/3/history").get_json()
    assert d["count"] == 2
    assert d["batches"][0]["items"][0]["order_number"] == "222"


def test_foreign_and_missing_ids_are_ignored(client):
    conn = database.get_connection(client.db_path)
    try:
        mine   = _add_order(conn, "spillover", "1", "Sales order", "100")
        others = _add_order(conn, "spillover", "2", "Sales order", "200")

        result = db_oa.archive_order_details(conn, "spillover", "1",
                                             [mine, others, 99999])
        assert result["count"] == 1                       # only own row archived
        assert database.list_order_details(conn, "spillover", "2")  # untouched

        # nothing matching at all -> no batch written
        result = db_oa.archive_order_details(conn, "spillover", "1", [others])
        assert result["count"] == 0 and result["batch_id"] is None
        assert len(db_oa.list_order_batches(conn, "spillover", "1")) == 1
    finally:
        conn.close()

    d = client.post("/order-details/spillover/1/archive", data={"ids": ""}).get_json()
    assert not d["ok"] and "no rows" in d["error"]


def test_dialog_markup_has_archive_controls_once(client):
    html = client.get("/spillover").get_data(as_text=True)
    assert html.count('id="btn-archive-orders"') == 1
    assert html.count('id="od-history"') == 1
    assert html.count('id="od-select-all"') == 1


def test_delete_batch_removes_only_that_batch(client):
    conn = database.get_connection(client.db_path)
    try:
        a = _add_order(conn, "spillover", "5", "Sales order", "111")
        b = _add_order(conn, "spillover", "5", "Return order", "222")
        keep = db_oa.archive_order_details(conn, "spillover", "5", [a])
        kill = db_oa.archive_order_details(conn, "spillover", "5", [b])
    finally:
        conn.close()

    assert client.post(f"/order-details/history/batch/{kill['batch_id']}/delete"
                       ).get_json()["ok"]

    conn = database.get_connection(client.db_path)
    try:
        batches = db_oa.list_order_batches(conn, "spillover", "5")
        assert [x["batch_id"] for x in batches] == [keep["batch_id"]]
    finally:
        conn.close()
