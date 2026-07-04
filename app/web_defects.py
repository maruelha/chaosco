"""Defects — list, detail, inline toggles, production defects

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
        meetings=database.MEETING_OPTIONS,
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


@app.route("/prod_defects")
def prod_defects_list():
    conn = _get_conn()
    try:
        rows = database.list_known_prod_defects(conn)
    finally:
        conn.close()
    return render_template("prod_defects.html", rows=rows)


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
            )
        finally:
            conn.close()
        return redirect(url_for("prod_defect_detail", record_id=row["id"], saved="1"))
    return render_template("prod_defect_detail.html", record={}, is_new=True, saved=False)


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
            )
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("prod_defect_detail", record_id=record_id, saved="1"))
    saved = request.args.get("saved") == "1"
    return render_template("prod_defect_detail.html", record=record, is_new=False, saved=saved)


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

