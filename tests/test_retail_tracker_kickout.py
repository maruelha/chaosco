"""Payment-method kick-out + board scenario groups (2026-07-09).

The rules a bug would silently break:
- kicking out REQUIRES a reason; the row leaves counting entirely and the
  active counts; reactivating clears the reason and counts again
- scenario grouping: till transactions win over the "1. Retail Sale" batch
  that textually contains them; unmatched headings land in "Other"
"""
import pytest

from app import database
from app import db_retail_tracker as db
import app.web_retail_tracker as web_rt
from app.retail_tracker_counting import compute_cpm
from app.web import app


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "kick.db"
    database.init_db(p).close()
    db.init_schema(p)
    return p


def _cpm(conn, country="Croatia", method="AMEX", category="card"):
    with conn:
        cur = conn.execute(
            "INSERT INTO country_payment_methods (country, method_name, category,"
            " active, created_at) VALUES (?,?,?,1,'now')", (country, method, category))
    return cur.lastrowid


def test_kick_out_leaves_counting_and_reactivate_returns(db_path):
    conn = database.get_connection(db_path)
    try:
        cpm_id = _cpm(conn)
        _cpm(conn, method="Visa")

        db.set_cpm_active(conn, cpm_id, False, "not offered in HR anymore")
        rows = db.list_cpm(conn)
        by_id = {r["id"]: r for r in rows}
        assert by_id[cpm_id]["active"] == 0
        assert by_id[cpm_id]["inactive_reason"] == "not offered in HR anymore"

        # counting skips it entirely
        result = compute_cpm(rows, {}, set(), {})
        assert result["summary"]["total"] == 1

        counts = db.cpm_counts(conn)
        assert counts["total"] == 1 and counts["inactive"] == 1

        assert [r["id"] for r in db.list_cpm(conn, inactive_only=True)] == [cpm_id]

        db.set_cpm_active(conn, cpm_id, True)
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["active"] == 1 and row["inactive_reason"] is None
        assert db.cpm_counts(conn)["total"] == 2
    finally:
        conn.close()


def test_kick_out_route_requires_reason(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        cpm_id = _cpm(conn)
    finally:
        conn.close()
    client = app.test_client()

    resp = client.post(f"/retail-tracker/payment-methods/{cpm_id}/active",
                       data={"active": "0", "reason": "  "})
    assert resp.status_code == 400

    resp = client.post(f"/retail-tracker/payment-methods/{cpm_id}/active",
                       data={"active": "0", "reason": "duplicate of Visa"})
    assert resp.get_json()["ok"]

    conn = database.get_connection(db_path)
    try:
        assert db.list_cpm(conn, inactive_only=True)[0]["inactive_reason"] \
            == "duplicate of Visa"
    finally:
        conn.close()

    # kicked-out section renders with reason + the row is out of the matrix
    html = client.get("/retail-tracker/payment-methods").get_data(as_text=True)
    assert "Kicked out" in html and "duplicate of Visa" in html


@pytest.mark.parametrize("label,expected", [
    ("1. Retail Sale – e. suspend",                 "Till transactions"),
    ("1. Retail Sale – f. retrieve",                "Till transactions"),
    ("1. Retail Sale – d. sales cancellation",      "Till transactions"),
    ("1. Retail Sale – b) different article types", "Different articles (first batch)"),
    ("7. Discounts",                                "Discounts"),
    ("8. Payment Methods General",                  "General payment methods"),
    ("Payment methods – Return",                    "General payment methods"),
    ("5. B2B invoice",                              "B2B"),
    ("4. Promat / FOC sale",                        "PROMAT/FOC"),
    ("3. Exchange (question if we need)",           "Other"),
    (None,                                          "Other"),
])
def test_scenario_group_mapping(label, expected):
    assert web_rt._scenario_group(label) == expected
