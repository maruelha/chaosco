"""Sustainphase Issues — routes (Flask Blueprint; rewritten 2026-09-03
[USER]: source is now the Go-Live defect tracker workbook).

- `/`               the incidents board (tab "ASPEN Incidents"): every
                    column, comment history, notes + next step, filters
- `/upload`         file-picker upload (name-contains guard, dated copy)
- `/incident/<no>/next-step`   inline save
- `/solutions`      the Issue Solution tracker, read-only table + filters
- `/totals`         the computed totals (per interface all/open, per reason)
No SQL here.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for)

from app import database
from app.config_loader import load_config
from app.db import sustain_issues as db_si
from app.sustain_issues_importer import run_sustain_issues_import

bp = Blueprint("sustain_issues", __name__, url_prefix="/sustain-issues")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = Path(__file__).parent.parent / "data" / "uploads"

# the workbook is "Go-Live defect tracker[ (1)].xlsx" — browser copies work
_FILENAME_MARKER = "go-live defect tracker"

NOTES_ENTITY = "sustain_incident"


def _get_conn():
    return database.get_connection(_db_path)


def _distinct(rows: list[dict], field: str) -> list[str]:
    return sorted({(r.get(field) or "").strip() for r in rows
                   if (r.get(field) or "").strip()}, key=str.casefold)


@bp.route("/")
def sustain_issues_home():
    conn = _get_conn()
    try:
        incidents = db_si.list_incidents(conn)
        comments = db_si.comments_by_incident(conn)
        annotations = db_si.get_incident_annotations(conn)
        # the shared notes component, one instance per incident row
        notes_by_key = {i["incident_number"]: database.list_notes(
            conn, NOTES_ENTITY, i["incident_number"]) for i in incidents}
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for notes in notes_by_key.values() for n in notes])
    finally:
        conn.close()
    for i in incidents:
        i["comments"] = comments.get(i["incident_number"], [])
        i["next_step"] = (annotations.get(i["incident_number"]) or {}).get("next_step")
        i["notes"] = notes_by_key.get(i["incident_number"], [])
    return render_template(
        "sustain_issues.html",
        incidents=incidents,
        attachments_by_note=attachments_by_note,
        notes_entity=NOTES_ENTITY,
        filter_options={"requestor": _distinct(incidents, "requestor"),
                        "status": _distinct(incidents, "status"),
                        "assigned_to": _distinct(incidents, "assigned_to")},
        si_ok=request.args.get("si_ok"),
        si_msg=request.args.get("si_msg"),
    )


@bp.route("/upload", methods=["POST"])
def sustain_issues_upload():
    """Dated copy in data/uploads (traceability; mirrored by the backup),
    then import all three tabs — same pattern as the other card uploads."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return redirect(url_for("sustain_issues.sustain_issues_home",
                                si_ok="0", si_msg="No file selected."))
    name = f.filename.lower()
    if not name.endswith(".xlsx"):
        return redirect(url_for(
            "sustain_issues.sustain_issues_home", si_ok="0",
            si_msg="That is not an .xlsx file — pick the Go-Live defect"
                   " tracker workbook."))
    if _FILENAME_MARKER not in name:
        return redirect(url_for(
            "sustain_issues.sustain_issues_home", si_ok="0",
            si_msg="That doesn't look like the Go-Live defect tracker —"
                   " expected a filename containing 'Go-Live defect tracker'."))
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = _UPLOAD_FOLDER / f"sustain_issues_{stamp}.xlsx"
    f.save(str(xlsx_path))
    result = run_sustain_issues_import(_cfg, xlsx_path)
    if result["ok"]:
        msg = (f"{f.filename}: {result['incidents']} incidents —"
               f" {result['inserted']} new · {result['updated']} updated"
               f" · {result['new_comments']} new comments")
        if result["skipped"]:
            msg += f" · {result['skipped']} row(s) without incident number skipped"
        msg += (f" · {result['solutions']} issue-solution rows"
                f" · {result['interfaces']} interfaces")
        return redirect(url_for("sustain_issues.sustain_issues_home",
                                si_ok="1", si_msg=msg))
    return redirect(url_for("sustain_issues.sustain_issues_home",
                            si_ok="0", si_msg=result["error"]))


@bp.route("/incident/<incident_number>/next-step", methods=["POST"])
def sustain_incident_next_step(incident_number: str):
    """Save the incident's next step (inline; ↻ archive via the generic
    /next-steps 'sustain_incident' entity)."""
    value = (request.get_json(silent=True) or {}).get("next_step", "")
    conn = _get_conn()
    try:
        db_si.set_sustain_incident_next_step(conn, incident_number, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/solutions")
def sustain_solutions():
    """Issue Solution tracker — read-only table [USER: "not any edit
    possibility"]; dropdown filters per heading, text search over Text /
    Reason / Solution (client-side)."""
    conn = _get_conn()
    try:
        rows = db_si.list_solutions(conn)
    finally:
        conn.close()
    return render_template(
        "sustain_solutions.html", rows=rows,
        filter_options={f: _distinct(rows, f) for f in
                        ("owner", "interface", "msg", "external_reference",
                         "inc_reference", "status")})


def _download(html: str, stem: str, today: str):
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{stem}_{today}.html"',
    }


def totals_context(conn) -> dict:
    """The Total sheet, computed: per interface (all / open) with the rows
    behind each line, the unlisted interfaces ("n/a", …) as extra rows, a
    grand total, and the reasons report [USER 2026-09-03]. Shared by the
    page, the download and the Email Reports attachment."""
    return {"totals": db_si.interface_totals(conn),
            "reasons": db_si.reason_totals(conn),
            "closed_statuses": sorted(db_si.SOLUTION_CLOSED_STATUSES),
            "today": date.today().strftime("%Y-%m-%d")}


@bp.route("/totals")
def sustain_totals():
    conn = _get_conn()
    try:
        ctx = totals_context(conn)
    finally:
        conn.close()
    return render_template("sustain_totals.html", **ctx)


@bp.route("/totals/download")
def sustain_totals_download():
    """Dated standalone snapshot — the expandable lines survive (plain
    <details>), toolbar + copy buttons are dropped."""
    conn = _get_conn()
    try:
        ctx = totals_context(conn)
    finally:
        conn.close()
    html = render_template("sustain_totals.html", **ctx, download=True)
    return _download(html, "sustain_totals", ctx["today"])


def incidents_report_context(conn) -> dict:
    """ASPEN incidents REPORT [USER 2026-09-03: table for scanning, grouped
    by status, newest comment only, no next step]."""
    groups = db_si.incidents_by_status(conn)
    flat = [i for g in groups for i in g["incidents"]]
    return {"groups": groups, "total": len(flat),
            "filter_options": {"requestor": _distinct(flat, "requestor"),
                               "assigned": _distinct(flat, "assigned_to")},
            "today": date.today().strftime("%Y-%m-%d")}


@bp.route("/report")
def sustain_incidents_report():
    conn = _get_conn()
    try:
        ctx = incidents_report_context(conn)
    finally:
        conn.close()
    return render_template("sustain_incidents_report.html", **ctx)


@bp.route("/report/download")
def sustain_incidents_report_download():
    conn = _get_conn()
    try:
        ctx = incidents_report_context(conn)
    finally:
        conn.close()
    html = render_template("sustain_incidents_report.html", **ctx, download=True)
    return _download(html, "sustain_incidents", ctx["today"])
