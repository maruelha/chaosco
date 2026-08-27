"""Known Production Issues (rename + rebuild, 2026-08-06).

What must hold:
- new fields (channel, type, scenario dropdown, sub_case, how_to_detect,
  how_to_handle) save and round-trip on create + edit
- an existing free-text scenario not in the fixed list stays visible
  (never silently lost or forced)
- list page: Channel/Scenario columns + filters, note count on Edit
- inbox filing target 'prod_defect': search + file + nonexistent refused
- download route produces a standalone snapshot; email pre-tick + the
  gather_attachments branch both work
"""
from pathlib import Path

import pytest

from app import database, emailer
from app.db import email as db_email
import app.web_core as web_core
import app.web_email as web_email
from app.web import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "prod_defects.db"
    database.init_db(db_path).close()
    db_email.init_schema(db_path)
    monkeypatch.setattr(web_core, "_db_path", db_path)
    monkeypatch.setattr(web_email, "_db_path", db_path)
    c = app.test_client()
    c.db_path = db_path
    return c


def _new(client, **fields):
    base = {"short_description": "issue", "scenario": "GWC"}
    base.update(fields)
    resp = client.post("/prod_defects/new", data=base)
    record_id = int(resp.headers["Location"].split("/prod_defects/")[1].split("?")[0])
    return record_id


def test_create_and_edit_round_trip_new_fields(client):
    record_id = _new(client, channel="ECOM", type="Defect",
                     sub_case="several items in one order row, GWC applied",
                     how_to_detect="check order lines for GWC flag",
                     how_to_handle="manual credit note")
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["channel"] == "ECOM"
    assert row["type"] == "Defect"
    assert row["sub_case"] == "several items in one order row, GWC applied"
    assert row["how_to_detect"] == "check order lines for GWC flag"
    assert row["how_to_handle"] == "manual credit note"
    assert row["scenario"] == "GWC"

    client.post(f"/prod_defects/{record_id}", data={
        "short_description": "issue", "scenario": "SFDC", "channel": "Retail",
        "type": "Risk", "how_to_handle": "escalate",
    })
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["channel"] == "Retail" and row["type"] == "Risk"
    assert row["scenario"] == "SFDC"
    assert row["how_to_handle"] == "escalate"


# ---------------------------------------------------------------------------
# Unique display id: ECOM-001 / RETAIL-001 [USER 2026-08-27]

def test_display_id_assigned_sequentially_per_channel(client):
    ecom1 = _new(client, channel="ECOM")
    retail1 = _new(client, channel="Retail")
    ecom2 = _new(client, channel="ECOM")
    conn = database.get_connection(client.db_path)
    try:
        e1 = database.get_known_prod_defect(conn, ecom1)
        r1 = database.get_known_prod_defect(conn, retail1)
        e2 = database.get_known_prod_defect(conn, ecom2)
    finally:
        conn.close()
    assert e1["display_id"] == "ECOM-001"
    assert r1["display_id"] == "RETAIL-001"
    assert e2["display_id"] == "ECOM-002"


def test_display_id_none_without_a_channel(client):
    record_id = _new(client)  # no channel picked
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["display_id"] is None


def test_display_id_never_changes_when_channel_is_edited(client):
    record_id = _new(client, channel="ECOM")
    client.post(f"/prod_defects/{record_id}", data={
        "short_description": "issue", "scenario": "GWC", "channel": "Retail"})
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["display_id"] == "ECOM-001"  # stays put even though channel changed
    assert row["channel"] == "Retail"


def test_display_id_backfilled_for_legacy_rows_oldest_first(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = database.init_db(db_path)
    conn.execute(
        "INSERT INTO known_prod_defects (short_description, channel, created_at, updated_at)"
        " VALUES (?, ?, ?, ?)",
        ("Old ECOM issue", "ECOM", "2026-01-01T00:00:00", "2026-01-01T00:00:00"))
    conn.execute(
        "INSERT INTO known_prod_defects (short_description, channel, created_at, updated_at)"
        " VALUES (?, ?, ?, ?)",
        ("Old Retail issue", "Retail", "2026-01-02T00:00:00", "2026-01-02T00:00:00"))
    conn.commit()
    conn.close()

    database.init_db(db_path).close()  # re-run migrations, same as app startup

    conn = database.get_connection(db_path)
    try:
        rows = {r["short_description"]: r["display_id"]
                for r in database.list_known_prod_defects(conn, status=None)}
    finally:
        conn.close()
    assert rows["Old ECOM issue"] == "ECOM-001"
    assert rows["Old Retail issue"] == "RETAIL-001"


def test_relevant_checkboxes_round_trip(client):
    record_id = _new(client, relevant_core_south="on")  # GBS Ops left unchecked
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["relevant_core_south"] == 1
    assert row["relevant_gbs_ops"] == 0
    html = client.get(f"/prod_defects/{record_id}").get_data(as_text=True)
    cs_field = html.split('id="f-relevant-cs"')[1].split(">")[0]
    gbs_field = html.split('id="f-relevant-gbs"')[1].split(">")[0]
    assert "checked" in cs_field
    assert "checked" not in gbs_field

    client.post(f"/prod_defects/{record_id}", data={
        "short_description": "issue", "scenario": "GWC", "relevant_gbs_ops": "on",
    })  # Core South left unchecked this time
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["relevant_core_south"] == 0
    assert row["relevant_gbs_ops"] == 1


def test_relevant_checkboxes_shown_and_checked_in_expanded_row(client):
    record_id = _new(client, relevant_core_south="on")
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "Relevant for Core South" in html and "Relevant for GBS Ops" in html
    row_html = html.split(f'<details class="kpd-row" data-id="{record_id}">')[1].split("</details>")[0]
    cs_cb = row_html.split('class="kpd-cs-toggle"')[1].split(">")[0]
    gbs_cb = row_html.split('class="kpd-gbs-toggle"')[1].split(">")[0]
    assert "checked" in cs_cb
    assert "checked" not in gbs_cb


def test_relevant_toggle_routes_update_the_record(client):
    record_id = _new(client)
    resp = client.post(f"/prod_defects/{record_id}/relevant-core-south", data={"value": "1"})
    assert resp.get_json()["ok"]
    resp = client.post(f"/prod_defects/{record_id}/relevant-gbs-ops", data={"value": "1"})
    assert resp.get_json()["ok"]
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["relevant_core_south"] == 1 and row["relevant_gbs_ops"] == 1

    resp = client.post(f"/prod_defects/{record_id}/relevant-core-south", data={"value": "0"})
    assert resp.get_json()["ok"]
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row["relevant_core_south"] == 0 and row["relevant_gbs_ops"] == 1


def test_relevant_filters_narrow_the_list(client):
    cs_id = _new(client, short_description="CSOnly", scenario="GWC", relevant_core_south="on")
    _new(client, short_description="Neither", scenario="GWC")

    html = client.get("/prod_defects?relevant_core_south=yes").get_data(as_text=True)
    assert "CSOnly" in html and "Neither" not in html

    html = client.get("/prod_defects?relevant_core_south=no").get_data(as_text=True)
    assert "CSOnly" not in html and "Neither" in html

    html = client.get("/prod_defects?relevant_gbs_ops=yes").get_data(as_text=True)
    assert "CSOnly" not in html and "Neither" not in html

    html = client.get(f"/prod_defects?relevant_core_south=yes").get_data(as_text=True)
    assert 'value="yes" selected' in html
    assert ">Clear</a>" in html
    assert cs_id  # keep the id referenced


def test_risk_and_limitation_rows_have_no_fixed_button_or_relevant_checkboxes(client):
    """[USER 2026-08-27]: "the risk and limitations do NOT need the mark
    as fixed button or the core south GBS ops check list" — Delete stays,
    everything else is dropped, not just hidden."""
    _new(client, short_description="RiskRow", scenario="GWC", type="Risk", relevant_gbs_ops="on")
    _new(client, short_description="LimitationRow", scenario="GWC", type="Limitation",
        relevant_core_south="on")
    html = client.get("/prod_defects").get_data(as_text=True)
    body = html.split("<script>")[0]  # scripts always reference the button/checkbox classes
    _, limitation_html, risk_html = _split_sections(body)

    for section_html in (limitation_html, risk_html):
        assert "kpd-fix-btn" not in section_html
        assert "kpd-cs-toggle" not in section_html
        assert "kpd-gbs-toggle" not in section_html
        assert "kpd-del-btn" in section_html


def test_legacy_scenario_not_in_fixed_list_stays_visible(client):
    record_id = _new(client, scenario="A very old free-text scenario")
    html = client.get(f"/prod_defects/{record_id}").get_data(as_text=True)
    assert "A very old free-text scenario (current)" in html
    assert 'selected>A very old free-text scenario (current)' in html \
        or "A very old free-text scenario (current)</option>" in html


def test_list_shows_id_scenario_subcase_and_filters(client):
    ecom_id = _new(client, short_description="EcomIssue", scenario="GWC", channel="ECOM",
                   type="Defect", sub_case="a specific sub-case")
    _new(client, short_description="RetailIssue", scenario="SFDC", channel="Retail", type="Risk")

    html = client.get("/prod_defects").get_data(as_text=True)
    assert "Known Production Issues" in html
    assert "ECOM-001" in html  # display id shown
    assert "a specific sub-case" in html
    assert "EcomIssue" in html and "RetailIssue" in html  # RetailIssue (Risk) is in the Risks table
    assert 'id="f-channel"' in html  # Channel stays filterable even though it's not a column
    assert 'id="f-type"' not in html  # Type filter dropped along with the column

    html = client.get("/prod_defects?channel=ECOM").get_data(as_text=True)
    assert "EcomIssue" in html and "RetailIssue" not in html

    html = client.get("/prod_defects?scenario=SFDC").get_data(as_text=True)
    assert "RetailIssue" in html and "EcomIssue" not in html

    conn = database.get_connection(client.db_path)
    try:
        database.add_note(conn, "prod_defect", str(ecom_id), heading="h", note_text="n")
    finally:
        conn.close()
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "Edit (1)" in html


def test_list_presorted_by_scenario(client):
    _new(client, short_description="C", scenario="Zebra scenario")
    _new(client, short_description="A", scenario="Apple scenario")
    _new(client, short_description="B", scenario="Middle scenario")
    conn = database.get_connection(client.db_path)
    try:
        rows = database.list_known_prod_defects(conn)
    finally:
        conn.close()
    assert [r["scenario"] for r in rows] == ["Apple scenario", "Middle scenario", "Zebra scenario"]


def test_marketplace_scenario_option_available(client):
    import app.web_defects as web_defects
    assert "Marketplace" in web_defects._prod_defect_scenarios()


def test_biz_impact_not_truncated(client):
    long_impact = ("This is a much longer business impact description than the "
                   "old 200px truncation allowed to show " * 2).strip()
    _new(client, short_description="LongTextRow", scenario="GWC", biz_impact=long_impact)
    html = client.get("/prod_defects").get_data(as_text=True)
    assert long_impact in html
    assert "kpd-truncate" not in html


def test_sub_case_shown_confluence_removed_how_to_detect_and_handle_shown(client):
    _new(client, short_description="SubCaseRow", scenario="GWC",
        sub_case="specific edge case text", how_to_detect="detect it this way",
        how_to_handle="handle it this way", confluence="should-not-render-either")
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "specific edge case text" in html
    assert "detect it this way" in html
    assert "handle it this way" in html
    assert "should-not-render-either" not in html


def test_confluence_link_rendered_from_config(client, monkeypatch):
    import app.web_defects as web_defects
    monkeypatch.setitem(web_defects._cfg, "prod_defects_confluence_url",
                        "https://confluence.example/page")
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "https://confluence.example/page" in html


def test_inbox_filing_target(client):
    record_id = _new(client, short_description="Findable issue", scenario="GWC")
    conn = database.get_connection(client.db_path)
    try:
        note_id = database.add_inbox_item(conn, "H", "route me")
    finally:
        conn.close()

    hits = client.get("/inbox/targets?type=prod_defect&q=Findable").get_json()
    assert hits and hits[0]["value"] == str(record_id)

    conn = database.get_connection(client.db_path)
    try:
        assert database.file_inbox_item(conn, note_id, "prod_defect", str(record_id))
        assert database.list_notes(conn, "prod_defect", str(record_id))
        # nonexistent target refused
        assert not database.file_inbox_item(conn, note_id, "prod_defect", "99999")
    finally:
        conn.close()


def test_inbox_picker_has_known_prod_issue_option(client):
    conn = database.get_connection(client.db_path)
    try:
        database.add_inbox_item(conn, "H", "text")
    finally:
        conn.close()
    html = client.get("/inbox").get_data(as_text=True)
    assert '<option value="prod_defect">Known Prod Issue</option>' in html


def test_download_route_produces_standalone_snapshot(client):
    _new(client, short_description="DownloadRow", scenario="GWC")
    resp = client.get("/prod_defects/download")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "known_prod_defects_" in resp.headers["Content-Disposition"]
    html = resp.get_data(as_text=True)
    assert "DownloadRow" in html
    assert "<script" not in html                # standalone_html strips scripts
    assert ",form," in html                     # forms hidden via injected CSS rule


def test_download_review_route_no_edit_delete_has_comment_widget(client):
    _new(client, short_description="ReviewRow", scenario="GWC", channel="ECOM", type="Defect")
    resp = client.get("/prod_defects/download-review")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "known_prod_defects_review_" in resp.headers["Content-Disposition"]
    html = resp.get_data(as_text=True)
    assert "ReviewRow" in html
    assert "Detail</button>" in html
    assert "kpd-detail-" in html                # per-row read-only detail dialog
    assert "Edit" not in html and "Delete" not in html
    assert "/prod_defects/" not in html.split("<script")[0]  # no edit/delete links in the markup
    assert "kpd-comment-btn" in html            # comment button (list + detail)
    assert "btn-download-comments" in html      # JSON export button
    assert "<script" in html                    # unlike /download, this keeps its JS
    assert 'id="type-filter"' in html           # client-side Type filter
    assert 'data-type="Defect"' in html


def test_email_page_pretick_and_gather_attachments():
    assert ("known_prod_defects", "Known Production Issues") in emailer.REPORT_CHOICES


def test_email_pretick_query_param(client):
    html = client.get("/email-report/?reports=known_prod_defects").get_data(as_text=True)
    assert 'value="known_prod_defects" checked' in html
    assert 'value="retail" checked' not in html
    # no query param at all -> default behaviour unchanged (everything ticked)
    html = client.get("/email-report/").get_data(as_text=True)
    assert 'value="retail" checked' in html


def test_gather_attachments_includes_known_prod_defects(client):
    _new(client, short_description="AttachMe", scenario="GWC")
    conn = database.get_connection(client.db_path)
    try:
        atts = emailer.gather_attachments(conn, {}, app, ["known_prod_defects"], "2026-08-06")
    finally:
        conn.close()
    assert [name for name, _ in atts] == ["known_prod_defects_2026-08-06.html"]
    assert "AttachMe" in atts[0][1]


# ---------------------------------------------------------------------------
# Mark Fixed / Archive [USER 2026-08-27]

def test_mark_fixed_removes_from_active_list_and_downloads_and_email(client):
    record_id = _new(client, short_description="FixMe", scenario="GWC")
    assert "FixMe" in client.get("/prod_defects").get_data(as_text=True)

    resp = client.post(f"/prod_defects/{record_id}/fixed", data={"value": "1"})
    assert resp.get_json()["ok"]

    assert "FixMe" not in client.get("/prod_defects").get_data(as_text=True)
    assert "FixMe" not in client.get("/prod_defects/download").get_data(as_text=True)
    assert "FixMe" not in client.get("/prod_defects/download-review").get_data(as_text=True)

    conn = database.get_connection(client.db_path)
    try:
        atts = emailer.gather_attachments(conn, {}, app, ["known_prod_defects"], "2026-08-06")
    finally:
        conn.close()
    assert "FixMe" not in atts[0][1]


def test_mark_fixed_never_deletes_the_record(client):
    record_id = _new(client, short_description="StillHere", scenario="GWC")
    client.post(f"/prod_defects/{record_id}/fixed", data={"value": "1"})
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    assert row is not None
    assert row["status"] == "fixed"
    assert row["fixed_at"] is not None


def test_archive_view_lists_only_fixed_items_with_reopen(client):
    fixed_id = _new(client, short_description="ArchivedRow", scenario="GWC")
    active_id = _new(client, short_description="StillActive", scenario="GWC")
    client.post(f"/prod_defects/{fixed_id}/fixed", data={"value": "1"})

    html = client.get("/prod_defects/archive").get_data(as_text=True)
    body = html.split("<script>")[0]  # scripts always reference both button
                                       # classes for their event listeners
    assert "ArchivedRow" in html and "StillActive" not in html
    assert "kpd-reopen-btn" in body and "kpd-fix-btn" not in body

    resp = client.post(f"/prod_defects/{fixed_id}/fixed", data={"value": "0"})
    assert resp.get_json()["ok"]
    html = client.get("/prod_defects/archive").get_data(as_text=True)
    assert "ArchivedRow" not in html
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "ArchivedRow" in html
    conn = database.get_connection(client.db_path)
    try:
        row = database.get_known_prod_defect(conn, fixed_id)
    finally:
        conn.close()
    assert row["status"] == "open" and row["fixed_at"] is None


def test_ecom_spillover_report_excludes_fixed_prod_defects(client):
    fixed_id = _new(client, short_description="HiddenFromReport", scenario="GWC")
    _new(client, short_description="ShownInReport", scenario="SFDC")
    client.post(f"/prod_defects/{fixed_id}/fixed", data={"value": "1"})

    html = client.get("/report/ecom").get_data(as_text=True)
    assert "HiddenFromReport" not in html
    assert "ShownInReport" in html


# ---------------------------------------------------------------------------
# Risks + Limitations split into their own tables [USER 2026-08-27]

def _split_sections(html):
    """(main_html, limitation_html, risk_html) — the page in table order."""
    main_html, rest = html.split("🔧 Limitations")
    limitation_html, risk_html = rest.split("⚠ Risks")
    return main_html, limitation_html, risk_html


def test_risks_and_limitations_split_into_their_own_tables(client):
    _new(client, short_description="ADefect", scenario="GWC", type="Defect")
    _new(client, short_description="ALimitation", scenario="GWC", type="Limitation")
    _new(client, short_description="ARisk", scenario="GWC", type="Risk")

    html = client.get("/prod_defects").get_data(as_text=True)
    main_html, limitation_html, risk_html = _split_sections(html)
    assert "ADefect" in main_html
    assert "ALimitation" not in main_html and "ARisk" not in main_html
    assert "ALimitation" in limitation_html
    assert "ADefect" not in limitation_html and "ARisk" not in limitation_html
    assert "ARisk" in risk_html
    assert "ADefect" not in risk_html and "ALimitation" not in risk_html


def test_risk_table_omits_biz_impact_how_to_detect_handle_confluence(client):
    _new(client, short_description="RiskRow", scenario="GWC", type="Risk",
        biz_impact="Big impact text", how_to_detect="Detect it this way",
        how_to_handle="Handle it this way", confluence="https://confluence.example/risk")
    html = client.get("/prod_defects").get_data(as_text=True)
    _, _, risk_html = _split_sections(html)
    assert "RiskRow" in risk_html
    assert "Big impact text" not in risk_html
    assert "Detect it this way" not in risk_html
    assert "Handle it this way" not in risk_html
    assert "https://confluence.example/risk" not in risk_html
    # channel/type/scenario/short description still there
    assert "GWC" in risk_html


def test_limitation_table_omits_biz_impact_sub_case_confluence(client):
    _new(client, short_description="LimitationRow", scenario="GWC", type="Limitation",
        biz_impact="Big impact text", sub_case="a specific sub-case",
        confluence="https://confluence.example/limitation")
    html = client.get("/prod_defects").get_data(as_text=True)
    _, limitation_html, _ = _split_sections(html)
    assert "LimitationRow" in limitation_html
    assert "Big impact text" not in limitation_html
    assert "a specific sub-case" not in limitation_html
    assert "https://confluence.example/limitation" not in limitation_html
    assert "GWC" in limitation_html


def test_empty_risk_and_limitation_tables_show_their_own_empty_state(client):
    _new(client, short_description="NoRisksHere", scenario="GWC", type="Defect")
    html = client.get("/prod_defects").get_data(as_text=True)
    _, limitation_html, risk_html = _split_sections(html)
    assert "No limitations currently listed." in limitation_html
    assert "No risks currently listed." in risk_html


def test_mark_fixed_moves_a_risk_row_to_the_archives_risk_table(client):
    risk_id = _new(client, short_description="ArchivedRisk", scenario="GWC", type="Risk")
    client.post(f"/prod_defects/{risk_id}/fixed", data={"value": "1"})

    html = client.get("/prod_defects").get_data(as_text=True)
    assert "ArchivedRisk" not in html

    html = client.get("/prod_defects/archive").get_data(as_text=True)
    main_html, limitation_html, risk_html = _split_sections(html)
    assert "ArchivedRisk" not in main_html and "ArchivedRisk" not in limitation_html
    assert "ArchivedRisk" in risk_html


def test_mark_fixed_moves_a_limitation_row_to_the_archives_limitation_table(client):
    limitation_id = _new(client, short_description="ArchivedLimitation", scenario="GWC",
                         type="Limitation")
    client.post(f"/prod_defects/{limitation_id}/fixed", data={"value": "1"})

    html = client.get("/prod_defects").get_data(as_text=True)
    assert "ArchivedLimitation" not in html

    html = client.get("/prod_defects/archive").get_data(as_text=True)
    main_html, limitation_html, risk_html = _split_sections(html)
    assert "ArchivedLimitation" not in main_html and "ArchivedLimitation" not in risk_html
    assert "ArchivedLimitation" in limitation_html


def test_archive_fixed_count_badge_includes_all_three_tables(client):
    defect_id = _new(client, short_description="D", scenario="GWC", type="Defect")
    limitation_id = _new(client, short_description="L", scenario="GWC", type="Limitation")
    risk_id = _new(client, short_description="R", scenario="GWC", type="Risk")
    for rid in (defect_id, limitation_id, risk_id):
        client.post(f"/prod_defects/{rid}/fixed", data={"value": "1"})
    html = client.get("/prod_defects").get_data(as_text=True)
    assert "🗄 Archive (3)" in html


def test_detail_page_shows_fixed_badge_and_toggle_button(client):
    record_id = _new(client, short_description="ToggleMe", scenario="GWC")
    html = client.get(f"/prod_defects/{record_id}").get_data(as_text=True)
    assert "FIXED" not in html
    assert "✓ Mark Fixed" in html and "↺ Reopen" not in html

    client.post(f"/prod_defects/{record_id}/fixed", data={"value": "1"})
    html = client.get(f"/prod_defects/{record_id}").get_data(as_text=True)
    assert "FIXED" in html
    assert "↺ Reopen" in html and "✓ Mark Fixed" not in html
