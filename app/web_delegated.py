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
from app.db import ecom as db_ecom
from app.db import jira as db_jira
from app.delegated_buckets import (BOARD_CSS, MB_EXPECTED, bucket_counts,
                                   bucket_issues, bucket_key, mb_status_state,
                                   overview_counts, staged_counts,
                                   unexpected_statuses)
from app.jira_importer import extract_latest_comment_orders, run_delegated_import

bp = Blueprint("delegated", __name__, url_prefix="/delegated")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = Path(__file__).parent.parent / "data" / "uploads"
# bucket for blockers nobody put a team on — last group of the Overview's
# blocker table, so an unassigned blocker stays visible [USER 2026-08-31]
_NO_TEAM = "No team assigned"


def _get_conn():
    return database.get_connection(_db_path)


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
    everything), so any issue whose Jira type isn't a story is dropped
    from the board/report/numbers here, registered as a blocker or not.
    "Story" matches by SUBSTRING (case-insensitive: "Story", "User
    Story", …) — an exact match emptied Marina's board on 2026-08-27
    because her Jira's type wording differed. A NULL type (export without
    <type>) is tolerated as a story rather than silently dropped; the
    board additionally SHOWS what the filter hid (_hidden_non_story)."""
    issues = db_jira.list_jira_issues(conn, seen_in="delegated")
    blocker_keys = db_blockers.list_blocker_jira_keys(conn)
    issues = [i for i in issues if i["jira_key"] not in blocker_keys
              and db_delegated.is_story_type(i.get("type"))]
    comments_map = {i["jira_key"]: db_jira.list_jira_comments(conn, i["jira_key"])
                    for i in issues}
    labels_map = db_jira.labels_for_issues(conn, [i["jira_key"] for i in issues])
    for i in issues:
        i["orders"] = extract_latest_comment_orders(
            comments_map[i["jira_key"]])["orders"]
        i["labels"] = labels_map.get(i["jira_key"], [])
    return issues, comments_map


def _hidden_non_story(conn) -> list[tuple[str, int]]:
    """[(type, count), …] of delegated-tagged, non-blocker issues the
    stories-only filter hides — shown on the board so the filter can never
    empty the page SILENTLY (that happened 2026-08-27)."""
    issues = db_jira.list_jira_issues(conn, seen_in="delegated")
    blocker_keys = db_blockers.list_blocker_jira_keys(conn)
    counts: dict[str, int] = {}
    for i in issues:
        if i["jira_key"] in blocker_keys:
            continue
        if not db_delegated.is_story_type(i.get("type")):
            key = (i.get("type") or "").strip() or "(no type)"
            counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


@bp.route("/")
def delegated_list():
    conn = _get_conn()
    try:
        issues, comments_map = _load_issues(conn)
        annotations = db_delegated.get_delegated_annotations(conn)
        note_counts = {i["jira_key"]: len(database.list_notes(
            conn, "delegated", i["jira_key"])) for i in issues}
        blockers_by_key = db_blockers.blockers_for_tickets(
            conn, [i["jira_key"] for i in issues])
        hidden_non_story = _hidden_non_story(conn)
        # MB join (2026-08-28 [USER]): the ECOM tab's row for the same
        # Jira ID — MB Status column on four buckets, full card on detail
        mb_rows = db_ecom.ecom_rows_for_jira_keys(
            conn, [i["jira_key"] for i in issues])
    finally:
        conn.close()
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["next_step"] = ann.get("next_step")
        i["blocked_reason"] = ann.get("blocked_reason")
        i["counts_toward_goal"] = ann.get("counts_toward_goal", False)
        i["backlog"] = ann.get("backlog", False)
        i["req_tool"] = ann.get("req_tool", False)
        i["sales_xls"] = ann.get("sales_xls")
        i["blockers"] = blockers_by_key.get(i["jira_key"], [])
        mb_row = mb_rows.get(i["jira_key"])
        i["mb_status"] = (mb_row or {}).get("status")
        i["mb_state"] = mb_status_state(bucket_key(i), mb_row)
    return render_template(
        "delegated.html",
        sections=bucket_issues(issues),
        board_css=BOARD_CSS,
        total=len(issues),
        all_labels=sorted({l for i in issues for l in i.get("labels", [])},
                          key=str.lower),
        jira_comments=comments_map,
        note_counts=note_counts,
        hidden_non_story=hidden_non_story,
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
        if result.get("blockers_registered"):
            msg += f" · {result['blockers_registered']} blockers registered"
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


@bp.route("/ticket/<jira_key>/backlog", methods=["POST"])
def delegated_backlog(jira_key: str):
    """Park/unpark toggle for the 📦 Backlog section (excluded from the
    Management Summary) [USER 2026-08-27]. Since 2026-09-01 [USER] the ONE
    control is the button on the detail page — parking is a deliberate act,
    so there is no board checkbox and no detail-form field for it."""
    conn = _get_conn()
    try:
        db_delegated.set_delegated_backlog(
            conn, jira_key, request.form.get("value") == "1")
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/ticket/<jira_key>/req-tool", methods=["POST"])
def delegated_req_tool(jira_key: str):
    """Inline checkbox toggle — dashboard-only flag [USER 2026-08-29], never
    shown on either report."""
    conn = _get_conn()
    try:
        db_delegated.set_delegated_req_tool(
            conn, jira_key, request.form.get("value") == "1")
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/ticket/<jira_key>/sales-xls", methods=["POST"])
def delegated_sales_xls(jira_key: str):
    """Cycling-chip save — dashboard-only TRI-STATE marker [USER 2026-09-01]
    ('documented in the Sales XLS?'): yes/no/maybe, empty = not assessed.
    Like ReqTool never shown on any report."""
    value = (request.form.get("value") or "").strip() or None
    if value is not None and value not in db_delegated.SALES_XLS_VALUES:
        return jsonify({"ok": False, "error": f"invalid value {value!r}"}), 400
    conn = _get_conn()
    try:
        db_delegated.set_delegated_sales_xls(conn, jira_key, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/upload-tracking", methods=["POST"])
def delegated_upload_tracking():
    """Upload the DTC_UAT_testtracking_ROE workbook and import ONLY its
    ECOM tab into the shared `ecom` table (2026-08-28 [USER] — same
    parse + upsert as the dashboard Import, so this also refreshes what
    the ECOM board shows; the other tabs stay with the dashboard
    Import). Feeds the MB Status column/card on this board."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return redirect(url_for("delegated.delegated_list", jira_ok="0",
                                jira_msg="No file selected."))
    name = f.filename.lower()
    stem = (_cfg.get("filename_stem") or "").strip().lower()
    if not name.endswith(".xlsx"):
        return redirect(url_for("delegated.delegated_list", jira_ok="0",
                                jira_msg="That is not an .xlsx file — pick the"
                                         " UAT test-tracking workbook."))
    if "testtracking" not in name and (not stem or stem not in name):
        return redirect(url_for(
            "delegated.delegated_list", jira_ok="0",
            jira_msg="That doesn't look like the UAT test-tracking workbook"
                     " — expected a filename containing 'testtracking'."))
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = _UPLOAD_FOLDER / f"delegated_tracking_{stamp}.xlsx"
    f.save(str(xlsx_path))
    from app.ecom_importer import ParseError, parse_ecom
    try:
        rows = parse_ecom(_cfg, xlsx_path=xlsx_path)["rows"]
    except ParseError as exc:
        return redirect(url_for("delegated.delegated_list", jira_ok="0",
                                jira_msg=str(exc)))
    # path read at call time (not the module-level _db_path) so the
    # schema lands in the SAME DB _get_conn writes to — also under test
    # monkeypatching
    db_ecom.init_schema(Path(_cfg["database_path"]))
    conn = _get_conn()
    try:
        counts = db_ecom.upsert_ecom_rows(
            conn, rows, date.today().strftime("%Y-%m-%d"))
        # diagnostic (2026-08-28): say immediately how many board tickets
        # now have an MB row, so a key mismatch is visible at upload time
        issues, _ = _load_issues(conn)
        keys = [i["jira_key"] for i in issues]
        matched = len(db_ecom.ecom_rows_for_jira_keys(conn, keys))
    finally:
        conn.close()
    msg = (f"{f.filename} (ECOM tab): {counts['inserted']} new ·"
           f" {counts['updated']} updated ·"
           f" {counts['skipped_missing_jira_id']} without Jira ID skipped ·"
           f" MB rows match {matched} of {len(keys)} board tickets")
    return redirect(url_for("delegated.delegated_list", jira_ok="1",
                            jira_msg=msg))


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
            # backlog deliberately NOT part of the form save — the detail
            # page's park/unpark button posts to /backlog [USER 2026-09-01]
            db_delegated.set_delegated_req_tool(
                conn, jira_key, request.form.get("req_tool") == "1")
            conn.close()
            return redirect(url_for("delegated.delegated_ticket_detail",
                                    jira_key=jira_key, saved="1"))
        comments = db_jira.list_jira_comments(conn, jira_key)
        issue["labels"] = db_jira.labels_for_issues(
            conn, [jira_key]).get(jira_key, [])
        mb_row = db_ecom.ecom_rows_for_jira_keys(
            conn, [jira_key]).get(jira_key)
        next_step = db_delegated.get_delegated_next_step(conn, jira_key)
        blocked_reason = db_delegated.get_delegated_blocked_reason(conn, jira_key)
        counts_toward_goal = db_delegated.get_delegated_counts_toward_goal(conn, jira_key)
        backlog = db_delegated.get_delegated_backlog(conn, jira_key)
        req_tool = db_delegated.get_delegated_req_tool(conn, jira_key)
        sales_xls = db_delegated.get_delegated_sales_xls(conn, jira_key)
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
        counts_toward_goal=counts_toward_goal, backlog=backlog,
        req_tool=req_tool, sales_xls=sales_xls,
        blockers=blockers,
        mb_row=mb_row,
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
        i["backlog"] = ann.get("backlog", False)
        i["blockers"] = blockers_by_key.get(i["jira_key"], [])
    sections = [(title, css, items)
                for _key, title, css, items in bucket_issues(issues)]
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
        # (label filter removed again 2026-08-28 [USER: "not interesting"
        # on the report] — the board keeps its Label filter)
    }
    return {
        "sections": sections, "total": len(issues),
        "filter_options": filter_options,
        "report_comments": report_comments,
        # call-out archive (2026-08-28 [USER]) — collapsed 🗄 history on
        # the screen page; the download shows live call-outs only
        "archived_callouts": database.list_archived_report_comments(
            conn, "delegated"),
        "today": date.today().strftime("%Y-%m-%d"),
    }


def _open_blockers(conn) -> list[dict]:
    """Blockers that are still open [USER 2026-08-27: "blockers should only
    show up if they are not closed"] — closed = manually closed or the jira
    ticket reached the done family. Shared by the Management Summary and the
    Overview so both reports can never disagree about what is open."""
    open_blockers = []
    for b in db_blockers.list_blockers(conn):
        jira_status = None
        if b["jira_key"]:
            issue = db_jira.get_jira_issue(conn, b["jira_key"])
            jira_status = issue["jira_status"] if issue else None
        if not db_blockers.is_closed(b, jira_status):
            open_blockers.append(b)
    return open_blockers


def numbers_context(conn) -> dict:
    """Template context for the Management Summary — shared like
    report_context. Goal actual [USER 2026-08-27] = tickets past the
    gatekeeper check (Settlementfile/GBS/Sales/Resolved) + BLOCKED tickets
    whose defect was found in a way that counts toward the goal
    (counts_toward_goal, independent of status)."""
    issues, _comments = _load_issues(conn)
    annotations = db_delegated.get_delegated_annotations(conn)
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["counts_toward_goal"] = ann.get("counts_toward_goal", False)
        i["backlog"] = ann.get("backlog", False)
    # backlog tickets are parked — OUT of the Management Summary entirely
    # (total, stages, goal actual) [USER 2026-08-27]
    issues = [i for i in issues if not i["backlog"]]
    stages, unexpected = staged_counts(issues)
    post_gatekeeper_total = next(t for k, _l, t, _r in stages if k == "post_gatekeeper")
    blocked_counting = sum(
        1 for i in issues
        if bucket_key(i) == "blocked" and i["counts_toward_goal"])
    open_blockers = _open_blockers(conn)
    blocked_ticket_counts = db_blockers.blocked_ticket_counts(conn)
    blocker_sections = [(key, label, [b for b in open_blockers if b["type"] == key])
                        for key, label in db_blockers.TYPE_SECTIONS]
    return {
        "stages": stages, "unexpected": unexpected,
        # name the odd statuses so nobody has to look them up [USER 2026-09-01]
        "unexpected_statuses": unexpected_statuses(issues),
        "total": len(issues),
        "goal": db_delegated.get_delegated_goal(conn),
        "actual": post_gatekeeper_total + blocked_counting,
        "blocked_counting": blocked_counting,
        "blocker_sections": blocker_sections,
        "blocked_ticket_counts": blocked_ticket_counts,
        "report_comments": database.list_report_comments(conn, "delegated_numbers"),
        # call-out archive (2026-08-28 [USER: "especially there"])
        "archived_callouts": database.list_archived_report_comments(
            conn, "delegated_numbers"),
        "today": date.today().strftime("%Y-%m-%d"),
    }


@bp.route("/wow")
def delegated_wow():
    """Ways of Working — the delegated-testing decision log [USER 2026-09-01]:
    ONE notes thread (shared notes system, entity ('delegated_wow', 'main'))
    to capture what is decided in the dailies. Inbox items can be filed
    here too (inbox filing target 'delegated_wow'). No own table — a note's
    entity flag says where it is pinned."""
    conn = _get_conn()
    try:
        notes = database.list_notes(conn, "delegated_wow", "main")
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template("delegated_wow.html", notes=notes,
                           attachments_by_note=attachments_by_note)


@bp.route("/wow/download")
def delegated_wow_download():
    """Dated standalone HTML snapshot of the Ways of Working notes [USER
    2026-09-01] — own self-contained template (inline CSS, no toolbar), like
    the three report downloads. Attachments are listed by name only."""
    conn = _get_conn()
    try:
        notes = database.list_notes(conn, "delegated_wow", "main")
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    today = date.today().strftime("%Y-%m-%d")
    html = render_template("delegated_wow_download.html", notes=notes,
                           attachments_by_note=attachments_by_note, today=today)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="delegated_ways_of_working_{today}.html"',
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


def overview_context(conn) -> dict:
    """Template context for the Delegated Testing Overview [USER 2026-08-31]
    — the management report: four pipeline stages (each with an In progress
    and a Blocked line), the execution-status bar, and the open blockers
    grouped by responsible TEAM instead of by type. Backlog tickets are out,
    same as on the Management Summary."""
    issues, _comments = _load_issues(conn)
    annotations = db_delegated.get_delegated_annotations(conn)
    blockers_by_key = db_blockers.blockers_for_tickets(
        conn, [i["jira_key"] for i in issues])
    for i in issues:
        ann = annotations.get(i["jira_key"]) or {}
        i["backlog"] = ann.get("backlog", False)
        # the Blocked line stages a ticket by its blocker's team
        i["blockers"] = blockers_by_key.get(i["jira_key"], [])
    issues = [i for i in issues if not i["backlog"]]
    ctx = overview_counts(issues)

    # blocker overview grouped by team [USER 2026-08-31] — fixed teams in
    # their combobox order first, then custom ones, "No team" last; empty
    # teams are left out entirely (no placeholder rows on a management page)
    by_team: dict[str, list] = {}
    for b in _open_blockers(conn):
        by_team.setdefault((b["team"] or "").strip() or _NO_TEAM, []).append(b)
    order = [t for t in db_blockers.FIXED_TEAMS if t in by_team]
    order += sorted((t for t in by_team
                     if t not in db_blockers.FIXED_TEAMS and t != _NO_TEAM),
                    key=str.lower)
    if _NO_TEAM in by_team:
        order.append(_NO_TEAM)

    ctx.update({
        "blocker_teams": [(t, by_team[t]) for t in order],
        "blocked_ticket_counts": db_blockers.blocked_ticket_counts(conn),
        "report_comments": database.list_report_comments(
            conn, "delegated_overview"),
        "archived_callouts": database.list_archived_report_comments(
            conn, "delegated_overview"),
        "today": date.today().strftime("%Y-%m-%d"),
    })
    return ctx


@bp.route("/overview")
def delegated_overview():
    """Delegated Testing Overview — the management report [USER 2026-08-31]:
    the pipeline by stage + the execution status, in the layout management
    asked for. Third report next to the status report and the Management
    Summary; the three deliberately stay separate."""
    conn = _get_conn()
    try:
        ctx = overview_context(conn)
    finally:
        conn.close()
    return render_template("delegated_overview.html", **ctx)


@bp.route("/overview/download")
def delegated_overview_download():
    """Dated standalone snapshot — download=True drops toolbar + scripts and
    renders the call-outs as static text, like the other two reports."""
    conn = _get_conn()
    try:
        ctx = overview_context(conn)
    finally:
        conn.close()
    html = render_template("delegated_overview.html", **ctx, download=True)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="delegated_overview_{ctx["today"]}.html"',
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
