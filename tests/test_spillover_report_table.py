"""Spillover status report — table form grouped by With whom (2026-07-10).

What must hold:
- the view groups into Sales -> MB -> Unassigned sections (only non-empty
  sections render), critical-first order preserved inside each
- comment_for_signoff renders as an editable input and the inline save
  route touches ONLY that field
"""
import pytest

from app import database
import app.web_reports as web_reports
import app.web_spillover as web_spillover
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "rpt.db"
    database.init_db(db_path).close()
    for mod in (web_spillover, web_reports):   # report-comment routes live in web_reports
        monkeypatch.setattr(mod, "_get_conn",
                            lambda: database.get_connection(db_path))
    conn = database.get_connection(db_path)
    try:
        with conn:
            for i, name in enumerate(["SalesItem", "MbItem", "NobodyItem"], start=1):
                conn.execute(
                    "INSERT INTO spillover (match_key, name, excel_row, first_seen,"
                    " last_seen) VALUES (?,?,?, 'd', 'd')", (name.lower(), name, i))
        ids = {r["name"]: r["spillover_id"] for r in database.get_spillover(conn)}
        database.set_spillover_with_whom(conn, ids["SalesItem"], "Sales")
        database.set_spillover_with_whom(conn, ids["MbItem"], "MB")
        database.upsert_spillover_annotation(
            conn, ids["MbItem"], None, "escalate to tech", None, "yes", "old comment", None)
        database.set_spillover_with_whom(conn, ids["MbItem"], "MB")  # re-set after full upsert
        database.include_spillover_report_ids(conn, list(ids.values()))
    finally:
        conn.close()
    c = app.test_client()
    c.db_path = db_path
    c.ids = ids
    return c


def test_view_groups_by_with_whom_in_order(client):
    html = client.get("/spillover/report/view").get_data(as_text=True)
    assert "Sales — follow-up with Sales" in html
    assert "MB — our follow-up" in html
    assert "Unassigned" in html
    # section order: Sales before MB before Unassigned
    assert (html.index("Sales — follow-up with Sales")
            < html.index("MB — our follow-up") < html.index("Unassigned"))
    # table form with the item content
    assert "rpt-table" in html and "SalesItem" in html
    assert "escalate to tech" in html
    assert 'value="old comment"' in html            # editable comment input


def test_empty_sections_do_not_render(client):
    conn = database.get_connection(client.db_path)
    try:
        # everyone becomes Sales -> MB + Unassigned sections disappear
        for sid in client.ids.values():
            database.set_spillover_with_whom(conn, sid, "Sales")
    finally:
        conn.close()
    html = client.get("/spillover/report/view").get_data(as_text=True)
    assert "Sales — follow-up with Sales" in html
    assert "MB — our follow-up" not in html
    assert "Unassigned" not in html


def test_callout_box_renders_and_add_route_roundtrip(client):
    # empty -> box rendered but marked co-empty (hidden in print/email)
    html = client.get("/spillover/report/view").get_data(as_text=True)
    assert "Call-outs" in html and "co-empty" in html

    d = client.post("/report-comments/spillover/add",
                    data={"comment": "cutover risk: SF backlog"}).get_json()
    assert d["ok"]
    html = client.get("/spillover/report/view").get_data(as_text=True)
    assert 'value="cutover risk: SF backlog"' in html
    assert 'class="callout-section"' in html          # no longer co-empty

    # update + delete via the generic routes
    client.post(f"/report-comments/{d['row']['id']}/update",
                data={"comment": "updated call-out"})
    html = client.get("/spillover/report/view").get_data(as_text=True)
    assert 'value="updated call-out"' in html
    client.post(f"/report-comments/{d['row']['id']}/delete")
    html = client.get("/spillover/report/view").get_data(as_text=True)
    assert "updated call-out" not in html

    # ecom report key is accepted now too
    assert client.post("/report-comments/ecom/add",
                       data={"comment": "x"}).get_json()["ok"]


def test_comment_signoff_route_touches_only_that_field(client):
    sid = client.ids["MbItem"]
    d = client.post(f"/spillover/{sid}/comment-signoff",
                    data={"comment_for_signoff": "waiting for SAP note"}).get_json()
    assert d["ok"]
    conn = database.get_connection(client.db_path)
    try:
        ann = database.get_spillover_annotation(conn, sid)
        assert ann["comment_for_signoff"] == "waiting for SAP note"
        assert ann["next_step"] == "escalate to tech"     # untouched
        assert ann["critical_for_signoff"] == "yes"       # untouched
        assert ann["with_whom"] == "MB"                   # untouched
    finally:
        conn.close()
