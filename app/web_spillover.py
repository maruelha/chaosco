"""Core South Spillover — list, annotations, detail, status report, order details

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

from app.ppt_spillover import build_spillover_ppt

@app.route("/spillover")
def spillover_list():
    area        = request.args.getlist("area")
    type_       = request.args.getlist("type")
    status      = request.args.getlist("status")
    assigned_to = request.args.getlist("assigned_to")
    critical    = request.args.getlist("critical")
    with_whom   = request.args.getlist("with_whom")
    in_report   = request.args.get("in_report", "")
    show_all    = request.args.get("show_all") == "1"

    hidden = _cfg.get("spillover_hidden_statuses", [])
    exclude = [] if (show_all or status) else hidden

    conn = _get_conn()
    try:
        rows    = database.get_spillover(
            conn,
            statuses=status or None,
            areas=area or None,
            types=type_ or None,
            assignees=assigned_to or None,
            critical=critical or None,
            with_whom=with_whom or None,
            in_report=in_report or None,
            exclude_statuses=exclude or None,
        )
        options          = database.get_spillover_filter_options(conn)
        docs_s4_ids      = database.get_docs_s4_spillover_ids(conn)
        report_comments  = database.list_report_comments(conn, "spillover")
        from app.db import teams_chats as db_tc
        chats_by_entity  = db_tc.chats_by_entity(conn, "spillover")
    finally:
        conn.close()

    return render_template(
        "spillover.html",
        rows=rows,
        options=options,
        area=area,
        type_=type_,
        status=status,
        assigned_to=assigned_to,
        critical=critical,
        with_whom=with_whom,
        in_report=in_report,
        show_all=show_all,
        hidden_statuses=hidden,
        docs_s4_ids=docs_s4_ids,
        report_comments=report_comments,
        chats_by_entity=chats_by_entity,
    )


@app.route("/spillover/<int:spillover_id>/annotation", methods=["POST"])
def spillover_annotation_save(spillover_id: int):
    importance          = request.form.get("importance_for_signoff", "").strip() or None
    next_step           = request.form.get("next_step", "").strip() or None
    comment_for_signoff = request.form.get("comment_for_signoff", "").strip() or None
    signoff_group       = request.form.get("signoff_group", "").strip() or None
    conn = _get_conn()
    try:
        existing        = database.get_spillover_annotation(conn, spillover_id)
        comment_history = existing["comment_history"] if existing else None
        critical        = existing["critical_for_signoff"] if existing else None
        database.upsert_spillover_annotation(
            conn, spillover_id, importance, next_step, comment_history, critical, comment_for_signoff, signoff_group)
        ann = database.get_spillover_annotation(conn, spillover_id)
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "importance_for_signoff": ann.get("importance_for_signoff") or "",
        "next_step":              ann.get("next_step") or "",
        "comment_for_signoff":    ann.get("comment_for_signoff") or "",
        "signoff_group":          ann.get("signoff_group") or "",
    })


@app.route("/spillover/<int:spillover_id>/comment", methods=["POST"])
def spillover_comment_save(spillover_id: int):
    comment_history = request.form.get("comment_history", "").strip() or None
    conn = _get_conn()
    try:
        existing            = database.get_spillover_annotation(conn, spillover_id)
        importance          = existing["importance_for_signoff"] if existing else None
        next_step           = existing["next_step"] if existing else None
        critical            = existing["critical_for_signoff"] if existing else None
        comment_for_signoff = existing["comment_for_signoff"] if existing else None
        signoff_group       = existing["signoff_group"] if existing else None
        database.upsert_spillover_annotation(
            conn, spillover_id, importance, next_step, comment_history, critical, comment_for_signoff, signoff_group)
        ann = database.get_spillover_annotation(conn, spillover_id)
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "comment_history": ann["comment_history"] or "",
    })


@app.route("/spillover/<int:spillover_id>/comment-signoff", methods=["POST"])
def spillover_comment_signoff_save(spillover_id: int):
    """Inline comment column on the report table view."""
    comment = request.form.get("comment_for_signoff", "").strip() or None
    conn = _get_conn()
    try:
        database.set_spillover_comment_for_signoff(conn, spillover_id, comment)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/spillover/<int:spillover_id>/with-whom", methods=["POST"])
def spillover_with_whom_save(spillover_id: int):
    """Who follows up: Sales | MB | blank — inline select on the list."""
    value = request.form.get("with_whom", "").strip()
    if value not in ("", "Sales", "MB"):
        return jsonify({"ok": False, "error": "with_whom must be Sales or MB"}), 400
    conn = _get_conn()
    try:
        database.set_spillover_with_whom(conn, spillover_id, value or None)
    finally:
        conn.close()
    return jsonify({"ok": True, "with_whom": value})


@app.route("/spillover/<int:spillover_id>/critical", methods=["POST"])
def spillover_critical_save(spillover_id: int):
    critical = request.form.get("critical_for_signoff", "").strip() or None
    conn = _get_conn()
    try:
        existing            = database.get_spillover_annotation(conn, spillover_id)
        importance          = existing["importance_for_signoff"] if existing else None
        next_step           = existing["next_step"] if existing else None
        comment_history     = existing["comment_history"] if existing else None
        comment_for_signoff = existing["comment_for_signoff"] if existing else None
        signoff_group       = existing["signoff_group"] if existing else None
        database.upsert_spillover_annotation(
            conn, spillover_id, importance, next_step, comment_history, critical, comment_for_signoff, signoff_group)
        ann = database.get_spillover_annotation(conn, spillover_id)
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "critical_for_signoff": ann["critical_for_signoff"] or "",
    })


# ---------------------------------------------------------------------------
# Spillover detail + note routes


@app.route("/spillover/<int:spillover_id>")
def spillover_detail(spillover_id: int):
    note_added   = request.args.get("note_added")   == "1"
    note_saved   = request.args.get("note_saved")   == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    conn = _get_conn()
    try:
        row = database.get_spillover_by_id(conn, spillover_id)
        if row is None:
            return render_template("404.html"), 404
        notes = database.list_notes(conn, "spillover", str(spillover_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "spillover_detail.html", row=row,
        notes=notes, attachments_by_note=attachments_by_note,
        note_added=note_added, note_saved=note_saved, note_deleted=note_deleted,
    )


@app.route("/spillover/report")
def spillover_report_select():
    area        = request.args.getlist("area")
    type_       = request.args.getlist("type")
    status      = request.args.getlist("status")
    assigned_to = request.args.getlist("assigned_to")
    critical    = request.args.getlist("critical")
    show_all    = request.args.get("show_all") == "1"
    hidden      = _cfg.get("spillover_hidden_statuses", [])
    exclude     = [] if (show_all or status) else hidden
    conn = _get_conn()
    try:
        rows            = database.get_spillover(conn, statuses=status or None, areas=area or None,
                              types=type_ or None, assignees=assigned_to or None,
                              critical=critical or None, exclude_statuses=exclude or None)
        options         = database.get_spillover_filter_options(conn)
        selected_ids    = database.get_spillover_report_ids(conn)
        report_comments = database.list_report_comments(conn, "spillover")
    finally:
        conn.close()
    return render_template(
        "spillover_report_select.html",
        rows=rows, options=options, selected_ids=selected_ids,
        area=area, type_=type_, status=status, assigned_to=assigned_to,
        critical=critical, show_all=show_all,
        report_comments=report_comments,
    )


@app.route("/spillover/<int:spillover_id>/report-toggle", methods=["POST"])
def spillover_report_toggle(spillover_id: int):
    conn = _get_conn()
    try:
        included = database.toggle_spillover_report_item(conn, spillover_id)
        total    = len(database.get_spillover_report_ids(conn))
    finally:
        conn.close()
    return jsonify({"ok": True, "included": included, "total": total})


@app.route("/spillover/report/include-ids", methods=["POST"])
def spillover_report_include_ids():
    ids  = [int(i) for i in request.form.getlist("ids") if i.isdigit()]
    conn = _get_conn()
    try:
        database.include_spillover_report_ids(conn, ids)
        total = len(database.get_spillover_report_ids(conn))
    finally:
        conn.close()
    return jsonify({"ok": True, "total": total})


@app.route("/spillover/report/clear", methods=["POST"])
def spillover_report_clear():
    conn = _get_conn()
    try:
        database.clear_spillover_report(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "total": 0})


@app.route("/spillover/report/view")
def spillover_report_view():
    conn = _get_conn()
    try:
        items           = database.get_spillover_report_items(conn)
        order_details   = {}
        for item in items:
            od = database.list_order_details(conn, "spillover", str(item["spillover_id"]))
            if od:
                order_details[item["spillover_id"]] = od
        report_comments = database.list_report_comments(conn, "spillover")
    finally:
        conn.close()
    _crit_order = {"yes": 0, "slightly": 1, "no": 2}
    items = sorted(items, key=lambda r: _crit_order.get(r.get("critical_for_signoff") or "", 3))
    from datetime import date
    return render_template(
        "spillover_report_view.html",
        items=items, order_details=order_details,
        report_comments=report_comments,
        today=date.today().strftime("%Y-%m-%d"),
    )


@app.route("/spillover/report/table")
def spillover_report_table():
    """Compact TABLE variant of the status report [USER 2026-07-10] —
    ADDITIONAL to the detailed card view, not a replacement: grouped by
    with_whom (Sales → MB → Unassigned), inline comments, call-outs box."""
    conn = _get_conn()
    try:
        items           = database.get_spillover_report_items(conn)
        order_details   = {}
        for item in items:
            od = database.list_order_details(conn, "spillover", str(item["spillover_id"]))
            if od:
                order_details[item["spillover_id"]] = od
        report_comments = database.list_report_comments(conn, "spillover")
    finally:
        conn.close()
    _crit_order = {"yes": 0, "slightly": 1, "no": 2}
    items = sorted(items, key=lambda r: _crit_order.get(r.get("critical_for_signoff") or "", 3))
    from datetime import date
    return render_template(
        "spillover_report_table.html",
        items=items, order_details=order_details,
        report_comments=report_comments,
        today=date.today().strftime("%Y-%m-%d"),
    )


@app.route("/spillover/report/ppt")
def spillover_report_ppt():
    conn = _get_conn()
    try:
        items         = database.get_spillover_report_items(conn)
        order_details = {}
        for item in items:
            od = database.list_order_details(conn, "spillover", str(item["spillover_id"]))
            if od:
                order_details[item["spillover_id"]] = od
    finally:
        conn.close()
    _crit_order = {"yes": 0, "slightly": 1, "no": 2}
    items = sorted(items, key=lambda r: _crit_order.get(r.get("critical_for_signoff") or "", 3))
    today = date.today().strftime("%Y-%m-%d")
    pptx_bytes = build_spillover_ppt(items=items, order_details=order_details, today=today)
    return pptx_bytes, 200, {
        "Content-Type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "Content-Disposition": f'attachment; filename="spillover_report_{today}.pptx"',
    }


# ---------------------------------------------------------------------------
# Generic order_details routes â€” work for any entity type


@app.route("/order-details/<entity_type>/<entity_id>")
def order_details_list(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        rows = database.list_order_details(conn, entity_type, entity_id)
    finally:
        conn.close()
    return jsonify(rows)


@app.route("/order-details/<entity_type>/<entity_id>/add", methods=["POST"])
def order_details_add(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        detail_id = database.add_order_detail(conn, entity_type, entity_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "id": detail_id})


@app.route("/order-details/<int:detail_id>/update", methods=["POST"])
def order_detail_update(detail_id: int):
    order_type   = request.form.get("order_type",   "").strip()
    order_number = request.form.get("order_number", "").strip()
    comment      = request.form.get("comment",      "").strip()
    docs_in_s4   = 1 if request.form.get("docs_in_s4") == "1" else 0
    conn = _get_conn()
    try:
        database.update_order_detail(conn, detail_id, order_type, order_number, comment, docs_in_s4)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/order-details/<int:detail_id>/delete", methods=["POST"])
def order_detail_delete(detail_id: int):
    conn = _get_conn()
    try:
        database.delete_order_detail(conn, detail_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# --- order archive (2026-07-16): selected rows -> one grouped history batch


@app.route("/order-details/<entity_type>/<entity_id>/archive", methods=["POST"])
def order_details_archive(entity_type: str, entity_id: str):
    ids = [int(i) for i in request.form.get("ids", "").split(",") if i.strip().isdigit()]
    label = request.form.get("label", "").strip()
    if not ids:
        return jsonify({"ok": False, "error": "no rows selected"})
    conn = _get_conn()
    try:
        result = database.archive_order_details(conn, entity_type, entity_id, ids, label)
    finally:
        conn.close()
    if result["count"] == 0:
        return jsonify({"ok": False, "error": "no matching rows"})
    return jsonify({"ok": True, **result})


@app.route("/order-details/<entity_type>/<entity_id>/history")
def order_details_history(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        batches = database.list_order_batches(conn, entity_type, entity_id)
    finally:
        conn.close()
    return jsonify({"batches": batches, "count": len(batches)})


@app.route("/order-details/history/batch/<int:batch_id>/delete", methods=["POST"])
def order_batch_delete(batch_id: int):
    conn = _get_conn()
    try:
        database.delete_order_batch(conn, batch_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# ECOM Gatekeeper Check

