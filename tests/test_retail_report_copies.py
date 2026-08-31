"""The Retail Status Report exists in three copies — they must agree.

    GET /retail/report/download   the button on the page
    emailer.render_retail_html    the email attachment
    report_exporter               the dated snapshot in report_export/

They drifted twice: the emailed copy lost the impacted defects (fixed
2026-08-10), and on 2026-08-30 the emailed AND exported copies silently lost
the whole "Missing test cases" block when that list moved out of settings.yaml
into its own module — the page kept it, so nothing looked broken.

Since 2026-08-31 all three go through `emailer.render_retail_html`. These
tests pin that: whatever a reader sees on screen is what lands in the mail and
in the export.
"""
import pathlib

import pytest

from app import database, emailer, report_exporter
from app.db import delegated as db_delegated
from app.db import jira as db_jira
from app.db import missing_tests as db_missing
from app.db import retrofits as db_retrofits
import app.web_core as web_core
from app.web import app


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    db_path = tmp_path / "copies.db"
    database.init_db(db_path).close()
    db_missing.init_schema(db_path)
    db_retrofits.init_schema(db_path)
    # the export also writes the Delegated snapshots
    db_jira.init_schema(db_path)
    db_delegated.init_schema(db_path)
    monkeypatch.setattr(web_core, "_db_path", db_path)

    conn = database.get_connection(db_path)
    db_missing.create_missing_test(conn, "Event store", "Sales must confirm")
    db_retrofits.create_retrofit(conn, "Retail", "New return flow",
                                 status="Potential", expected="CW40")
    conn.close()

    cfg = {"database_path": str(db_path), "retail_total_test_cases": 646,
           "report_export_folder": str(tmp_path / "export")}
    return {"db_path": db_path, "cfg": cfg}


def _screen_copy():
    return app.test_client().get("/retail/report/download").get_data(as_text=True)


def test_the_emailed_copy_carries_the_missing_test_cases(ctx):
    conn = database.get_connection(ctx["db_path"])
    try:
        with app.test_request_context("/"):
            mailed = emailer.render_retail_html(conn, ctx["cfg"], "2026-08-31")
    finally:
        conn.close()
    assert "Missing test cases (on top" in mailed
    assert "Event store" in mailed          # the entry itself, not just the heading
    assert "New return flow" in mailed      # and the retrofit section has content


def test_the_exported_snapshot_is_the_same_render(ctx):
    conn = database.get_connection(ctx["db_path"])
    try:
        with app.test_request_context("/"):
            saved = report_exporter.export_all_reports(conn, ctx["cfg"])
            expected = emailer.render_retail_html(conn, ctx["cfg"],
                                                  __import__("datetime").date.today().isoformat())
    finally:
        conn.close()
    html_path = next(p for p in saved
                     if p.name.startswith("retail_report") and p.suffix == ".html")
    assert html_path.read_text(encoding="utf-8") == expected


def test_screen_email_and_export_show_the_same_sections(ctx):
    screen = _screen_copy()
    conn = database.get_connection(ctx["db_path"])
    try:
        with app.test_request_context("/"):
            mailed = emailer.render_retail_html(conn, ctx["cfg"], "2026-08-31")
    finally:
        conn.close()
    for marker in ("Missing test cases (on top", "Event store",
                   "Retail Defects", "Retrofits", "New return flow"):
        assert marker in screen, f"missing from the page download: {marker}"
        assert marker in mailed, f"missing from the emailed copy: {marker}"


def test_a_db_without_retrofits_still_renders(tmp_path, monkeypatch):
    """A report must not break because another module was not initialised."""
    db_path = tmp_path / "bare.db"
    database.init_db(db_path).close()
    monkeypatch.setattr(web_core, "_db_path", db_path)
    conn = database.get_connection(db_path)
    try:
        with app.test_request_context("/"):
            html = emailer.render_retail_html(
                conn, {"database_path": str(db_path)}, "2026-08-31")
    finally:
        conn.close()
    assert "Retail Status Report" in html
