"""Delegated Testing — routes (Flask Blueprint, 2026-08-26).

The card for the testing work DELEGATED to the team: its own Jira XML
export, uploaded as a file on the card (like ECOMTestPlan — the browser
uploads the file's content, no folder config, works on both machines).
Tickets land in the SHARED jira store tagged seen_in_delegated; the card
groups them into the delegated buckets (app/delegated_buckets.py).
Authored fields (blocked reason, next step) in app/db/delegated.py.
No SQL here.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for)

from app import database
from app.config_loader import load_config
from app.db import delegated as db_delegated
from app.db import jira as db_jira
from app.delegated_buckets import BOARD_CSS, bucket_counts, bucket_issues
from app.jira_importer import extract_latest_comment_orders, run_delegated_import

bp = Blueprint("delegated", __name__, url_prefix="/delegated")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = Path(__file__).parent.parent / "data" / "uploads"


def _get_conn():
    return database.get_connection(_db_path)


def _me() -> str:
    return (_cfg.get("jira_gatekeeper_assignee") or "").strip().lower()


def _load_issues(conn):
    """Delegated issues + their comments + latest-comment orders."""
    issues = db_jira.list_jira_issues(conn, seen_in="delegated")
    comments_map = {i["jira_key"]: db_jira.list_jira_comments(conn, i["jira_key"])
                    for i in issues}
    for i in issues:
        i["orders"] = extract_latest_comment_orders(
            comments_map[i["jira_key"]])["orders"]
    return issues, comments_map


@bp.route("/")
def delegated_list():
    conn = _get_conn()
    try:
        issues, comments_map = _load_issues(conn)
        annotations = db_delegated.get_delegated_annotations(conn)
        note_counts = {i["jira_key"]: len(database.list_notes(
            conn, "delegated", i["jira_key"])) for i in issues}
        from app.db import teams_chats as db_tc
        chats_by_entity = db_tc.chats_by_entity(conn, "jira")
        # shared order-details component at ('jira', key) — same rows as the
        # gatekeeper/ECOM boards; green ✓ when any row has S4 docs
        docs_s4_jira = database.get_docs_s4_entity_ids(conn, "jira")
    finally:
        conn.close()
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["next_step"] = ann.get("next_step")
        i["blocked_reason"] = ann.get("blocked_reason")
    return render_template(
        "delegated.html",
        sections=bucket_issues(issues, _me()),
        board_css=BOARD_CSS,
        total=len(issues),
        jira_comments=comments_map,
        note_counts=note_counts,
        chats_by_entity=chats_by_entity,
        docs_s4_jira=docs_s4_jira,
        jira_ok=request.args.get("jira_ok"),
        jira_msg=request.args.get("jira_msg"),
    )


@bp.route("/upload", methods=["POST"])
def delegated_upload():
    """Upload the delegated Jira XML export — a dated copy is kept in
    data/uploads (traceability; mirrored by the backup), then imported."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return redirect(url_for("delegated.delegated_list", jira_ok="0",
                                jira_msg="No file selected."))
    if not f.filename.lower().endswith(".xml"):
        return redirect(url_for("delegated.delegated_list", jira_ok="0",
                                jira_msg="That is not an .xml file — pick the Jira XML export."))
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xml_path = _UPLOAD_FOLDER / f"delegated_jira_{stamp}.xml"
    f.save(str(xml_path))
    result = run_delegated_import(_cfg, xml_path)
    if result["ok"]:
        msg = (f"{f.filename}: {result['parsed']} tickets — "
               f"{result['inserted']} new · {result['updated']} refreshed · "
               f"{result['comments']} comments")
        return redirect(url_for("delegated.delegated_list", jira_ok="1", jira_msg=msg))
    return redirect(url_for("delegated.delegated_list", jira_ok="0",
                            jira_msg=result["error"]))


@bp.route("/ticket/<jira_key>/next-step", methods=["POST"])
def delegated_next_step(jira_key: str):
    """Inline blur-save of the authored next step on the card."""
    conn = _get_conn()
    try:
        db_delegated.set_delegated_next_step(
            conn, jira_key, request.form.get("next_step", "").strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/ticket/<jira_key>/blocked-reason", methods=["POST"])
def delegated_blocked_reason(jira_key: str):
    """Inline blur-save of the 'why blocked' field (BLOCKED rows)."""
    conn = _get_conn()
    try:
        db_delegated.set_delegated_blocked_reason(
            conn, jira_key, request.form.get("blocked_reason", "").strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/ticket/<jira_key>", methods=["GET", "POST"])
def delegated_ticket_detail(jira_key: str):
    """Detail page per delegated ticket — read-only Jira data (details +
    comments) + authored blocked reason / next step + notes ('delegated')."""
    conn = _get_conn()
    try:
        issue = db_jira.get_jira_issue(conn, jira_key)
        if issue is None:
            conn.close()
            from app.web_core import _not_found
            return _not_found(jira_key)
        if request.method == "POST":
            db_delegated.set_delegated_next_step(
                conn, jira_key, request.form.get("next_step", "").strip() or None)
            db_delegated.set_delegated_blocked_reason(
                conn, jira_key,
                request.form.get("blocked_reason", "").strip() or None)
            conn.close()
            return redirect(url_for("delegated.delegated_ticket_detail",
                                    jira_key=jira_key, saved="1"))
        comments = db_jira.list_jira_comments(conn, jira_key)
        next_step = db_delegated.get_delegated_next_step(conn, jira_key)
        blocked_reason = db_delegated.get_delegated_blocked_reason(conn, jira_key)
        notes = database.list_notes(conn, "delegated", jira_key)
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "delegated_ticket.html",
        issue=issue, comments=comments,
        orders=extract_latest_comment_orders(comments),
        is_blocked=(issue.get("jira_status") or "").strip().lower() == "blocked",
        next_step=next_step, blocked_reason=blocked_reason,
        notes=notes, attachments_by_note=attachments_by_note,
        saved=request.args.get("saved") == "1",
        note_added=request.args.get("note_added") == "1",
        note_saved=request.args.get("note_saved") == "1",
        note_deleted=request.args.get("note_deleted") == "1",
    )


def report_context(conn) -> dict:
    """Template context for the status report — shared by the page, the
    download route, and the dashboard Export Reports snapshot."""
    issues, _comments = _load_issues(conn)
    annotations = db_delegated.get_delegated_annotations(conn)
    report_comments = database.list_report_comments(conn, "delegated")
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["next_step"] = ann.get("next_step")
        i["blocked_reason"] = ann.get("blocked_reason")
    sections = [(title, css, items)
                for _key, title, css, items in bucket_issues(issues, _me())]
    filter_options = {
        "statuses": sorted({(i.get("jira_status") or "").strip()
                            for i in issues if (i.get("jira_status") or "").strip()}),
        "assignees": sorted({(i.get("jira_assignee") or "").strip()
                             for i in issues if (i.get("jira_assignee") or "").strip()}),
    }
    return {
        "sections": sections, "total": len(issues),
        "filter_options": filter_options,
        "report_comments": report_comments,
        "today": date.today().strftime("%Y-%m-%d"),
    }


def numbers_context(conn) -> dict:
    """Template context for the numbers report — shared like report_context."""
    issues, _comments = _load_issues(conn)
    return {
        "counts": bucket_counts(issues, _me()),
        "total": len(issues),
        "today": date.today().strftime("%Y-%m-%d"),
    }


@bp.route("/report")
def delegated_report():
    """Delegated status report — sales-report layout (deliberately a COPY,
    the two reports are expected to grow apart [USER 2026-08-26]) with the
    delegated buckets as sections; editable call-outs (key 'delegated')."""
    conn = _get_conn()
    try:
        ctx = report_context(conn)
    finally:
        conn.close()
    return render_template("delegated_report.html", **ctx)


@bp.route("/report/download")
def delegated_report_download():
    """Dated standalone snapshot of the status report. The template carries
    its own inline CSS; download=True drops toolbar, filter bar and scripts
    and renders the call-outs as static text."""
    conn = _get_conn()
    try:
        ctx = report_context(conn)
    finally:
        conn.close()
    html = render_template("delegated_report.html", **ctx, download=True)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="delegated_report_{ctx["today"]}.html"',
    }


@bp.route("/numbers")
def delegated_numbers():
    """Delegated numbers report — counts per bucket (retail-report style).
    Later backlog items join these counts in delegated_buckets."""
    conn = _get_conn()
    try:
        ctx = numbers_context(conn)
    finally:
        conn.close()
    return render_template("delegated_numbers.html", **ctx)


@bp.route("/numbers/download")
def delegated_numbers_download():
    """Dated standalone snapshot of the numbers page. The template already
    carries its own inline CSS; download=True just drops toolbar + script."""
    conn = _get_conn()
    try:
        ctx = numbers_context(conn)
    finally:
        conn.close()
    html = render_template("delegated_numbers.html", **ctx, download=True)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="delegated_numbers_{ctx["today"]}.html"',
    }
