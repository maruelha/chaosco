"""Report history page — Blueprint (/report-history).

One page, switcher over the four bucket reports: dates as rows (newest
first), the app's bucket columns, source tag per row (email / excel).
The import button pulls the workbook's ReportRetail / ReportECOM lines
in (upsert per date — re-runnable). No SQL here — storage in
app/db/report_history.py, parsing in app/report_history_importer.py.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import report_history as db_hist
from app.report_history_importer import import_report_tabs

bp = Blueprint("report_history", __name__, url_prefix="/report-history")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def history_page():
    report = request.args.get("report", "retail")
    if report not in db_hist.BUCKET_REPORTS:
        report = "retail"
    conn = _get_conn()
    try:
        rows = db_hist.list_history(conn, report)
    finally:
        conn.close()
    return render_template(
        "report_history.html",
        report=report,
        rows=rows,
        reports=db_hist.BUCKET_REPORTS,
        labels=db_hist.REPORT_LABELS,
        bucket_fields=db_hist.BUCKET_FIELDS,
        result=request.args.get("result"),
        error=request.args.get("error"),
    )


@bp.route("/import-tabs", methods=["POST"])
def import_tabs():
    """Pull the Report tabs' lines from the newest workbook (source
    'excel'); existing dates are updated, nothing is deleted."""
    report = request.form.get("report", "retail")
    conn = _get_conn()
    try:
        result = import_report_tabs(_cfg, conn)
    finally:
        conn.close()
    if result.get("error"):
        return redirect(url_for("report_history.history_page",
                                report=report, error=result["error"]))
    parts = []
    for key, r in result["reports"].items():
        if r["error"]:
            parts.append(f"{key}: {r['error']}")
        else:
            note = f"{key}: {r['imported']} line(s)"
            if r["skipped_no_date"]:
                note += f" ({r['skipped_no_date']} without a readable date skipped)"
            if r["unmapped"]:
                note += f" — unknown columns ignored: {', '.join(r['unmapped'])}"
            parts.append(note)
    return redirect(url_for("report_history.history_page", report=report,
                            result="Imported from the workbook — " + " · ".join(parts)))
