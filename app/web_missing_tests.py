"""Missing Test Cases — routes (Flask Blueprint, 2026-08-30).

The single source for "this test case does not exist yet". The Retail status
report and the Retail Requirements board both render THIS list; the page also
mirrors the Retail retrofits (read-only, with our own coverage note) because a
retrofit is the usual reason a test case is still missing.

Deliverables besides the page: a downloadable HTML report (also selectable in
the email mini app) and a copy & paste email text. No SQL here — storage in
app/db/missing_tests.py.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import missing_tests as db_missing

bp = Blueprint("missing_tests", __name__, url_prefix="/missing-tests")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def report_context(conn) -> dict:
    """Everything the page, the report and the email text share."""
    items = db_missing.list_missing_tests(conn)
    retrofits = db_missing.list_retrofits_with_notes(conn)
    return {
        "items": items,
        "retrofits": retrofits,
        "today": date.today().isoformat(),
        "email_text": db_missing.email_text(items, retrofits),
    }


@bp.route("/")
def missing_tests_page():
    conn = _get_conn()
    try:
        ctx = report_context(conn)
    finally:
        conn.close()
    return render_template("missing_tests.html", **ctx,
                           msg=request.args.get("msg"))


@bp.route("/add", methods=["POST"])
def missing_test_add():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("missing_tests.missing_tests_page"))
    conn = _get_conn()
    try:
        db_missing.create_missing_test(conn, title, request.form.get("details"))
    finally:
        conn.close()
    return redirect(url_for("missing_tests.missing_tests_page", msg="Added."))


@bp.route("/<int:item_id>/update", methods=["POST"])
def missing_test_update(item_id: int):
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("missing_tests.missing_tests_page"))
    conn = _get_conn()
    try:
        db_missing.update_missing_test(conn, item_id, title,
                                       request.form.get("details"))
    finally:
        conn.close()
    return redirect(url_for("missing_tests.missing_tests_page", msg="Saved."))


@bp.route("/<int:item_id>/delete", methods=["POST"])
def missing_test_delete(item_id: int):
    conn = _get_conn()
    try:
        db_missing.delete_missing_test(conn, item_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/retrofit/<int:retrofit_id>/note", methods=["POST"])
def retrofit_note_save(retrofit_id: int):
    """Blur-save of the coverage note next to a mirrored retrofit."""
    conn = _get_conn()
    try:
        db_missing.set_retrofit_note(conn, retrofit_id, request.form.get("note"))
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/report")
def missing_tests_report():
    conn = _get_conn()
    try:
        ctx = report_context(conn)
    finally:
        conn.close()
    return render_template("missing_tests_report.html", **ctx)


@bp.route("/report/download")
def missing_tests_report_download():
    """Dated standalone snapshot — the template carries its own inline CSS;
    download=True drops the toolbar so the file opens clean anywhere."""
    conn = _get_conn()
    try:
        ctx = report_context(conn)
    finally:
        conn.close()
    html = render_template("missing_tests_report.html", **ctx, download=True)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="missing_test_cases_{ctx["today"]}.html"',
    }
