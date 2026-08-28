"""CORE SOUTH Smoke Testing card (build plan step 3, 2026-08-27): upload
page + file-picker import wiring."""
import io
import re

import openpyxl
import pytest

from app import database
from app.db import smoke as db_smoke
import app.web_smoke as web_smoke
from app.web import app

_HEADER = [
    "RowID", "RowType", "WS", "Package", "Scenario", "Comment", "Status",
    "Company Code", "Sales Org.", "Plant (DC)", "Store Code",
    "MB Invoice Validation", "ParentRow", "Step", "Expected result",
    "Owner eMail", "Owner", "WS Executing", "ASPEN Ticket",
    "Execution Status", "Progress",
]
_COL = {name: i for i, name in enumerate(_HEADER)}


def _row(**vals) -> list:
    row = [None] * len(_HEADER)
    for key, val in vals.items():
        row[_COL[key]] = val
    return row


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "EU CS Smoke Test execution"
    ws.append(_HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sample_rows() -> list[list]:
    return [
        _row(RowID=100, RowType="Scenario", WS="eCOM", Package="Click & Collect",
             Scenario="Fulfill C&C order", Status="Not Started",
             **{"MB Invoice Validation": 1.0}),
        _row(RowID=101, RowType="Step", ParentRow=100, Step="Create order"),
        _row(RowID=200, RowType="Scenario", WS="Retail", Package="Store Sales",
             Scenario="Store sale FR", Status="In Progress",
             **{"Store Code": "FRBY", "MB Invoice Validation": 1.0}),
        _row(RowID=201, RowType="Step", ParentRow=200, Step="Ring up sale"),
    ]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "smoke.db"
    database.init_db(db_path).close()
    db_smoke.init_schema(db_path)
    monkeypatch.setattr(web_smoke, "_get_conn",
                        lambda: database.get_connection(db_path))
    monkeypatch.setitem(web_smoke._cfg, "database_path", str(db_path))
    monkeypatch.setattr(web_smoke, "_UPLOAD_FOLDER", tmp_path / "uploads")
    # the generic next-step archive (entity 'smoke') runs in its own module
    import app.web_next_steps as web_next_steps
    from app.db import next_steps as db_ns
    db_ns.init_schema(db_path)
    monkeypatch.setattr(web_next_steps, "_get_conn",
                        lambda: database.get_connection(db_path))
    return app.test_client()


def _upload(client, data=None, filename="EU CS Smoke Test execution.xlsx"):
    data = data if data is not None else _xlsx_bytes(_sample_rows())
    return client.post("/smoke/upload", data={
        "file": (io.BytesIO(data), filename)})


def test_home_shows_empty_state_before_import(client):
    html = client.get("/smoke/").get_data(as_text=True)
    assert "CORE SOUTH Smoke Testing" in html
    assert "No smoke test scenarios yet" in html


def test_upload_imports_and_home_shows_overview_counts(client):
    resp = _upload(client)
    assert resp.status_code == 302 and "smoke_ok=1" in resp.headers["Location"]

    html = client.get("/smoke/?smoke_ok=1&smoke_msg=x").get_data(as_text=True)
    assert "ECOM" in html and "OMNI" in html and "Retail" in html
    # sample rows: Click & Collect -> OMNI (1 scenario, not started),
    # Store Sales -> Retail (1 scenario, in progress) — eCOM/ECOM stays empty
    stat_cards = re.findall(r'<div class="num">(.*?)</div>', html)
    assert stat_cards == [
        "0", "0", "0", "0",   # ECOM: total/not_started/in_progress/completed
        "1", "1", "0", "0",   # OMNI
        "1", "0", "1", "0",   # Retail
    ]


def test_upload_rejects_non_xlsx_and_missing_file(client):
    resp = _upload(client, filename="notes.txt")
    assert "smoke_ok=0" in resp.headers["Location"]
    resp = client.post("/smoke/upload", data={})
    assert "smoke_ok=0" in resp.headers["Location"]


def test_upload_dated_copy_kept_in_uploads_folder(client, tmp_path):
    _upload(client)
    saved = list((tmp_path / "uploads").glob("smoke_*.xlsx"))
    assert len(saved) == 1


def test_upload_reports_error_when_nothing_matches(client):
    rows = [_row(RowID=1, RowType="Scenario", WS="Wholesale",
                 **{"MB Invoice Validation": 1.0})]
    resp = _upload(client, data=_xlsx_bytes(rows))
    assert "smoke_ok=0" in resp.headers["Location"]
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "No eCOM/Retail" in html


# ---------------------------------------------------------------------------
# eCOM page (build plan step 5)

def _ecom_split_rows() -> list[list]:
    return [
        _row(RowID=100, RowType="Scenario", WS="eCOM", Package="Click & Collect",
             Scenario="Fulfill Click and Collect order", Status="Not Started",
             **{"MB Invoice Validation": 1.0}),
        _row(RowID=101, RowType="Step", ParentRow=100, Step="Create order",
             Owner="Alice", **{"Expected result": "Order created",
                               "WS Executing": "GBS"}),
        _row(RowID=150, RowType="Scenario", WS="eCOM", Package="Ship from Campus South",
             Scenario="Ship standard order", Status="Completed",
             **{"MB Invoice Validation": 1.0}),
        _row(RowID=151, RowType="Step", ParentRow=150, Step="Pick and pack"),
        _row(RowID=152, RowType="Step", ParentRow=150, Step="Ship it"),
    ]


def test_ecom_page_splits_omni_and_ecom(client):
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    html = client.get("/smoke/ecom").get_data(as_text=True)
    assert "Fulfill Click and Collect order" in html
    assert "Ship standard order" in html
    # C&C is OMNI, Ship standard is ECOM — and since 2026-08-28 the ECOM
    # section comes FIRST [USER], so the ECOM scenario renders before the
    # OMNI one
    assert html.find('data-scenario="ship standard order"') \
        < html.find('data-scenario="fulfill click and collect order"')


def test_ecom_page_expands_to_show_steps(client):
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    html = client.get("/smoke/ecom").get_data(as_text=True)
    assert "Create order" in html
    assert "Order created" in html
    assert "Pick and pack" in html
    assert "Ship it" in html


def test_overview_links_ecom_and_omni_headers_to_ecom_page(client):
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    html = client.get("/smoke/").get_data(as_text=True)
    assert html.count('href="/smoke/ecom">ECOM') + html.count('href="/smoke/ecom">OMNI') == 2


# ---------------------------------------------------------------------------
# Retail page (build plan step 6)

def _retail_rows() -> list[list]:
    return [
        _row(RowID=200, RowType="Scenario", WS="Retail", Package="Store Sales",
             Scenario="Store sale FR", Status="In Progress",
             **{"Store Code": "FRBY", "MB Invoice Validation": 1.0}),
        _row(RowID=201, RowType="Step", ParentRow=200, Step="Ring up sale",
             **{"Expected result": "Sale posted"}),
        _row(RowID=210, RowType="Scenario", WS="Retail", Package="Store Return to DC",
             Scenario="Store return PT", Status="Completed",
             **{"Store Code": "PT01", "MB Invoice Validation": 1.0}),
        _row(RowID=211, RowType="Step", ParentRow=210, Step="Process return"),
    ]


def test_retail_page_lists_scenarios_with_expandable_steps(client):
    _upload(client, data=_xlsx_bytes(_retail_rows()))
    html = client.get("/smoke/retail").get_data(as_text=True)
    assert "Store sale FR" in html and "Store return PT" in html
    assert 'data-group="retail"' in html
    assert "Ring up sale" in html and "Sale posted" in html
    assert "Process return" in html


def test_overview_links_retail_header_to_retail_page(client):
    _upload(client, data=_xlsx_bytes(_retail_rows()))
    html = client.get("/smoke/").get_data(as_text=True)
    assert 'href="/smoke/retail">Retail' in html


# ---------------------------------------------------------------------------
# Scenario comment + next step (2026-08-28) — authored, keyed by RowID

def test_comment_and_next_step_save_and_render(client):
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    resp = client.post("/smoke/scenario/150/comment",
                       json={"comment": "flaky on FR store"})
    assert resp.get_json()["ok"]
    resp = client.post("/smoke/scenario/150/next-step",
                       json={"next_step": "retest after deploy"})
    assert resp.get_json()["ok"]

    html = client.get("/smoke/ecom").get_data(as_text=True)
    assert "flaky on FR store" in html          # textarea + 📝 marker
    assert "📝" in html
    assert "retest after deploy" in html        # input + summary preview

    # survives a re-import (annotations are never replaced)
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    html = client.get("/smoke/ecom").get_data(as_text=True)
    assert "flaky on FR store" in html


def test_next_step_archive_via_generic_component(client):
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    client.post("/smoke/scenario/150/next-step",
                json={"next_step": "ask the owner"})
    resp = client.post("/next-steps/smoke/150/archive")
    data = resp.get_json()
    assert data["ok"] and data["archived"] == "ask the owner"
    listing = client.get("/next-steps/smoke/150/list.json").get_json()
    assert [i["next_step"] for i in listing["items"]] == ["ask the owner"]
    # live field cleared
    html = client.get("/smoke/ecom").get_data(as_text=True)
    assert "ask the owner" not in html


# ---------------------------------------------------------------------------
# Step filters: WS Executing + Owner (2026-08-28)

def test_step_rows_carry_filter_data_and_dropdowns_list_values(client):
    _upload(client, data=_xlsx_bytes(_ecom_split_rows()))
    html = client.get("/smoke/ecom").get_data(as_text=True)
    assert 'data-ws="GBS"' in html and 'data-owner="Alice"' in html
    # dropdowns exist per group with the distinct values
    assert 'id="smoke-ws-omni"' in html and 'id="smoke-owner-omni"' in html
    omni_bar = html.split('id="smoke-ws-omni"')[1].split("</select>")[0]
    assert '<option value="GBS">GBS</option>' in omni_bar
