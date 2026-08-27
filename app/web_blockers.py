"""Blockers — routes (Flask Blueprint, 2026-08-27).

Defects/tasks/business clarifications that block Delegated Testing tickets.
Own list (grouped by type) + add/edit detail page + notes thread. A blocker
with a jira_key shows its LIVE status/comments when that key is already in
the shared jira store (refreshed by the existing delegated upload — no
separate import here). No SQL here.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import blockers as db_blockers
from app.db import jira as db_jira

bp = Blueprint("blockers", __name__, url_prefix="/blockers")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def blockers_list():
    conn = _get_conn()
    try:
        rows = db_blockers.list_blockers(conn)
        note_counts = {r["blocker_id"]: len(database.list_notes(
            conn, "blocker", str(r["blocker_id"]))) for r in rows}
        jira_status = {}
        for r in rows:
            if r["jira_key"]:
                issue = db_jira.get_jira_issue(conn, r["jira_key"])
                jira_status[r["blocker_id"]] = issue["jira_status"] if issue else None
    finally:
        conn.close()
    sections = [(key, label, [r for r in rows if r["type"] == key])
                for key, label in db_blockers.TYPE_SECTIONS]
    return render_template(
        "blockers.html", sections=sections, total=len(rows),
        note_counts=note_counts, jira_status=jira_status,
        type_sections=db_blockers.TYPE_SECTIONS,
    )


def _form_fields():
    type_ = request.form.get("type", "").strip()
    name = request.form.get("name", "").strip()
    jira_key = request.form.get("jira_key", "").strip() or None
    return type_, name, jira_key


@bp.route("/new", methods=["GET", "POST"])
def blocker_new():
    error = None
    if request.method == "POST":
        type_, name, jira_key = _form_fields()
        if type_ not in db_blockers.TYPES or not name:
            error = "Pick a type and enter a name."
        else:
            conn = _get_conn()
            try:
                row = db_blockers.create_blocker(conn, type_, name, jira_key)
            finally:
                conn.close()
            return redirect(url_for("blockers.blocker_detail",
                                    blocker_id=row["blocker_id"], saved="1"))
    else:
        type_, name, jira_key = "", "", ""
    return render_template(
        "blocker_detail.html", record={"type": type_, "name": name,
                                        "jira_key": jira_key},
        is_new=True, saved=False, types=db_blockers.TYPE_SECTIONS, error=error,
    )


@bp.route("/<int:blocker_id>", methods=["GET", "POST"])
def blocker_detail(blocker_id: int):
    conn = _get_conn()
    try:
        record = db_blockers.get_blocker(conn, blocker_id)
        if record is None:
            conn.close()
            from app.web_core import _not_found
            return _not_found(str(blocker_id))
        error = None
        if request.method == "POST":
            type_, name, jira_key = _form_fields()
            if type_ not in db_blockers.TYPES or not name:
                error = "Pick a type and enter a name."
            else:
                db_blockers.update_blocker(conn, blocker_id, type_, name, jira_key)
                conn.close()
                return redirect(url_for("blockers.blocker_detail",
                                        blocker_id=blocker_id, saved="1"))
            record = {**record, "type": type_, "name": name, "jira_key": jira_key}
        jira_issue = jira_comments = None
        if record.get("jira_key"):
            jira_issue = db_jira.get_jira_issue(conn, record["jira_key"])
            if jira_issue:
                jira_comments = db_jira.list_jira_comments(conn, record["jira_key"])
        notes = database.list_notes(conn, "blocker", str(blocker_id))
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "blocker_detail.html", record=record, is_new=False, error=error,
        saved=request.args.get("saved") == "1",
        types=db_blockers.TYPE_SECTIONS,
        jira_issue=jira_issue, jira_comments=jira_comments,
        notes=notes, attachments_by_note=attachments_by_note,
    )
