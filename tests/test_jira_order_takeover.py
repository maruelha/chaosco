"""Jira acceptance-criteria takeover for order details (2026-07-16).

Decisions [USER]: acceptance criteria ONLY (comment numbers never offered),
archived numbers count as present, takeover only ADDS missing rows.
What must hold:
- extract_ac_order_pairs: label+number pairs, XXXX placeholders skipped,
  duplicate numbers deduped
- suggestions = AC numbers covered by NO live or archived order row
  (case-insensitive; a row covers a number it equals or contains)
- take-over inserts exactly the missing pairs, never touches existing rows,
  and is a no-op when re-run
"""
import pytest

from app import database
from app.db import jira as db_jira
from app.db import order_archive as db_oa
import app.web_reference as web_reference
import app.web_spillover as web_spillover
from app.jira_importer import extract_ac_order_pairs
from app.web import app

JIRA = "S4ECOM-777"
AC = ("Checklist:\n"
      "Sales Order: TBY_SS_ADE0006955\n"
      "Return Order - TBY_RT_ADE0007001\n"
      "Exchange Order: XXXX\n"           # placeholder -> skipped
      "Sales Order: TBY_SS_ADE0006955\n")  # duplicate -> deduped


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "takeover.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_oa.init_schema(db_path)
    monkeypatch.setattr(web_reference, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setattr(web_spillover, "_get_conn",
                        lambda: database.get_connection(db_path))
    conn = database.get_connection(db_path)
    try:
        db_jira.upsert_jira_issues(conn, [{
            "jira_key": JIRA, "summary": "SM7_Case",
            "acceptance_criteria": AC,
            "comments": [{"created": "Mon",
                          "body": "Order: TBY_CM_ADE0009999 from a comment"}],
        }])
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    return c


def test_extract_ac_order_pairs_skips_placeholders_and_dupes():
    pairs = extract_ac_order_pairs(AC)
    assert pairs == [
        {"order_type": "Sales Order", "order_number": "TBY_SS_ADE0006955"},
        {"order_type": "Return Order", "order_number": "TBY_RT_ADE0007001"},
    ]
    assert extract_ac_order_pairs(None) == []


def test_suggestions_ac_only_and_archived_counts_as_present(client):
    # empty order list -> both AC numbers missing; the comment number is NOT
    d = client.get(f"/order-details/jira/{JIRA}/jira-suggestions").get_json()
    assert [m["order_number"] for m in d["missing"]] == [
        "TBY_SS_ADE0006955", "TBY_RT_ADE0007001"]
    assert all("9999" not in m["order_number"] for m in d["missing"])

    conn = database.get_connection(client.db_path)
    try:
        # live row covers the sales order (case-insensitive)
        i1 = database.add_order_detail_full(conn, "jira", JIRA,
                                            "Sales", "tby_ss_ade0006955")
        # archived row covers the return order
        i2 = database.add_order_detail_full(conn, "jira", JIRA,
                                            "Return", "TBY_RT_ADE0007001")
        db_oa.archive_order_details(conn, "jira", JIRA, [i2], "chain 1")
    finally:
        conn.close()

    d = client.get(f"/order-details/jira/{JIRA}/jira-suggestions").get_json()
    assert d["missing"] == []

    # unknown ticket -> no suggestions, no error
    d = client.get("/order-details/jira/NOPE-1/jira-suggestions").get_json()
    assert d["ok"] and d["missing"] == []


def test_take_over_adds_only_missing_and_is_idempotent(client):
    conn = database.get_connection(client.db_path)
    try:
        database.add_order_detail_full(conn, "jira", JIRA,
                                       "Sales order", "TBY_SS_ADE0006955")
    finally:
        conn.close()

    d = client.post(f"/order-details/jira/{JIRA}/take-over-jira").get_json()
    assert d["ok"]
    assert [(a["order_type"], a["order_number"]) for a in d["added"]] == [
        ("Return Order", "TBY_RT_ADE0007001")]

    conn = database.get_connection(client.db_path)
    try:
        rows = database.list_order_details(conn, "jira", JIRA)
        assert [(r["order_type"], r["order_number"]) for r in rows] == [
            ("Sales order", "TBY_SS_ADE0006955"),      # untouched
            ("Return Order", "TBY_RT_ADE0007001")]     # added from AC
    finally:
        conn.close()

    # everything covered now -> second click adds nothing
    d = client.post(f"/order-details/jira/{JIRA}/take-over-jira").get_json()
    assert d["ok"] and d["added"] == []
