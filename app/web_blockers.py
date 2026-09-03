"""Blockers — routes (Flask Blueprint, 2026-08-27).

Defects/tasks/business clarifications that block Delegated Testing tickets.
Own list (grouped by type) + add/edit detail page + notes thread. A blocker
with a jira_key shows its LIVE status/comments when that key is already in
the shared jira store (refreshed by the existing delegated upload — no
separate import here). No SQL here.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import blockers as db_blockers
from app.db import jira as db_jira

bp = Blueprint("blockers", __name__, url_prefix="/blockers")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def _jira_status_map(conn, rows):
    """{blocker_id: jira_status} plus {blocker_id: last_seen} for the same
    keys. last_seen = when an upload last carried the key — shown as an
    "as of" stamp on the list [USER 2026-09-01: "the Status value in Jira
    is never updating"] so a stale status is diagnosable: an old date
    means the uploads don't contain this ticket; a current date with an
    old status would mean the parse is wrong for that file."""
    status, seen = {}, {}
    for r in rows:
        if r["jira_key"]:
            issue = db_jira.get_jira_issue(conn, r["jira_key"])
            status[r["blocker_id"]] = issue["jira_status"] if issue else None
            seen[r["blocker_id"]] = issue["last_seen"] if issue else None
    return status, seen


@bp.route("/")
def blockers_list():
    conn = _get_conn()
    try:
        rows = db_blockers.list_blockers(conn)
        blocked_counts = db_blockers.blocked_ticket_counts(conn)
        jira_status, jira_seen = _jira_status_map(conn, rows)
        team_options = db_blockers.team_options(conn)
    finally:
        conn.close()
    # Open/closed split [USER 2026-08-27: "focus on the open issues"] —
    # closed = manually closed OR jira in the done family; the type
    # sections carry only open blockers, closed ones collapse below.
    open_rows = [r for r in rows
                 if not db_blockers.is_closed(r, jira_status.get(r["blocker_id"]))]
    closed_rows = [r for r in rows
                   if db_blockers.is_closed(r, jira_status.get(r["blocker_id"]))]
    sections = [(key, label, [r for r in open_rows if r["type"] == key])
                for key, label in db_blockers.TYPE_SECTIONS]
    return render_template(
        "blockers.html", sections=sections, total=len(open_rows),
        closed_rows=closed_rows,
        jira_status=jira_status, jira_seen=jira_seen,
        blocked_counts=blocked_counts,
        type_sections=db_blockers.TYPE_SECTIONS,
        team_options=team_options,
    )


def _form_fields():
    type_ = request.form.get("type", "").strip()
    name = request.form.get("name", "").strip()
    jira_key = request.form.get("jira_key", "").strip() or None
    return type_, name, jira_key


def _extra_form_fields():
    # team [USER 2026-08-28]: fixed picks + "Other" free text — the form
    # sends team='__other__' plus team_other when Other is chosen
    team = request.form.get("team", "").strip()
    if team == "__other__":
        team = request.form.get("team_other", "").strip()
    return {
        "comment": request.form.get("comment", "").strip() or None,
        "impact": request.form.get("impact", "").strip() or None,
        "solman_id": request.form.get("solman_id", "").strip() or None,
        "team": team or None,
    }


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
                row = db_blockers.create_blocker(conn, type_, name, jira_key,
                                                 **_extra_form_fields())
            finally:
                conn.close()
            return redirect(url_for("blockers.blocker_detail",
                                    blocker_id=row["blocker_id"], saved="1"))
    else:
        type_, name, jira_key = "", "", ""
    conn = _get_conn()
    try:
        team_options = db_blockers.team_options(conn)
    finally:
        conn.close()
    return render_template(
        "blocker_detail.html", record={"type": type_, "name": name,
                                        "jira_key": jira_key},
        is_new=True, saved=False, types=db_blockers.TYPE_SECTIONS, error=error,
        team_options=team_options,
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
                db_blockers.update_blocker(conn, blocker_id, type_, name, jira_key,
                                           **_extra_form_fields())
                conn.close()
                return redirect(url_for("blockers.blocker_detail",
                                        blocker_id=blocker_id, saved="1"))
            record = {**record, "type": type_, "name": name, "jira_key": jira_key,
                      **_extra_form_fields()}
        jira_issue = jira_comments = None
        if record.get("jira_key"):
            jira_issue = db_jira.get_jira_issue(conn, record["jira_key"])
            if jira_issue:
                jira_comments = db_jira.list_jira_comments(conn, record["jira_key"])
        notes = database.list_notes(conn, "blocker", str(blocker_id))
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
        team_options = db_blockers.team_options(conn)
    finally:
        conn.close()
    closed = db_blockers.is_closed(
        record, jira_issue["jira_status"] if jira_issue else None)
    return render_template(
        "blocker_detail.html", record=record, is_new=False, error=error,
        saved=request.args.get("saved") == "1",
        types=db_blockers.TYPE_SECTIONS, closed=closed,
        jira_issue=jira_issue, jira_comments=jira_comments,
        notes=notes, attachments_by_note=attachments_by_note,
        team_options=team_options,
    )


@bp.route("/<int:blocker_id>/close", methods=["POST"])
def blocker_toggle_closed(blocker_id: int):
    """Manual close/reopen [USER 2026-08-27] — jira-backed blockers also
    auto-close when their ticket reaches Resolved/Closed/Done."""
    value = request.form.get("value") == "1"
    conn = _get_conn()
    try:
        db_blockers.set_blocker_closed(conn, blocker_id, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:blocker_id>/team", methods=["POST"])
def blocker_team(blocker_id: int):
    """Inline team pick on the Blockers list [USER 2026-08-28] — the
    client resolves 'Other…' to the typed value before posting."""
    conn = _get_conn()
    try:
        db_blockers.set_blocker_team(
            conn, blocker_id, request.form.get("team", ""))
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:blocker_id>/impact", methods=["POST"])
def blocker_impact(blocker_id: int):
    """Inline blur-save of the Impact field — editable on the Management
    Summary's blocker overview [USER 2026-08-28], same field as the
    detail form's Impact textarea."""
    conn = _get_conn()
    try:
        db_blockers.set_blocker_impact(
            conn, blocker_id, request.form.get("impact", ""))
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:blocker_id>/next-step", methods=["POST"])
def blocker_next_step(blocker_id: int):
    """Inline blur-save of the authored next step (archive entity 'blocker')."""
    conn = _get_conn()
    try:
        db_blockers.set_blocker_next_step(
            conn, blocker_id, request.form.get("next_step", "").strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Attach-to-ticket picker (build plan step 8) — AJAX-driven, same pattern as
# _order_details.html: no per-page context needed, only an opening button
# with data-jira-key + data-name. Drop-in include: _blocker_picker.html.

def _slim(rows: list[dict]) -> list[dict]:
    # label = jira key / BC id / name — the row chips show ONLY this
    # [USER 2026-08-27: "I only want to see the id (else everything
    # explodes)"]; the full name stays for the dialog's pick list + titles.
    return [{"blocker_id": r["blocker_id"], "type": r["type"],
             "name": r["name"], "jira_key": r["jira_key"],
             "label": db_blockers.chip_label(r),
             # linked rows only (2026-09-03): the import's "not in Jira" stamp
             "jira_missing_since": r.get("link_jira_missing_since")} for r in rows]


def _picker_payload(conn, jira_key: str) -> dict:
    """Closed blockers (manually closed or Jira done) are left OUT of the
    pick list [USER 2026-09-01: "once closed they do not need to be in the
    list"]; already-attached ones stay in `linked` even when closed, so
    the chip remains visible and detachable."""
    linked = db_blockers.list_blockers_for_ticket(conn, jira_key)
    linked_ids = {b["blocker_id"] for b in linked}
    rows = db_blockers.list_blockers(conn)
    jira_status, _seen = _jira_status_map(conn, rows)
    available = [b for b in rows
                 if b["blocker_id"] not in linked_ids
                 and not db_blockers.is_closed(b, jira_status.get(b["blocker_id"]))]
    return {"linked": _slim(linked), "available": _slim(available)}


@bp.route("/links/<jira_key>")
def blocker_links_json(jira_key: str):
    conn = _get_conn()
    try:
        payload = _picker_payload(conn, jira_key)
    finally:
        conn.close()
    return jsonify(payload)


@bp.route("/links/<jira_key>/attach", methods=["POST"])
def blocker_link_attach(jira_key: str):
    blocker_id = request.form.get("blocker_id", type=int)
    if not blocker_id:
        return jsonify({"ok": False, "error": "no blocker selected"}), 400
    conn = _get_conn()
    try:
        db_blockers.link_blocker(conn, blocker_id, jira_key)
        payload = _picker_payload(conn, jira_key)
    finally:
        conn.close()
    return jsonify({"ok": True, **payload})


@bp.route("/links/<jira_key>/detach", methods=["POST"])
def blocker_link_detach(jira_key: str):
    blocker_id = request.form.get("blocker_id", type=int)
    conn = _get_conn()
    try:
        db_blockers.unlink_blocker(conn, blocker_id, jira_key)
        payload = _picker_payload(conn, jira_key)
    finally:
        conn.close()
    return jsonify({"ok": True, **payload})


@bp.route("/links/<jira_key>/quick-create", methods=["POST"])
def blocker_link_quick_create(jira_key: str):
    """Create a new blocker and attach it to this ticket in one step —
    the "add name, jira key and type while attaching" flow [USER 2026-08-27]."""
    type_, name, blocker_jira_key = _form_fields()
    if type_ not in db_blockers.TYPES or not name:
        return jsonify({"ok": False, "error": "Pick a type and enter a name."}), 400
    conn = _get_conn()
    try:
        row = db_blockers.create_blocker(conn, type_, name, blocker_jira_key)
        db_blockers.link_blocker(conn, row["blocker_id"], jira_key)
        payload = _picker_payload(conn, jira_key)
    finally:
        conn.close()
    return jsonify({"ok": True, **payload})
