"""Manual Test Cases — routes (Flask Blueprint, 2026-08-05).

One Blueprint for BOTH verticals, parameterised by stream (retail | ecom):
/manual/<stream> list + /manual/<stream>/report — the report is the simple
Retail pattern, assembled from the shared _report_blocks.html macros.
No SQL here — storage in app/db/manual_tests.py.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import manual_tests as db_manual
from app.report_log import append_report_row
from app.reporter import (compute_impacted_totals, compute_retail_report,
                          load_status_mappings, passed_family)

bp = Blueprint("manual_tests", __name__, url_prefix="/manual")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])

STREAMS: dict[str, dict] = {
    "retail": {"vertical": "manual_retail", "label": "Manual Test Cases Retail",
               "sheet": "Manual Retail"},
    "ecom":   {"vertical": "manual_ecom", "label": "Manual Test Cases ECOM",
               "sheet": "Manual ECOM"},
}


def _get_conn():
    return database.get_connection(_db_path)


def _stream(stream: str) -> dict | None:
    return STREAMS.get(stream)


@bp.route("/<stream>")
def manual_list(stream: str):
    spec = _stream(stream)
    if spec is None:
        return render_template("404.html", defect_id=stream), 404
    vertical = spec["vertical"]

    sel_status   = request.args.get("status", "")
    sel_country  = request.args.get("country", "")
    sel_scenario = request.args.get("scenario", "")
    search       = request.args.get("search", "").strip()

    conn = _get_conn()
    try:
        rows = db_manual.get_manual_rows(
            conn, vertical,
            statuses=[sel_status] if sel_status else None,
            countries=[sel_country] if sel_country else None,
            scenarios=[sel_scenario] if sel_scenario else None,
            search=search or None,
        )
        options = db_manual.get_manual_filter_options(conn, vertical)
    finally:
        conn.close()

    return render_template(
        "manual_list.html",
        stream=stream, label=spec["label"], rows=rows, options=options,
        sel_status=sel_status, sel_country=sel_country,
        sel_scenario=sel_scenario, search=search,
    )


def _report_context(conn, stream: str) -> dict:
    """Shared context for the report page/download: buckets (same
    definitions as Retail — one config) + defects referenced in the tab
    AND matching the vertical's channel; off-channel references surface
    in the diagnostics instead of vanishing [USER 2026-08-05]."""
    spec = STREAMS[stream]
    vertical = spec["vertical"]
    mappings = load_status_mappings()
    report = compute_retail_report(
        db_manual.get_manual_status_counts(conn, vertical), mappings)
    defects = db_manual.get_manual_defects_impacted(
        conn, vertical, passed_family(mappings))
    totals = compute_impacted_totals(defects)
    return {
        "stream": stream,
        "label": spec["label"],
        "channel_label": db_manual.CHANNEL[vertical].capitalize(),
        "report": report,
        "impacted_defects": defects,
        "impacted_total": totals["total"],
        "mb_total": totals["mb"],
        "sales_total": totals["sales"],
        "offchannel_refs": db_manual.get_manual_offchannel_defect_refs(
            conn, vertical),
        "report_comments": database.list_report_comments(conn, vertical),
        "today": date.today().isoformat(),
    }


@bp.route("/<stream>/report")
def manual_report(stream: str):
    if _stream(stream) is None:
        return render_template("404.html", defect_id=stream), 404
    conn = _get_conn()
    try:
        ctx = _report_context(conn, stream)
    finally:
        conn.close()
    return render_template("manual_report.html", **ctx)


@bp.route("/<stream>/report/download")
def manual_report_download(stream: str):
    """Dated standalone snapshot — the page itself made self-contained
    (CSS inlined, buttons/scripts stripped), same as the email attachment."""
    if _stream(stream) is None:
        return render_template("404.html", defect_id=stream), 404
    from app.emailer import standalone_html
    from app.web_core import app as flask_app
    resp = flask_app.test_client().get(
        url_for("manual_tests.manual_report", stream=stream))
    today = date.today().isoformat()
    return standalone_html(resp.get_data(as_text=True)), 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="manual_{stream}_report_{today}.html"',
    }


@bp.route("/<stream>/report/save-excel", methods=["POST"])
def manual_report_save_excel(stream: str):
    """Append one dated row to the vertical's sheet of the report log
    workbook (same file as the Retail/ECOM logs, own sheet)."""
    spec = _stream(stream)
    if spec is None:
        return jsonify({"ok": False, "error": f"unknown stream: {stream}"}), 404
    try:
        conn = _get_conn()
        try:
            report = compute_retail_report(
                db_manual.get_manual_status_counts(conn, spec["vertical"]),
                load_status_mappings())
        finally:
            conn.close()
        save_date = request.form.get("date") or date.today().isoformat()
        path = append_report_row(_cfg, report, save_date, spec["sheet"])
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})
    return jsonify({"ok": True, "path": path, "date": save_date})
