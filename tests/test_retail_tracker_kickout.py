"""Payment-method kick-out + board scenario groups (2026-07-09), plus
manual voucher lines + tender type code (2026-08-06).

The rules a bug would silently break:
- kicking out REQUIRES a reason; the row leaves counting entirely and the
  active counts; reactivating clears the reason and counts again
- scenario grouping: till transactions win over the "1. Retail Sale" batch
  that textually contains them; unmatched headings land in "Other"
- manual payment-method lines (origin='manual') are NEVER pruned by
  delete_cpm_not_in; if the Excel later grows the same (country,
  method_name), upsert_cpm_rows takes it over (origin -> 'excel') but
  keeps the user's source + tender_type_code
- card is always ZPSP (template-derived, never stored); voucher/unknown
  rows carry their own tender_type_code
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


def test_bulk_kick_out_and_take_back_in(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        ids = [_cpm(conn), _cpm(conn, method="Visa"), _cpm(conn, method="Maestro")]
    finally:
        conn.close()
    client = app.test_client()

    # kicking out needs a reason, and at least one id
    assert client.post("/retail-tracker/payment-methods/bulk-active",
                       data={"ids": f"{ids[0]},{ids[1]}", "active": "0",
                             "reason": " "}).status_code == 400
    assert client.post("/retail-tracker/payment-methods/bulk-active",
                       data={"ids": "", "active": "0",
                             "reason": "x"}).status_code == 400

    resp = client.post("/retail-tracker/payment-methods/bulk-active",
                       data={"ids": f"{ids[0]},{ids[1]}", "active": "0",
                             "reason": "not able to test in testenvironment"})
    assert resp.get_json() == {"ok": True, "count": 2}

    conn = database.get_connection(db_path)
    try:
        inactive = {r["id"]: r for r in db.list_cpm(conn, inactive_only=True)}
        assert set(inactive) == {ids[0], ids[1]}
        assert all(r["inactive_reason"] == "not able to test in testenvironment"
                   for r in inactive.values())
    finally:
        conn.close()

    # mass take-back-in clears the reasons again
    resp = client.post("/retail-tracker/payment-methods/bulk-active",
                       data={"ids": f"{ids[0]},{ids[1]}", "active": "1"})
    assert resp.get_json() == {"ok": True, "count": 2}
    conn = database.get_connection(db_path)
    try:
        assert db.list_cpm(conn, inactive_only=True) == []
        assert all(r["active"] == 1 and r["inactive_reason"] is None
                   for r in db.list_cpm(conn))
    finally:
        conn.close()


@pytest.mark.parametrize("reason,expected", [
    ("not able to test in testenvironment",      True),
    ("Not able to test in test environment!",    True),   # spacing/case/punct.
    ("NOT ABLE TO TEST IN THE TESTENVIRONMENT",  True),
    ("not offered in HR anymore",                False),
    ("duplicate of Visa",                        False),
    ("",                                         False),
    (None,                                       False),
])
def test_kickout_env_blocked_matching(reason, expected):
    assert web_rt._kickout_env_blocked(reason) is expected


def test_kicked_out_page_splits_env_blocked_from_other(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        env_id = _cpm(conn)
        other_id = _cpm(conn, method="Visa")
        db.set_cpm_active(conn, env_id, False, "not able to test in testenvironment")
        db.set_cpm_active(conn, other_id, False, "duplicate of AMEX")
    finally:
        conn.close()

    html = app.test_client().get("/retail-tracker/payment-methods") \
        .get_data(as_text=True)
    assert "Not able to test in testenvironment" in html
    assert "Other reasons" in html
    # env-blocked list renders before the other-reasons list
    assert html.index("Not able to test in testenvironment") \
        < html.index("Other reasons")


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


# ---------------------------------------------------------------------------
# Manual voucher lines + tender type code [USER 2026-08-06]
# ---------------------------------------------------------------------------

def test_add_cpm_manual_creates_origin_manual_row(db_path):
    conn = database.get_connection(db_path)
    try:
        cpm_id = db.add_cpm_manual(conn, "Malta", "MyVoucher", "voucher",
                                   "ZVCH", "Marina 2026-08-06")
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["origin"] == "manual"
        assert row["category"] == "voucher"
        assert row["tender_type_code"] == "ZVCH"
        assert row["source"] == "Marina 2026-08-06"
        assert row["active"] == 1
    finally:
        conn.close()


def test_add_cpm_manual_rejects_duplicate(db_path):
    conn = database.get_connection(db_path)
    try:
        db.add_cpm_manual(conn, "Malta", "MyVoucher", "voucher", None, "src")
        with pytest.raises(ValueError):
            db.add_cpm_manual(conn, "Malta", "MyVoucher", "voucher", None, "src2")
        # the existing Excel row is also a duplicate target
        _cpm(conn, country="Croatia", method="AMEX")
        with pytest.raises(ValueError):
            db.add_cpm_manual(conn, "Croatia", "AMEX", "card", None, "src")
    finally:
        conn.close()


def test_delete_cpm_not_in_skips_manual_rows(db_path):
    conn = database.get_connection(db_path)
    try:
        excel_id = _cpm(conn, country="Croatia", method="AMEX")
        manual_id = db.add_cpm_manual(conn, "Malta", "MyVoucher", "voucher",
                                      None, "src")
        # a re-import parse that no longer contains EITHER row
        removed = db.delete_cpm_not_in(conn, set())
        assert removed == 1  # only the excel-origin row
        remaining = {r["id"] for r in db.list_cpm(conn)}
        assert remaining == {manual_id}
    finally:
        conn.close()


def test_upsert_takes_over_manual_row_keeps_source_and_tender_code(db_path):
    conn = database.get_connection(db_path)
    try:
        cpm_id = db.add_cpm_manual(conn, "Malta", "MyVoucher", "voucher",
                                   "ZVCH", "Marina 2026-08-06")
        db.upsert_cpm_rows(conn, [
            {"country": "Malta", "method_name": "MyVoucher", "category": "voucher",
             "excel_row": 42, "comment": "now in the Excel too"},
        ])
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["origin"] == "excel"
        assert row["source"] == "Marina 2026-08-06"          # untouched
        assert row["tender_type_code"] == "ZVCH"              # untouched
        assert row["excel_row"] == 42
        assert row["comment"] == "now in the Excel too"
        # now the importer's prune WOULD remove it if absent from the parse
        removed = db.delete_cpm_not_in(conn, set())
        assert removed == 1
        assert db.list_cpm(conn) == []
    finally:
        conn.close()


def test_set_cpm_tender_code_and_source(db_path):
    conn = database.get_connection(db_path)
    try:
        cpm_id = _cpm(conn, category="voucher")
        db.set_cpm_tender_code(conn, cpm_id, "ZVCH")
        db.set_cpm_source(conn, cpm_id, "Iuliia analysis")
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["tender_type_code"] == "ZVCH"
        assert row["source"] == "Iuliia analysis"
        db.set_cpm_tender_code(conn, cpm_id, "")
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["tender_type_code"] is None
    finally:
        conn.close()


def test_cpm_add_route_success_and_validation(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    client = app.test_client()

    # missing required field -> redirect with error flag, nothing created
    resp = client.post("/retail-tracker/payment-methods/add",
                       data={"country": "Malta", "method_name": "MyVoucher"})
    assert resp.status_code == 302 and "cpmerr=missing" in resp.location
    conn = database.get_connection(db_path)
    try:
        assert db.list_cpm(conn) == []
    finally:
        conn.close()

    resp = client.post("/retail-tracker/payment-methods/add",
                       data={"country": "Malta", "method_name": "MyVoucher",
                             "category": "voucher", "tender_type_code": "ZVCH",
                             "source": "Marina 2026-08-06"})
    assert resp.status_code == 302 and "cpmadded=1" in resp.location
    conn = database.get_connection(db_path)
    try:
        rows = db.list_cpm(conn)
        assert len(rows) == 1 and rows[0]["origin"] == "manual"
    finally:
        conn.close()

    # duplicate -> redirect with dup flag, no second row
    resp = client.post("/retail-tracker/payment-methods/add",
                       data={"country": "Malta", "method_name": "MyVoucher",
                             "source": "again"})
    assert resp.status_code == 302 and "cpmerr=dup" in resp.location
    conn = database.get_connection(db_path)
    try:
        assert len(db.list_cpm(conn)) == 1
    finally:
        conn.close()


def test_cpm_tender_code_and_source_routes(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        cpm_id = _cpm(conn, category="voucher")
    finally:
        conn.close()
    client = app.test_client()

    assert client.post(f"/retail-tracker/payment-methods/{cpm_id}/tender-code",
                       data={"tender_type_code": "ZVCH"}).get_json()["ok"]
    assert client.post(f"/retail-tracker/payment-methods/{cpm_id}/source",
                       data={"source": "Iuliia analysis"}).get_json()["ok"]

    conn = database.get_connection(db_path)
    try:
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["tender_type_code"] == "ZVCH"
        assert row["source"] == "Iuliia analysis"
    finally:
        conn.close()


def test_card_row_renders_fixed_zpsp_voucher_renders_input(db_path, monkeypatch):
    monkeypatch.setattr(web_rt, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        _cpm(conn, country="Croatia", method="AMEX", category="card")
        db.add_cpm_manual(conn, "Malta", "MyVoucher", "voucher", "ZVCH", "src")
    finally:
        conn.close()

    html = app.test_client().get("/retail-tracker/payment-methods").get_data(as_text=True)
    assert "ZPSP" in html
    assert 'name="pm-tendercode-' in html
    assert "manual" in html  # the origin pill on the manually added row


def test_source_backfill_on_column_creation(tmp_path):
    """The first-ever init_schema on a fresh DB creates the source column
    with no pre-existing rows — nothing to backfill, no crash. Rows added
    afterwards are NOT auto-labelled."""
    p = tmp_path / "backfill.db"
    database.init_db(p).close()
    db.init_schema(p)
    conn = database.get_connection(p)
    try:
        cpm_id = _cpm(conn)  # inserted directly, bypassing add_cpm_manual
        row = {r["id"]: r for r in db.list_cpm(conn)}[cpm_id]
        assert row["source"] is None
    finally:
        conn.close()
