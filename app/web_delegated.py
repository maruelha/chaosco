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
from app.db import blockers as db_blockers
from app.db import delegated as db_delegated
from app.db import jira as db_jira
from app.delegated_buckets import BOARD_CSS, bucket_counts, bucket_issues, bucket_key, staged_counts
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
    """Delegated issues + their comments + latest-comment orders.

    Tickets registered as a BLOCKER (app/db/blockers.py) are excluded here
    [USER 2026-08-27] — a defect/task that blocks testing must not also show
    up as a testing ticket to work through; it lives on the Blockers page
    instead. Same shared jira store, so its status/comments still refresh
    on the usual delegated upload.

    ONLY USER STORIES [USER 2026-08-27: "the main page should only have
    jira user stories"] — the delegated export deliberately also carries
    the blocker DEFECT issues (blockers design: one upload refreshes
    everything), so any issue whose Jira type isn't Story is dropped from
    the board/report/numbers here, registered as a blocker or not. A NULL
    type (export without <type>) is tolerated as a story rather than
    silently dropped."""
    issues = db_jira.list_jira_issues(conn, seen_in="delegated")
    blocker_keys = db_blockers.list_blocker_jira_keys(conn)
    issues = [i for i in issues if i["jira_key"] not in blocker_keys
              and (i.get("type") is None
                   or i["type"].strip().lower() == "story")]
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
        blockers_by_key = db_blockers.blockers_for_tickets(
            conn, [i["jira_key"] for i in issues])
    finally:
        conn.close()
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["next_step"] = ann.get("next_step")
        i["blocked_reason"] = ann.get("blocked_reason")
        i["counts_toward_goal"] = ann.get("counts_toward_goal", False)
        i["blockers"] = blockers_by_key.get(i["jira_key"], [])
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


@bp.route("/ticket/<jira_key>/counts-toward-goal", methods=["POST"])
def delegated_counts_toward_goal(jira_key: str):
    """Inline checkbox toggle — whether this BLOCKED ticket's defect counts
    toward the weekly goal (depends on WHERE it was found, not on status)."""
    conn = _get_conn()
    try:
        db_delegated.set_delegated_counts_toward_goal(
            conn, jira_key, request.form.get("value") == "1")
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
            db_delegated.set_delegated_counts_toward_goal(
                conn, jira_key, request.form.get("counts_toward_goal") == "1")
            conn.close()
            return redirect(url_for("delegated.delegated_ticket_detail",
                                    jira_key=jira_key, saved="1"))
        comments = db_jira.list_jira_comments(conn, jira_key)
        next_step = db_delegated.get_delegated_next_step(conn, jira_key)
        blocked_reason = db_delegated.get_delegated_blocked_reason(conn, jira_key)
        counts_toward_goal = db_delegated.get_delegated_counts_toward_goal(conn, jira_key)
        blockers = db_blockers.list_blockers_for_ticket(conn, jira_key)
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
        counts_toward_goal=counts_toward_goal, blockers=blockers,
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
    blockers_by_key = db_blockers.blockers_for_tickets(
        conn, [i["jira_key"] for i in issues])
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["next_step"] = ann.get("next_step")
        i["blocked_reason"] = ann.get("blocked_reason")
        i["blockers"] = blockers_by_key.get(i["jira_key"], [])
    sections = [(title, css, items)
                for _key, title, css, items in bucket_issues(issues, _me())]
    # blocker filter (step 9) — only blockers actually attached to a ticket
    # in THIS report, same defect/task/clarification order as everywhere else
    type_order = {key: idx for idx, (key, _) in enumerate(db_blockers.TYPE_SECTIONS)}
    seen_blockers = {b["blocker_id"]: b for i in issues for b in i["blockers"]}
    blocker_options = [
        {"blocker_id": b["blocker_id"],
         "label": b["name"] + (f" ({b['jira_key']})" if b["jira_key"] else "")}
        for b in sorted(seen_blockers.values(),
                        key=lambda b: (type_order.get(b["type"], 9), b["name"].lower()))
    ]
    filter_options = {
        "statuses": sorted({(i.get("jira_status") or "").strip()
                            for i in issues if (i.get("jira_status") or "").strip()}),
        "assignees": sorted({(i.get("jira_assignee") or "").strip()
                             for i in issues if (i.get("jira_assignee") or "").strip()}),
        "blockers": blocker_options,
    }
    return {
        "sections": sections, "total": len(issues),
        "filter_options": filter_options,
        "report_comments": report_comments,
        "today": date.today().strftime("%Y-%m-%d"),
    }


def numbers_context(conn) -> dict:
    """Template context for the Management Summary — shared like
    report_context. Goal actual [USER 2026-08-27] = tickets past the
    gatekeeper check (Settlementfile/GBS/Sales/Resolved) + BLOCKED tickets
    whose defect was found in a way that counts toward the goal
    (counts_toward_goal, independent of status)."""
    issues, _comments = _load_issues(conn)
    annotations = db_delegated.get_delegated_annotations(conn)
    me = _me()
    for i in issues:
        i["counts_toward_goal"] = (annotations.get(i["jira_key"]) or {}).get(
            "counts_toward_goal", False)
    stages, unexpected = staged_counts(issues, me)
    post_gatekeeper_total = next(t for k, _l, t, _r in stages if k == "post_gatekeeper")
    blocked_counting = sum(
        1 for i in issues
        if bucket_key(i, me) == "blocked" and i["counts_toward_goal"])
    blockers = db_blockers.list_blockers(conn)
    # only OPEN blockers on the Management Summary [USER 2026-08-27:
    # "blockers should only show up if they are not closed"] — closed =
    # manually closed or the jira ticket reached the done family
    open_blockers = []
    for b in blockers:
        jira_status = None
        if b["jira_key"]:
            issue = db_jira.get_jira_issue(conn, b["jira_key"])
            jira_status = issue["jira_status"] if issue else None
        if not db_blockers.is_closed(b, jira_status):
            open_blockers.append(b)
    blocked_ticket_counts = db_blockers.blocked_ticket_counts(conn)
    blocker_sections = [(key, label, [b for b in open_blockers if b["type"] == key])
                        for key, label in db_blockers.TYPE_SECTIONS]
    return {
        "stages": stages, "unexpected": unexpected,
        "total": len(issues),
        "goal": db_delegated.get_delegated_goal(conn),
        "actual": post_gatekeeper_total + blocked_counting,
        "blocked_counting": blocked_counting,
        "blocker_sections": blocker_sections,
        "blocked_ticket_counts": blocked_ticket_counts,
        "report_comments": database.list_report_comments(conn, "delegated_numbers"),
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
    """Management Summary Status Report (renamed 2026-08-27, was "numbers" —
    route/template/filenames kept so exports/email keep working): bucket
    counts staged into 3 review groups, the weekly goal vs actual, and a
    blocker overview. Later backlog items join the counts in
    delegated_buckets."""
    conn = _get_conn()
    try:
        ctx = numbers_context(conn)
    finally:
        conn.close()
    return render_template("delegated_numbers.html", **ctx)


@bp.route("/numbers/goal", methods=["POST"])
def delegated_goal_save():
    """Inline blur-save of the ONE weekly goal number — no history kept
    [USER 2026-08-27], downloaded reports serve as the history."""
    conn = _get_conn()
    try:
        db_delegated.set_delegated_goal(conn, request.form.get("goal", type=int) or 0)
    finally:
        conn.close()
    return jsonify({"ok": True})


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
