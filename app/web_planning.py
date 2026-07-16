"""Planning — CS follow-ups, meeting prep, todos, followups, enhancements

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

@app.route("/cs_followups")
def cs_followup_list():
    areas     = request.args.getlist("area")
    with_whom = request.args.getlist("with_whom")
    statuses  = request.args.getlist("status")
    show_done = request.args.get("done") == "1"
    conn = _get_conn()
    try:
        rows    = database.list_cs_followups(conn, areas=areas or None,
                                             with_whom=with_whom or None,
                                             statuses=statuses or None,
                                             include_done=show_done)
        options = database.get_cs_followup_options(conn)
    finally:
        conn.close()
    return render_template("cs_followup_list.html", rows=rows, options=options,
                           areas=areas, with_whom=with_whom, statuses=statuses,
                           show_done=show_done,
                           all_statuses=database.CS_FOLLOWUP_STATUSES,
                           today=date.today().isoformat())


@app.route("/cs_followups/new", methods=["GET", "POST"])
def cs_followup_new():
    if request.method == "POST":
        def _f(n): return request.form.get(n, "").strip() or None
        conn = _get_conn()
        try:
            row = database.create_cs_followup(
                conn,
                area=_f("area"), jira_id=_f("jira_id"), topic=request.form.get("topic", "").strip(),
                description=_f("description"), next_step=_f("next_step"), with_whom=_f("with_whom"),
            )
        finally:
            conn.close()
        return redirect(url_for("cs_followup_detail", followup_id=row["id"], saved="1"))
    return render_template("cs_followup_detail.html", record={}, is_new=True, saved=False)


@app.route("/cs_followups/<int:followup_id>", methods=["GET", "POST"])
def cs_followup_detail(followup_id: int):
    saved = request.args.get("saved") == "1"
    conn = _get_conn()
    try:
        record = database.get_cs_followup(conn, followup_id)
        if record is None:
            return render_template("404.html"), 404
        if request.method == "POST":
            def _f(n): return request.form.get(n, "").strip() or None
            database.update_cs_followup(
                conn, followup_id,
                area=_f("area"), jira_id=_f("jira_id"),
                topic=request.form.get("topic", "").strip(),
                description=_f("description"), next_step=_f("next_step"),
                with_whom=_f("with_whom"),
            )
        notes = database.list_notes(conn, "cs_followup", str(followup_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("cs_followup_detail", followup_id=followup_id, saved="1"))
    return render_template("cs_followup_detail.html", record=record, is_new=False, saved=saved,
                           notes=notes, attachments_by_note=attachments_by_note)


@app.route("/cs_followups/<int:followup_id>/status", methods=["POST"])
def cs_followup_status(followup_id: int):
    status = request.form.get("status", "")
    if status not in database.CS_FOLLOWUP_STATUSES:
        return jsonify({"ok": False})
    conn = _get_conn()
    try:
        database.set_cs_followup_status(conn, followup_id, status)
    finally:
        conn.close()
    return jsonify({"ok": True, "status": status})


@app.route("/cs_followups/<int:followup_id>/delete", methods=["POST"])
def cs_followup_delete(followup_id: int):
    conn = _get_conn()
    try:
        database.delete_cs_followup(conn, followup_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/meeting-prep")
def meeting_prep_list():
    meeting_filter = request.args.get("meeting", "")
    status_filter  = request.args.get("status", "planned")
    conn = _get_conn()
    try:
        items = database.get_meeting_prep(
            conn,
            meeting=meeting_filter or None,
            status=status_filter or None,
        )
    finally:
        conn.close()
    return render_template(
        "meeting_prep.html",
        items=items,
        meetings=database.MEETING_OPTIONS,
        overall_topics=database.MEETING_OVERALL_TOPICS,
        meeting_filter=meeting_filter,
        status_filter=status_filter,
    )


@app.route("/meeting-prep/agenda")
def meeting_prep_agenda():
    meeting_filter = request.args.get("meeting", "")
    status_filter  = request.args.get("status", "planned")
    conn = _get_conn()
    try:
        items = database.get_meeting_prep(
            conn,
            meeting=meeting_filter or None,
            status=status_filter or None,
        )
    finally:
        conn.close()
    order = {t: i for i, t in enumerate(database.MEETING_OVERALL_TOPICS)}
    items.sort(key=lambda r: (order.get(r.get("overall_topic") or "", 999), r.get("id", 0)))
    return render_template(
        "meeting_agenda.html",
        items=items,
        meeting_filter=meeting_filter,
        status_filter=status_filter,
        today=date.today().strftime("%d %B %Y"),
        overall_topics=database.MEETING_OVERALL_TOPICS,
    )


@app.route("/meeting-prep/dtco2c-daily")
def dtco2c_daily_report():
    conn = _get_conn()
    try:
        topics    = database.get_meeting_prep(conn, meeting="DTC O2C Daily", status="planned")
        defects   = database.list_daily_defects(conn)
        followups = database.get_followups(conn, with_whom="DTC O2C", include_done=False)
    finally:
        conn.close()
    return render_template(
        "dtco2c_daily_report.html",
        topics=topics,
        defects=defects,
        followups=followups,
        today=date.today().strftime("%d %B %Y"),
    )


@app.route("/meeting-prep/add", methods=["POST"])
def meeting_prep_add():
    meeting             = request.form.get("meeting", "").strip()
    topic               = request.form.get("topic", "").strip()
    source_entity_type  = request.form.get("source_entity_type", "").strip() or None
    source_entity_id    = request.form.get("source_entity_id", "").strip() or None
    overall_topic       = request.form.get("overall_topic", "").strip() or None
    if meeting and topic:
        conn = _get_conn()
        try:
            database.add_meeting_prep(conn, meeting, topic,
                                      source_entity_type, source_entity_id,
                                      overall_topic)
        finally:
            conn.close()
    back = request.form.get("back_url")
    if back:
        return redirect(back + "?added_to_meeting=1")
    return redirect(url_for("meeting_prep_list",
                            meeting=request.form.get("meeting_filter", "")))


@app.route("/meeting-prep/<int:item_id>/status", methods=["POST"])
def meeting_prep_status(item_id: int):
    status = request.form.get("status", "planned")
    conn = _get_conn()
    try:
        database.set_meeting_prep_status(conn, item_id, status)
    finally:
        conn.close()
    return jsonify({"ok": True, "status": status})


@app.route("/meeting-prep/<int:item_id>/note", methods=["POST"])
def meeting_prep_note(item_id: int):
    note = request.form.get("note", "").strip()
    conn = _get_conn()
    try:
        database.set_meeting_prep_note(conn, item_id, note)
    finally:
        conn.close()
    return jsonify({"ok": True, "note": note})


@app.route("/meeting-prep/<int:item_id>/topic", methods=["POST"])
def meeting_prep_topic(item_id: int):
    topic = request.form.get("topic", "").strip()
    if not topic:
        return jsonify({"ok": False, "error": "empty"})
    conn = _get_conn()
    try:
        database.set_meeting_prep_topic(conn, item_id, topic)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic})


@app.route("/meeting-prep/<int:item_id>/overall_topic", methods=["POST"])
def meeting_prep_overall_topic(item_id: int):
    overall_topic = request.form.get("overall_topic", "").strip() or None
    conn = _get_conn()
    try:
        database.set_meeting_prep_overall_topic(conn, item_id, overall_topic)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/meeting-prep/<int:item_id>/delete", methods=["POST"])
def meeting_prep_delete(item_id: int):
    conn = _get_conn()
    try:
        database.delete_meeting_prep(conn, item_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# To-do list


@app.route("/todos")
def todo_list():
    f_area    = request.args.get("area", "")
    f_status  = request.args.get("status", "")
    f_prio    = request.args.get("priority", "")
    f_whom    = request.args.get("for_whom", "")
    f_due     = request.args.get("due_date", "")
    f_closed  = request.args.get("closed", "") == "1"
    conn = _get_conn()
    try:
        items   = database.get_todos(conn,
                    area=f_area or None, status=f_status or None,
                    priority=f_prio or None, for_whom=f_whom or None,
                    due_date=f_due or None, include_closed=f_closed)
        opts    = database.get_todo_filter_options(conn)
    finally:
        conn.close()
    today = date.today().isoformat()
    return render_template("todo_list.html",
        items=items, opts=opts, today=today,
        statuses=database.TODO_STATUSES,
        priorities=database.TODO_PRIORITIES,
        f_area=f_area, f_status=f_status, f_prio=f_prio,
        f_whom=f_whom, f_due=f_due, f_closed=f_closed)


@app.route("/todos/add", methods=["POST"])
def todo_add():
    topic    = request.form.get("topic", "").strip()
    area     = request.form.get("area", "").strip()
    kind     = request.form.get("kind", "").strip()
    priority = request.form.get("priority", "Medium")
    due_date = request.form.get("due_date", "").strip()
    for_whom = request.form.get("for_whom", "").strip()
    if topic:
        conn = _get_conn()
        try:
            database.add_todo(conn, area, kind, topic, priority, due_date, for_whom)
        finally:
            conn.close()
    return redirect(url_for("todo_list"))


@app.route("/todos/<int:todo_id>/edit", methods=["POST"])
def todo_edit(todo_id: int):
    topic    = request.form.get("topic", "").strip()
    area     = request.form.get("area", "").strip()
    kind     = request.form.get("kind", "").strip()
    priority = request.form.get("priority", "Medium")
    due_date = request.form.get("due_date", "").strip()
    for_whom = request.form.get("for_whom", "").strip()
    if topic:
        conn = _get_conn()
        try:
            database.update_todo(conn, todo_id, area, kind, topic, priority, due_date, for_whom)
        finally:
            conn.close()
    return jsonify({"ok": True})


@app.route("/todos/<int:todo_id>/status", methods=["POST"])
def todo_status(todo_id: int):
    status = request.form.get("status", "open")
    conn = _get_conn()
    try:
        database.set_todo_status(conn, todo_id, status)
    finally:
        conn.close()
    return jsonify({"ok": True, "status": status})


@app.route("/followups")
def followup_list():
    f_whom      = request.args.getlist("with_whom")
    f_group     = request.args.getlist("group_name")
    f_when      = request.args.get("when_next", "")
    f_done      = request.args.get("done", "") == "1"
    conn = _get_conn()
    try:
        items = database.get_followups(conn,
                    with_whom=f_whom or None,
                    when_next=f_when or None,
                    group_name=f_group or None,
                    include_done=f_done)
        opts  = database.get_followup_filter_options(conn)
        incoming = database.list_incoming_notes(conn, "followup")
    finally:
        conn.close()
    today = date.today().isoformat()
    return render_template("followup_list.html",
        items=items, opts=opts, today=today, incoming=incoming,
        statuses=database.FOLLOWUP_STATUSES,
        f_whom=f_whom, f_group=f_group, f_when=f_when, f_done=f_done)


@app.route("/followups/add", methods=["POST"])
def followup_add():
    with_whom  = request.form.get("with_whom", "").strip()
    topic      = request.form.get("topic", "").strip()
    when_next  = request.form.get("when_next", "").strip() or date.today().isoformat()
    group_name = request.form.get("group_name", "").strip() or None
    if with_whom and topic:
        conn = _get_conn()
        try:
            database.add_followup(conn, with_whom, topic, when_next, group_name)
        finally:
            conn.close()
    return redirect(url_for("followup_list"))


@app.route("/followups/<int:followup_id>/edit", methods=["POST"])
def followup_edit(followup_id: int):
    with_whom  = request.form.get("with_whom", "").strip()
    topic      = request.form.get("topic", "").strip()
    when_next  = request.form.get("when_next", "").strip() or None
    group_name = request.form.get("group_name", "").strip() or None
    if with_whom and topic:
        conn = _get_conn()
        try:
            database.update_followup(conn, followup_id, with_whom, topic, when_next, group_name)
        finally:
            conn.close()
    return redirect(url_for("followup_list"))


@app.route("/followups/<int:followup_id>/delete", methods=["POST"])
def followup_delete(followup_id: int):
    conn = _get_conn()
    try:
        database.delete_followup(conn, followup_id)
    finally:
        conn.close()
    return redirect(url_for("followup_list"))


@app.route("/followups/<int:followup_id>/status", methods=["POST"])
def followup_status(followup_id: int):
    status = request.form.get("status", "open")
    conn = _get_conn()
    try:
        database.set_followup_status(conn, followup_id, status)
    finally:
        conn.close()
    return jsonify({"ok": True, "status": status})


@app.route("/followups/<int:followup_id>")
def followup_detail(followup_id: int):
    note_added   = request.args.get("note_added") == "1"
    note_saved   = request.args.get("note_saved") == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    conn = _get_conn()
    try:
        row = database.get_followup_by_id(conn, followup_id)
        if row is None:
            return render_template("404.html"), 404
        notes = database.list_notes(conn, "followup", str(followup_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "followup_detail.html", row=row,
        notes=notes, attachments_by_note=attachments_by_note,
        note_added=note_added, note_saved=note_saved, note_deleted=note_deleted,
        statuses=database.FOLLOWUP_STATUSES,
    )


@app.route("/enhancements")
def enhancements_list():
    area           = request.args.get("area", "")
    priority       = request.args.get("priority", "")
    status         = request.args.get("status", "")
    include_closed = request.args.get("closed", "") == "1"
    conn = _get_conn()
    try:
        items = database.get_enhancements(
            conn,
            area=area or None,
            priority=priority or None,
            status=status or None,
            include_closed=include_closed,
        )
        areas = database.get_enhancement_areas(conn)
    finally:
        conn.close()
    return jsonify({
        "items": items,
        "areas": areas,
        "priorities": database.ENHANCEMENT_PRIORITIES,
    })


@app.route("/enhancements/add", methods=["POST"])
def enhancements_add():
    area        = request.form.get("area", "").strip()
    enhancement = request.form.get("enhancement", "").strip()
    priority    = request.form.get("priority", "Medium")
    if not enhancement:
        return jsonify({"ok": False, "error": "enhancement required"})
    conn = _get_conn()
    try:
        new_id = database.add_enhancement(conn, area, enhancement, priority)
    finally:
        conn.close()
    return jsonify({"ok": True, "id": new_id})


@app.route("/enhancements/<int:item_id>/status", methods=["POST"])
def enhancements_status(item_id: int):
    status = request.form.get("status", "not_started")
    conn = _get_conn()
    try:
        database.set_enhancement_status(conn, item_id, status)
    finally:
        conn.close()
    return jsonify({"ok": True, "status": status})


@app.route("/enhancements/page")
def enhancements_page():
    include_closed = request.args.get("closed", "") == "1"
    sort  = request.args.get("sort", "priority")
    dirn  = request.args.get("dir", "asc")
    conn = _get_conn()
    try:
        items = database.get_enhancements(conn, include_closed=include_closed)
    finally:
        conn.close()
    prio_order = {"High": 0, "Medium": 1, "Low": 2}
    status_order = {"not_started": 0, "in_progress": 1, "closed": 2}
    reverse = dirn == "desc"
    if sort == "priority":
        items.sort(key=lambda r: prio_order.get(r["priority"], 9), reverse=reverse)
    elif sort == "status":
        items.sort(key=lambda r: status_order.get(r["status"], 9), reverse=reverse)
    elif sort == "area":
        items.sort(key=lambda r: (r["area"] or "").lower(), reverse=reverse)
    return render_template(
        "enhancements_page.html",
        items=items,
        include_closed=include_closed,
        priorities=database.ENHANCEMENT_PRIORITIES,
        sort=sort,
        dirn=dirn,
    )


@app.route("/enhancements/<int:item_id>/delete", methods=["POST"])
def enhancements_delete(item_id: int):
    conn = _get_conn()
    try:
        database.delete_enhancement(conn, item_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/enhancements/<int:item_id>/update", methods=["POST"])
def enhancements_update(item_id: int):
    area        = request.form.get("area", "").strip()
    enhancement = request.form.get("enhancement", "").strip()
    priority    = request.form.get("priority", "Medium")
    if not enhancement:
        return jsonify({"ok": False, "error": "enhancement text required"})
    conn = _get_conn()
    try:
        database.update_enhancement(conn, item_id, area, enhancement, priority)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Inbox â€” daily capture notes (entity_type='input', entity_id='inbox')

