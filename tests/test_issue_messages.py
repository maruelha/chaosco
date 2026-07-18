"""Issue-message builder (2026-07-16).

[USER decisions]: message types = editable table with TIBCO/IIB APIs +
comment (own card, seeded with the 8 defaults); special texts FIXED in
code; context header per screen (jira -> SolMan ID, retail -> tc/country,
spillover -> name + external id); ✉️ button on rows + detail pages.
What must hold:
- seed runs once (only when empty); CRUD roundtrip
- meta.json serves types + the 8 fixed templates
- context per entity type collects the right identifier + labeled orders
- build_message: header + resolved placeholders + API line; no highlighted
  orders -> full list stands in
- save-note lands on the entity with source='issue-msg'
"""
import pytest

from app import database
from app.db import jira as db_jira
from app.db import message_types as db_mt
from app.issue_messages import SPECIAL_TEXTS, build_message
import app.web_issue_msg as web_im
from app.web import app

JIRA = "S4ECOM-9"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "im.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_mt.init_schema(db_path)
    monkeypatch.setattr(web_im, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def test_seed_once_and_crud(client):
    conn = database.get_connection(client.db_path)
    try:
        types = db_mt.list_message_types(conn)
        assert [t["name"] for t in types][:2] == ["Reservation order", "Sales order"]
        assert len(types) == 8
        db_mt._seed_defaults(conn)                        # idempotent
        assert len(db_mt.list_message_types(conn)) == 8
    finally:
        conn.close()

    d = client.post("/message-types/add",
                    data={"name": "Credit memo", "tibco_api": "tib.credit"}).get_json()
    assert d["ok"]
    client.post(f"/message-types/{d['id']}/update",
                data={"name": "Credit memo", "tibco_api": "tib.credit.v2",
                      "iib_api": "iib.credit", "comment": "rare"})
    conn = database.get_connection(client.db_path)
    try:
        row = [t for t in db_mt.list_message_types(conn) if t["name"] == "Credit memo"][0]
        assert row["tibco_api"] == "tib.credit.v2" and row["iib_api"] == "iib.credit"
    finally:
        conn.close()
    assert client.post(f"/message-types/{d['id']}/delete").get_json()["ok"]

    meta = client.get("/issue-msg/meta.json").get_json()
    assert len(meta["types"]) == 8
    assert [t["key"] for t in meta["templates"]] == [t["key"] for t in SPECIAL_TEXTS]


def test_build_message_assembly():
    text = build_message(
        "8000123", ["A1", "B2", "C3"],
        "please check why {message} message not created in s4 for {orders}",
        "Sales billing", ["B2"], tibco_api="tib.sales", iib_api=None)
    assert text == ("8000123 — orders: A1, B2, C3\n\n"
                    "please check why Sales billing message not created in s4 for B2\n\n"
                    "TIBCO: tib.sales")
    # no highlighted orders -> full list stands in; no APIs -> no API line
    text = build_message("TC1 / DE", ["A1", "B2"],
                         "issue with the {message} {orders}", "Sales order", [])
    assert text == "TC1 / DE — orders: A1, B2\n\nissue with the Sales order A1, B2"

    # check_tibco: {tibco_api} appends " (api)" to the sentence — or nothing
    tibco_tpl = [t for t in SPECIAL_TEXTS if t["key"] == "check_tibco"][0]["text"]
    text = build_message("8000123", ["A1"], tibco_tpl, "Sales order", [],
                         tibco_api="tib.sales")
    assert ("please check if the Sales order message for the A1"
            " has reached tibco (tib.sales)") in text
    text = build_message("8000123", ["A1"], tibco_tpl, "Sales order", [])
    assert text.endswith("has reached tibco")


def test_context_per_entity_type(client):
    conn = database.get_connection(client.db_path)
    try:
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": JIRA, "solman_id": "8000777", "summary": "S", "comments": []}])
        database.add_order_detail_full(conn, "jira", JIRA, "Sales order", "TBY_1")
        with conn:
            conn.execute(
                "INSERT INTO retail (match_key, test_case_id, country, order_number,"
                " s4_billing_documents) VALUES ('t1|de', 'RET0001', 'Germany', 'R-100', 'B-200')")
            conn.execute(
                "INSERT INTO spillover (match_key, name, external_id, order_numbers,"
                " first_seen, last_seen) VALUES ('7', 'Voucher gap', 'SOL-1', '555, 556', 'd', 'd')")
        rid = conn.execute("SELECT retail_id FROM retail").fetchone()[0]
        sid = conn.execute("SELECT spillover_id FROM spillover").fetchone()[0]
        database.add_order_detail_full(conn, "spillover", str(sid), "Return order", "557")
    finally:
        conn.close()

    d = client.get(f"/issue-msg/context/jira/{JIRA}").get_json()
    assert d["ident"] == "8000777"
    assert d["orders"] == [{"label": "Sales order", "number": "TBY_1"}]

    d = client.get(f"/issue-msg/context/retail/{rid}").get_json()
    assert d["ident"] == "RET0001 / Germany"
    assert d["orders"] == [{"label": "Order", "number": "R-100"},
                           {"label": "S4 billing", "number": "B-200"}]

    d = client.get(f"/issue-msg/context/spillover/{sid}").get_json()
    assert d["ident"] == "Voucher gap (SOL-1)"
    assert d["orders"] == [{"label": "Return order", "number": "557"},
                           {"label": "Imported orders", "number": "555, 556"}]

    assert client.get("/issue-msg/context/nonsense/1").status_code == 404


def test_save_note_lands_on_entity(client):
    d = client.post(f"/issue-msg/jira/{JIRA}/save-note",
                    data={"heading": "Issue message — Check in TIBCO",
                          "text": "8000777 — orders: TBY_1\n\nplease check…"}).get_json()
    assert d["ok"]
    conn = database.get_connection(client.db_path)
    try:
        notes = database.list_notes(conn, "jira", JIRA)
        assert notes[0]["heading"] == "Issue message — Check in TIBCO"
        assert notes[0]["source"] == "issue-msg"
    finally:
        conn.close()

    assert not client.post(f"/issue-msg/jira/{JIRA}/save-note",
                           data={"text": ""}).get_json()["ok"]
    assert client.post("/issue-msg/todo/1/save-note",
                       data={"text": "x"}).status_code == 404
