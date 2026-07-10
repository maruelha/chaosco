"""Next-step archive component (2026-07-10) — generic across verticals.

The rules a bug would silently break:
- archiving stores the CURRENT value with a timestamp and clears ONLY the
  next-step field (other annotation fields untouched)
- an empty field archives nothing (clear error, no history entry)
- history is per (entity_type, entity_id); newest first; deletable
- the ecom entry resolves ecom_id -> jira_id (annotations key) correctly
"""
import pytest

from app import database
from app.db import ecom as db_ecom
from app.db import next_steps as db_ns
import app.web_next_steps as web_ns
from app.web import app


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "ns.db"
    database.init_db(p).close()
    db_ns.init_schema(p)
    db_ecom.init_schema(p)
    return p


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setattr(web_ns, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def test_spillover_archive_clears_only_next_step(client):
    conn = database.get_connection(client.db_path)
    try:
        with conn:
            conn.execute("INSERT INTO spillover (match_key, name, first_seen, last_seen)"
                         " VALUES ('a', 'Alpha', 'd', 'd')")
        sid = conn.execute("SELECT spillover_id FROM spillover").fetchone()[0]
        database.upsert_spillover_annotation(
            conn, sid, "high", "chase the SF creation", "history", "yes", "c", "g")
    finally:
        conn.close()

    d = client.post(f"/next-steps/spillover/{sid}/archive").get_json()
    assert d["ok"] and d["archived"] == "chase the SF creation" and d["count"] == 1

    conn = database.get_connection(client.db_path)
    try:
        ann = database.get_spillover_annotation(conn, sid)
        assert ann["next_step"] is None                       # cleared
        assert ann["importance_for_signoff"] == "high"        # untouched
        assert ann["critical_for_signoff"] == "yes"           # untouched
        items = db_ns.list_next_step_history(conn, "spillover", str(sid))
        assert [i["next_step"] for i in items] == ["chase the SF creation"]
        assert items[0]["archived_at"]
    finally:
        conn.close()

    # empty now -> archiving again refuses, no second entry
    d = client.post(f"/next-steps/spillover/{sid}/archive").get_json()
    assert not d["ok"] and "empty" in d["error"]


def test_ecom_archive_resolves_jira_key(client):
    conn = database.get_connection(client.db_path)
    try:
        db_ecom.upsert_ecom_rows(conn, [{
            "jira_id": "S4ECOM-7", "status": "Not Ready", "assigned_to": "",
            "country": "DE", "testcase_scenario": "X", "test_case_id": "T1",
            "testcase_name": "T1_case", "description_change": "",
            "execution_started": "", "order_number": "", "old_order_numbers": "",
            "defect_id_ref": "", "s4_sales_order": "", "s4_billing_documents": "",
            "s4_journal_invoice_entry": "", "delivery_note": "",
            "reason_for_pass_with_reservation": "", "comment": "",
            "excel_row": 2, "_skip_reason": ""}], "2026-07-10")
        ecom_id = db_ecom.get_ecom_rows(conn)[0]["ecom_id"]
        db_ecom.upsert_ecom_annotation(conn, "S4ECOM-7", next_step="ping key user")
    finally:
        conn.close()

    d = client.post(f"/next-steps/ecom/{ecom_id}/archive").get_json()
    assert d["ok"] and d["archived"] == "ping key user"

    conn = database.get_connection(client.db_path)
    try:
        assert db_ecom.get_ecom_by_id(conn, ecom_id)["next_step"] is None
        # history is addressed by the PAGE id (ecom_id), not the jira key
        assert db_ns.list_next_step_history(conn, "ecom", str(ecom_id))
    finally:
        conn.close()


def test_defect_and_retail_registry_entries(client):
    conn = database.get_connection(client.db_path)
    try:
        with conn:
            conn.execute("INSERT INTO defects (defect_id, channel) VALUES ('D-1', 'Retail')")
            conn.execute("INSERT INTO retail (match_key, test_case_id, country)"
                         " VALUES ('t1|de', 'T1', 'Germany')")
        rid = conn.execute("SELECT retail_id FROM retail").fetchone()[0]
        database.set_defect_next_step(conn, "D-1", "retest after fix")
        database.set_retail_next_step(conn, rid, "ask Jose")
    finally:
        conn.close()

    assert client.post("/next-steps/defect/D-1/archive").get_json()["ok"]
    assert client.post(f"/next-steps/retail/{rid}/archive").get_json()["ok"]

    conn = database.get_connection(client.db_path)
    try:
        assert database.get_defect_next_step(conn, "D-1") is None
        assert database.get_retail_annotation(conn, rid)["next_step"] is None
    finally:
        conn.close()


def test_history_list_newest_first_and_delete(client):
    conn = database.get_connection(client.db_path)
    try:
        db_ns.archive_next_step(conn, "defect", "D-9", "first step")
        eid = db_ns.archive_next_step(conn, "defect", "D-9", "second step")
        db_ns.archive_next_step(conn, "defect", "OTHER", "unrelated")
    finally:
        conn.close()

    d = client.get("/next-steps/defect/D-9/list.json").get_json()
    assert d["count"] == 2
    assert [i["next_step"] for i in d["items"]] == ["second step", "first step"]

    client.post(f"/next-steps/entry/{eid}/delete")
    d = client.get("/next-steps/defect/D-9/list.json").get_json()
    assert [i["next_step"] for i in d["items"]] == ["first step"]


def test_unknown_entity_type_404s(client):
    assert client.post("/next-steps/nonsense/1/archive").status_code == 404
