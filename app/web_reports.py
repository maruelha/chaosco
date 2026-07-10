"""Sign-off reports — retail/ecom spillover reports, report comments

Routes module (refactoring step 4) — registers on the shared app from
app.web_core; endpoint names and URLs are unchanged from the old monolith.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
from flask import jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app import database
from app.web_core import (app, _cfg, _get_conn, _not_found,
                          _UPLOAD_FOLDER, _IMAGE_EXTS, _ALLOWED_EXTS)

@app.route("/report-comments/<report>/add", methods=["POST"])
def report_comment_add(report: str):
    if report not in ("spillover", "retail", "ecom"):
        return jsonify({"ok": False}), 400
    comment = request.form.get("comment", "").strip()
    conn = _get_conn()
    try:
        new_id = database.add_report_comment(conn, report, comment)
    finally:
        conn.close()
    return jsonify({"ok": True, "row": {"id": new_id, "comment": comment}})


@app.route("/report-comments/<int:comment_id>/update", methods=["POST"])
def report_comment_update(comment_id: int):
    comment = request.form.get("comment", "").strip()
    conn = _get_conn()
    try:
        database.update_report_comment(conn, comment_id, comment)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/report-comments/<int:comment_id>/delete", methods=["POST"])
def report_comment_delete(comment_id: int):
    conn = _get_conn()
    try:
        database.delete_report_comment(conn, comment_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Retail routes


def _prepare_report(rows: list) -> list[tuple[str, list]]:
    """Group rows by critical_for_signoff, sort each group by (signoff_group, name)."""
    order = [
        ("yes",      "Critical for sign-off: Yes"),
        ("slightly", "Critical for sign-off: Slightly"),
        ("no",       "Critical for sign-off: No"),
        ("",         "Critical for sign-off: Not set"),
    ]
    groups: dict[str, list] = {k: [] for k, _ in order}
    for r in rows:
        key = (r.get("critical_for_signoff") or "").lower()
        groups[key if key in groups else ""].append(r)
    for grp in groups.values():
        grp.sort(key=lambda r: (
            (r.get("signoff_group") or "").lower() or "\xff",
            (r.get("name") or "").lower(),
        ))
    return [(label, groups[key]) for key, label in order if groups[key]]


@app.route("/report/retail")
def retail_report():
    hidden = _cfg.get("spillover_hidden_statuses", [])
    exclude_areas = {"ecom", "omni"}
    conn = _get_conn()
    try:
        rows = database.get_spillover(conn, exclude_statuses=hidden or None)
    finally:
        conn.close()
    rows = [r for r in rows if (r.get("area") or "").lower() not in exclude_areas]
    return render_template("report.html",
        title="Retail Spillover Report",
        report_date=date.today().isoformat(),
        sections=_prepare_report(rows),
        total=len(rows),
        prod_defects=[])


@app.route("/report/ecom")
def ecom_report():
    hidden = _cfg.get("spillover_hidden_statuses", [])
    ecom_areas = {"ecom", "omni"}
    conn = _get_conn()
    try:
        rows = database.get_spillover(conn, exclude_statuses=hidden or None)
        prod_defects = database.list_known_prod_defects(conn)
    finally:
        conn.close()
    rows = [r for r in rows if (r.get("area") or "").lower() in ecom_areas]
    return render_template("report.html",
        title="ECOM / Omni Spillover Report",
        report_date=date.today().isoformat(),
        sections=_prepare_report(rows),
        total=len(rows),
        prod_defects=prod_defects)


# ---------------------------------------------------------------------------
# Known production defects routes

