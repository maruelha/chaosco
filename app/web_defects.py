"""Defects — list, detail, inline toggles, production defects

Routes module (refactoring step 4) — registers on the shared app from
app.web_core; endpoint names and URLs are unchanged from the old monolith.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import openpyxl
from flask import jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app import database
from app.web_core import (app, _cfg, _get_conn, _not_found,
                          _UPLOAD_FOLDER, _IMAGE_EXTS, _ALLOWED_EXTS)

@app.route("/defects")
def defects_list():
    search        = request.args.get("search", "").strip()
    channel       = request.args.get("channel", "")
    statuses      = request.args.getlist("status")
    action_needed = request.args.get("action_needed", "no")
    dtco2c        = request.args.get("dtco2c", "")
    daily         = request.args.get("daily", "")
    show_all      = request.args.get("show_all") == "1"
    note_added    = request.args.get("note_added") == "1"

    hidden = _cfg.get("defects_hidden_statuses", [])
    exclude = [] if (show_all or statuses) else hidden

    conn = _get_conn()
    try:
        defects = database.list_defects(
            conn,
            search=search or None,
            channel=channel or None,
            statuses=statuses or None,
            action_needed=action_needed or None,
            exclude_statuses=exclude or None,
            dtco2c=dtco2c or None,
            daily=daily or None,
        )
        options = database.get_filter_options(conn)
    finally:
        conn.close()

    return render_template(
        "defects.html",
        defects=defects,
        options=options,
        search=search,
        channel=channel,
        statuses=statuses,
        action_needed=action_needed,
        dtco2c=dtco2c,
        daily=daily,
        show_all=show_all,
        hidden=hidden,
        note_added=note_added,
    )


@app.route("/defects/<defect_id>", methods=["GET", "POST"])
def defect_detail(defect_id: str):
    conn = _get_conn()
    try:
        defect = database.get_defect(conn, defect_id)
        if defect is None:
            return _not_found(defect_id)

        if request.method == "POST":
            def _field(name: str) -> str | None:
                v = request.form.get(name, "").strip()
                return v or None

            database.upsert_defect_annotation(
                conn,
                defect_id,
                description=_field("description"),
                business_impact=_field("business_impact"),
                reach=_field("reach"),
                retest_needs=_field("retest_needs"),
                next_step=_field("next_step"),
                action_needed=bool(request.form.get("action_needed")),
                comments=_field("comments"),
                dtco2c=bool(request.form.get("dtco2c")),
                dtco2c_resp=_field("dtco2c_resp"),
                daily=bool(request.form.get("daily")),
            )
            return redirect(url_for("defect_detail", defect_id=defect_id, saved="1"))

        notes = database.list_notes(conn, "defect", defect_id)
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes]
        )
        from app.db import planning as db_planning
        meetings = db_planning.get_meeting_options(conn)
    finally:
        conn.close()

    saved = request.args.get("saved") == "1"
    note_added = request.args.get("note_added") == "1"
    note_saved = request.args.get("note_saved") == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    added_to_meeting = request.args.get("added_to_meeting") == "1"
    return render_template(
        "defect_detail.html",
        defect=defect,
        saved=saved,
        notes=notes,
        attachments_by_note=attachments_by_note,
        note_added=note_added,
        note_saved=note_saved,
        note_deleted=note_deleted,
        added_to_meeting=added_to_meeting,
        meetings=meetings,
    )


# ---------------------------------------------------------------------------
# Spillover routes


@app.route("/defects/<defect_id>/dtco2c", methods=["POST"])
def defect_toggle_dtco2c(defect_id: str):
    value = request.json.get("value", False) if request.is_json else bool(request.form.get("value"))
    conn = _get_conn()
    try:
        database.set_defect_dtco2c(conn, defect_id, value)
    finally:
        conn.close()
    return {"ok": True}


@app.route("/defects/<defect_id>/daily", methods=["POST"])
def defect_toggle_daily(defect_id: str):
    value = request.json.get("value", False) if request.is_json else bool(request.form.get("value"))
    conn = _get_conn()
    try:
        database.set_defect_daily(conn, defect_id, value)
    finally:
        conn.close()
    return {"ok": True}


def _split_by_type(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Limitations and Risks each get their own table below the main one
    [USER 2026-08-27] — the main table keeps Defect/Accepted Defect/blank."""
    limitation_rows = [r for r in rows if (r.get("type") or "") == "Limitation"]
    risk_rows = [r for r in rows if (r.get("type") or "") == "Risk"]
    other_rows = [r for r in rows if (r.get("type") or "") not in ("Limitation", "Risk")]
    return other_rows, limitation_rows, risk_rows


def _group_by_scenario(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    """[(scenario, rows), ...] preserving the query's scenario sort order —
    the management report's per-scenario counts [USER 2026-08-27]."""
    groups: list[tuple[str, list[dict]]] = []
    for row in rows:
        key = row.get("scenario") or "(no scenario)"
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        groups[-1][1].append(row)
    return groups


def prod_defects_report_context(conn) -> dict:
    """Management report scope (planning chat 2026-08-27): Channel=ECOM,
    non-fixed. Defects/Accepted Defects and Limitations require BOTH
    audience flags (relevant for Core South AND GBS Ops) [USER]; Risks
    include ALL ECOM risks regardless of the flags [USER: "plus the
    risks"]. Sections carry per-scenario groups for the counts."""
    both_flags = database.list_known_prod_defects(
        conn, channel="ECOM", relevant_core_south="yes", relevant_gbs_ops="yes")
    defect_rows, limitation_rows, _ = _split_by_type(both_flags)
    risk_rows = database.list_known_prod_defects(conn, channel="ECOM", type_="Risk")
    sections = [
        ("Defects", "sec-defects", _group_by_scenario(defect_rows), len(defect_rows)),
        ("Limitations", "sec-limitations", _group_by_scenario(limitation_rows),
         len(limitation_rows)),
        ("Risks", "sec-risks", _group_by_scenario(risk_rows), len(risk_rows)),
    ]
    return {"sections": sections, "today": date.today().isoformat()}


@app.route("/prod_defects/report")
def prod_defects_report():
    """Management-facing summary [USER 2026-08-27: "management worthy
    summary"] — standalone print-ready page in the established report
    style; no working controls."""
    conn = _get_conn()
    try:
        ctx = prod_defects_report_context(conn)
    finally:
        conn.close()
    return render_template("prod_defects_report.html", download=False, **ctx)


@app.route("/prod_defects")
def prod_defects_list():
    channel = request.args.get("channel", "").strip()
    scenario = request.args.get("scenario", "").strip()
    relevant_cs = request.args.get("relevant_core_south", "").strip()
    relevant_gbs = request.args.get("relevant_gbs_ops", "").strip()
    conn = _get_conn()
    try:
        rows = database.list_known_prod_defects(
            conn, channel=channel or None, scenario=scenario or None,
            relevant_core_south=relevant_cs or None, relevant_gbs_ops=relevant_gbs or None)
        review_comment_count = len(database.list_review_comments(conn))
        fixed_count = len(database.list_known_prod_defects(conn, status="fixed"))
    finally:
        conn.close()
    rows, limitation_rows, risk_rows = _split_by_type(rows)
    return render_template(
        "prod_defects.html", rows=rows, limitation_rows=limitation_rows, risk_rows=risk_rows,
        channels=_PROD_DEFECT_CHANNELS, scenarios=_prod_defect_scenarios(),
        sel_channel=channel, sel_scenario=scenario,
        sel_relevant_cs=relevant_cs, sel_relevant_gbs=relevant_gbs,
        review_comment_count=review_comment_count,
        confluence_url=_cfg.get("prod_defects_confluence_url", ""),
        archived=False, fixed_count=fixed_count)


@app.route("/prod_defects/archive")
def prod_defects_archive():
    """Fixed items — kept for reference, excluded from the active list,
    downloads, email report and the ECOM Spillover Report section
    [USER 2026-08-27]. Reopen brings a row back to the active list."""
    channel = request.args.get("channel", "").strip()
    scenario = request.args.get("scenario", "").strip()
    relevant_cs = request.args.get("relevant_core_south", "").strip()
    relevant_gbs = request.args.get("relevant_gbs_ops", "").strip()
    conn = _get_conn()
    try:
        rows = database.list_known_prod_defects(
            conn, channel=channel or None, scenario=scenario or None,
            status="fixed",
            relevant_core_south=relevant_cs or None, relevant_gbs_ops=relevant_gbs or None)
    finally:
        conn.close()
    rows, limitation_rows, risk_rows = _split_by_type(rows)
    return render_template(
        "prod_defects.html", rows=rows, limitation_rows=limitation_rows, risk_rows=risk_rows,
        channels=_PROD_DEFECT_CHANNELS, scenarios=_prod_defect_scenarios(),
        sel_channel=channel, sel_scenario=scenario,
        sel_relevant_cs=relevant_cs, sel_relevant_gbs=relevant_gbs,
        review_comment_count=0,
        confluence_url="",
        archived=True,
        fixed_count=len(rows) + len(limitation_rows) + len(risk_rows))


_PROD_DEFECT_TYPES = ["Defect", "Limitation", "Risk", "Accepted Defect"]
_PROD_DEFECT_CHANNELS = ["ECOM", "Retail"]


def _prod_defect_scenarios() -> list[str]:
    return _cfg.get("prod_defect_scenarios", [])


@app.route("/prod_defects/new", methods=["GET", "POST"])
def prod_defect_new():
    if request.method == "POST":
        def _f(name): return request.form.get(name, "").strip() or None
        conn = _get_conn()
        try:
            row = database.create_known_prod_defect(
                conn,
                short_description=_f("short_description"),
                scenario=_f("scenario"),
                description=_f("description"),
                biz_impact=_f("biz_impact"),
                numbers=_f("numbers"),
                refs=_f("refs"),
                next_steps=_f("next_steps"),
                comments=_f("comments"),
                confluence=_f("confluence"),
                channel=_f("channel"),
                type_=_f("type"),
                sub_case=_f("sub_case"),
                how_to_detect=_f("how_to_detect"),
                how_to_handle=_f("how_to_handle"),
                relevant_core_south=bool(request.form.get("relevant_core_south")),
                relevant_gbs_ops=bool(request.form.get("relevant_gbs_ops")),
            )
        finally:
            conn.close()
        return redirect(url_for("prod_defect_detail", record_id=row["id"], saved="1"))
    return render_template("prod_defect_detail.html", record={}, is_new=True, saved=False,
                           scenarios=_prod_defect_scenarios(), types=_PROD_DEFECT_TYPES,
                           channels=_PROD_DEFECT_CHANNELS)


@app.route("/prod_defects/<int:record_id>", methods=["GET", "POST"])
def prod_defect_detail(record_id: int):
    conn = _get_conn()
    try:
        record = database.get_known_prod_defect(conn, record_id)
        if record is None:
            return _not_found(str(record_id))
        if request.method == "POST":
            def _f(name): return request.form.get(name, "").strip() or None
            database.update_known_prod_defect(
                conn, record_id,
                short_description=_f("short_description"),
                scenario=_f("scenario"),
                description=_f("description"),
                biz_impact=_f("biz_impact"),
                numbers=_f("numbers"),
                refs=_f("refs"),
                next_steps=_f("next_steps"),
                comments=_f("comments"),
                confluence=_f("confluence"),
                channel=_f("channel"),
                type_=_f("type"),
                sub_case=_f("sub_case"),
                how_to_detect=_f("how_to_detect"),
                how_to_handle=_f("how_to_handle"),
                relevant_core_south=bool(request.form.get("relevant_core_south")),
                relevant_gbs_ops=bool(request.form.get("relevant_gbs_ops")),
            )
        notes = database.list_notes(conn, "prod_defect", str(record_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("prod_defect_detail", record_id=record_id, saved="1"))
    saved = request.args.get("saved") == "1"
    return render_template("prod_defect_detail.html", record=record, is_new=False, saved=saved,
                           notes=notes, attachments_by_note=attachments_by_note,
                           scenarios=_prod_defect_scenarios(), types=_PROD_DEFECT_TYPES,
                           channels=_PROD_DEFECT_CHANNELS)


@app.route("/prod_defects/download")
def prod_defects_download():
    """Dated standalone snapshot of the full list (no filters applied) —
    same mechanism as the report Download HTML buttons."""
    from app.emailer import standalone_html
    resp = app.test_client().get(url_for("prod_defects_list"))
    today = date.today().isoformat()
    return standalone_html(resp.get_data(as_text=True)), 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="known_prod_defects_{today}.html"',
    }


@app.route("/prod_defects/download-review")
def prod_defects_download_review():
    """Standalone, offline-reviewable snapshot: read-only overview + a
    per-row Detail popup (no Edit/Delete), plus a client-side "add feedback"
    feature — comments are kept in the browser (localStorage) and exported
    as JSON to send back. No server round-trip once downloaded."""
    conn = _get_conn()
    try:
        rows = database.list_known_prod_defects(conn)
    finally:
        conn.close()
    today = date.today().isoformat()
    html = render_template(
        "prod_defects_review.html", rows=rows, today=today, types=_PROD_DEFECT_TYPES)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="known_prod_defects_review_{today}.html"',
    }


@app.route("/prod_defects/review-comments")
def prod_defects_review_comments():
    conn = _get_conn()
    try:
        comments = database.list_review_comments(conn)
        known_ids = {str(r["id"]) for r in database.list_known_prod_defects(conn)}
    finally:
        conn.close()
    for c in comments:
        c["defect_exists"] = c["defect_id"] in known_ids
    return render_template(
        "prod_defects_review_comments.html", comments=comments,
        imported=request.args.get("imported"), duplicate=request.args.get("duplicate"),
        malformed=request.args.get("malformed"), upload_error=request.args.get("upload_error"))


@app.route("/prod_defects/review-comments/upload", methods=["POST"])
def prod_defects_review_comments_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(url_for("prod_defects_review_comments", upload_error="No file selected."))
    try:
        payload = json.loads(f.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return redirect(url_for("prod_defects_review_comments",
                                upload_error="That file isn't valid JSON — is it the comments export?"))
    if not isinstance(payload, dict) or "comments" not in payload:
        return redirect(url_for("prod_defects_review_comments",
                                upload_error="That JSON doesn't look like a comments export (no 'comments' list)."))
    conn = _get_conn()
    try:
        result = database.import_review_comments(conn, payload)
    finally:
        conn.close()
    return redirect(url_for(
        "prod_defects_review_comments", imported=result["inserted"],
        duplicate=result["duplicate"], malformed=result["malformed"]))


@app.route("/prod_defects/review-comments/<comment_id>/delete", methods=["POST"])
def prod_defects_review_comment_delete(comment_id: str):
    conn = _get_conn()
    try:
        database.delete_review_comment(conn, comment_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/prod_defects/<int:record_id>/fixed", methods=["POST"])
def prod_defect_toggle_fixed(record_id: int):
    value = request.json.get("value", False) if request.is_json else request.form.get("value") == "1"
    conn = _get_conn()
    try:
        database.mark_known_prod_defect_fixed(conn, record_id, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/prod_defects/<int:record_id>/relevant-core-south", methods=["POST"])
def prod_defect_toggle_relevant_cs(record_id: int):
    """Inline list-column checkbox (2026-08-27) — mirrors the defects
    board's dtco2c/daily toggles (JSON body from a checkbox change)."""
    value = request.json.get("value", False) if request.is_json else request.form.get("value") == "1"
    conn = _get_conn()
    try:
        database.set_known_prod_defect_relevant_core_south(conn, record_id, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/prod_defects/<int:record_id>/relevant-gbs-ops", methods=["POST"])
def prod_defect_toggle_relevant_gbs(record_id: int):
    value = request.json.get("value", False) if request.is_json else request.form.get("value") == "1"
    conn = _get_conn()
    try:
        database.set_known_prod_defect_relevant_gbs_ops(conn, record_id, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/prod_defects/<int:record_id>/delete", methods=["POST"])
def prod_defect_delete(record_id: int):
    conn = _get_conn()
    try:
        database.delete_known_prod_defect(conn, record_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Links routes

