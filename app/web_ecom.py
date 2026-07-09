"""ECOM vertical — routes (Flask Blueprint, day plan 05.07 step 8).

Own Blueprint by design (CLAUDE.md new-module pattern). No SQL here —
storage in app/db/ecom.py; Jira context is read-only from the shared jira
store (app/db/jira.py), joined by jira id. Excel fields and Jira fields
stay strictly separate on the pages too.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import ecom as db_ecom
from app.db import jira as db_jira
from app.jira_importer import run_jira_import

bp = Blueprint("ecom", __name__, url_prefix="/ecom")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def ecom_list():
    statuses  = request.args.getlist("status")
    countries = request.args.getlist("country")
    scenarios = request.args.getlist("scenario")
    q         = request.args.get("q", "").strip() or None

    conn = _get_conn()
    try:
        rows = db_ecom.get_ecom_rows(conn, statuses=statuses or None,
                                     countries=countries or None,
                                     scenarios=scenarios or None, q=q)
        distincts = db_ecom.get_ecom_distincts(conn)
        jira_keys = {i["jira_key"] for i in db_jira.list_jira_issues(conn)}
    finally:
        conn.close()
    return render_template(
        "ecom.html", rows=rows, distincts=distincts, jira_keys=jira_keys,
        sel_statuses=statuses, sel_countries=countries, sel_scenarios=scenarios,
        q=q or "",
        jira_ok=request.args.get("jira_ok"),
        jira_msg=request.args.get("jira_msg"),
    )


@bp.route("/import-jira", methods=["POST"])
def ecom_import_jira():
    """'Update from Jira' — runs the ECOM-folder XML import (step 2 code)."""
    result = run_jira_import(_cfg, "ecom")
    if result["ok"]:
        msg = (f"{Path(result['xml_path']).name}: {result['parsed']} issues — "
               f"{result['inserted']} new · {result['updated']} refreshed · "
               f"{result['comments']} comments")
        return redirect(url_for("ecom.ecom_list", jira_ok="1", jira_msg=msg))
    return redirect(url_for("ecom.ecom_list", jira_ok="0", jira_msg=result["error"]))


@bp.route("/<int:ecom_id>", methods=["GET", "POST"])
def ecom_detail(ecom_id: int):
    conn = _get_conn()
    try:
        row = db_ecom.get_ecom_by_id(conn, ecom_id)
        if row is None:
            conn.close()
            return render_template("404.html", defect_id=f"ECOM #{ecom_id}"), 404
        if request.method == "POST":
            db_ecom.upsert_ecom_annotation(
                conn, row["jira_id"],
                next_step=request.form.get("next_step", "").strip() or None,
                comment_history=request.form.get("comment_history", "").strip() or None,
                action_needed=request.form.get("action_needed") == "1")
            conn.close()
            return redirect(url_for("ecom.ecom_detail", ecom_id=ecom_id, saved="1"))
        jira = db_jira.get_jira_issue(conn, row["jira_id"])
        jira_comments = (db_jira.list_jira_comments(conn, row["jira_id"])
                         if jira else [])
        notes = database.list_notes(conn, "ecom", ecom_id)
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "ecom_detail.html",
        row=row, jira=jira, jira_comments=jira_comments,
        notes=notes, attachments_by_note=attachments_by_note,
        saved=request.args.get("saved") == "1",
        note_added=request.args.get("note_added") == "1",
        note_saved=request.args.get("note_saved") == "1",
        note_deleted=request.args.get("note_deleted") == "1",
        orders_moved=request.args.get("orders_moved"),
    )


@bp.route("/<int:ecom_id>/pull-orders", methods=["POST"])
def ecom_pull_orders(ecom_id: int):
    """Gatekeeper → ECOM handover: re-point order rows with the same jira id."""
    conn = _get_conn()
    try:
        row = db_ecom.get_ecom_by_id(conn, ecom_id)
        moved = (db_ecom.relink_gatekeeper_orders(conn, row["jira_id"], ecom_id)
                 if row else 0)
    finally:
        conn.close()
    return redirect(url_for("ecom.ecom_detail", ecom_id=ecom_id, orders_moved=moved))
