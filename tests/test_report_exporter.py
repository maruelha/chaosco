"""Export Reports (dashboard card): export_all_reports writes all six
snapshot files — Retail/Spillover HTML+PPTX and the Delegated report +
numbers HTML (download-mode renders, no buttons/scripts)."""
import pytest

from app import database
from app.db import delegated as db_delegated
from app.db import jira as db_jira
import app.web_delegated as web_delegated
from app.report_exporter import export_all_reports
from app.web import app


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "export.db"
    database.init_db(db_path).close()
    db_jira.init_schema(db_path)
    db_delegated.init_schema(db_path)
    monkeypatch.setattr(web_delegated, "_get_conn",
                        lambda: database.get_connection(db_path))
    cfg = {"database_path": str(db_path),
           "report_export_folder": str(tmp_path / "report_export"),
           "jira_gatekeeper_assignee": "Haase"}
    monkeypatch.setitem(web_delegated._cfg, "jira_gatekeeper_assignee", "Haase")
    return db_path, cfg


def test_export_writes_all_six_files(env):
    db_path, cfg = env
    conn = database.get_connection(db_path)
    try:
        with app.test_request_context():
            saved = export_all_reports(conn, cfg)
    finally:
        conn.close()
    names = sorted(p.name for p in saved)
    assert len(saved) == 6
    stems = [n.rsplit("_", 1)[0] for n in names]  # drop the date part
    assert "delegated_report" in stems
    assert "delegated_numbers" in stems
    assert sum(n.endswith(".html") for n in names) == 4
    assert sum(n.endswith(".pptx") for n in names) == 2
    for p in saved:
        assert p.exists() and p.stat().st_size > 0
    # the delegated snapshots are the clean download renders — no buttons
    delegated = [p for p in saved if p.name.startswith("delegated")]
    for p in delegated:
        html = p.read_text(encoding="utf-8")
        assert 'class="toolbar"' not in html
        assert "<script>" not in html
