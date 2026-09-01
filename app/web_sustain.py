"""Core South Sustainphase Monitoring — routes (Flask Blueprint, build
plan step 3, 2026-08-27). File-picker upload of the daily GBS Operations
checklist workbook (`…DTC_GBS Operations_checklist.xlsx`, prefix varies —
matched on the name containing 'DTC_GBS Operations_checklist' so browser
'(1)' double-download copies still work); import via
app.sustain_importer.run_sustain_import. No SQL here.

The 2026-08-31 workbook version added a free-text column M
"Comments/Observations": shown as its own column in the day report and as
its own section in the management summary, but never part of a status.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import sustain as db_sustain
from app.db import sustain_callouts as db_sc
from app.sustain_importer import run_sustain_import

bp = Blueprint("sustain", __name__, url_prefix="/sustain")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = Path(__file__).parent.parent / "data" / "uploads"

_FILENAME_MARKER = "dtc_gbs operations_checklist"


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def sustain_home():
    show_closed = request.args.get("show_closed") == "1"
    conn = _get_conn()
    try:
        tabs = db_sustain.list_tabs(conn)
        callouts = db_sc.list_callouts(conn, include_closed=show_closed)
        for c in callouts:
            c["note_count"] = len(
                database.list_notes(conn, "sustain_callout", str(c["id"])))
    finally:
        conn.close()
    return render_template(
        "sustain.html",
        tabs=tabs,
        callouts=callouts,
        show_closed=show_closed,
        callout_channels=db_sc.CALLOUT_CHANNELS,
        callout_types=db_sc.CALLOUT_TYPES,
        sustain_ok=request.args.get("sustain_ok"),
        sustain_msg=request.args.get("sustain_msg"),
    )


@bp.route("/callouts/add", methods=["POST"])
def sustain_callout_add():
    topic = request.form.get("topic", "").strip()
    if not topic:
        return redirect(url_for("sustain.sustain_home"))
    conn = _get_conn()
    try:
        db_sc.create_callout(
            conn,
            channel=request.form.get("channel", ""),
            type_=request.form.get("type", ""),
            topic=topic,
            responsible=request.form.get("responsible"),
        )
    finally:
        conn.close()
    return redirect(url_for("sustain.sustain_home"))


@bp.route("/callouts/<int:callout_id>/update", methods=["POST"])
def sustain_callout_update(callout_id: int):
    topic = request.form.get("topic", "").strip()
    if not topic:
        return redirect(url_for("sustain.sustain_home"))
    conn = _get_conn()
    try:
        db_sc.update_callout(
            conn, callout_id,
            channel=request.form.get("channel", ""),
            type_=request.form.get("type", ""),
            topic=topic,
            responsible=request.form.get("responsible"),
        )
    finally:
        conn.close()
    return redirect(url_for("sustain.sustain_home"))


@bp.route("/callouts/<int:callout_id>/status", methods=["POST"])
def sustain_callout_status(callout_id: int):
    """Cycling status chip — server decides the next state
    (open -> in_progress -> closed -> open), saved immediately."""
    conn = _get_conn()
    try:
        new_status = db_sc.cycle_status(conn, callout_id)
    finally:
        conn.close()
    if new_status is None:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "status": new_status,
                    "label": db_sc.STATUS_LABELS[new_status]})


@bp.route("/callouts/<int:callout_id>/delete", methods=["POST"])
def sustain_callout_delete(callout_id: int):
    conn = _get_conn()
    try:
        db_sc.delete_callout(conn, callout_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/callouts/<int:callout_id>/next-step", methods=["POST"])
def sustain_callout_next_step(callout_id: int):
    """Save the call-out's next step (inline, onblur; ↻ archive via the
    generic /next-steps 'sustain_callout' entity)."""
    value = (request.get_json(silent=True) or {}).get("next_step", "")
    conn = _get_conn()
    try:
        db_sc.set_callout_next_step(conn, callout_id, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/day/<day>/<stream>")
def sustain_day(day, stream):
    """One (day, stream) tab mirrored in the Excel's structure: parent
    tasks expandable to their country/provider detail rows. All shown
    statuses are recomputed (storage-layer classification), never the
    workbook's cached formulas."""
    conn = _get_conn()
    try:
        tasks = db_sustain.list_tasks(conn, day, stream)
        counts = db_sustain.summary_counts(conn, day, stream)
        tabs = db_sustain.list_tabs(conn)
    finally:
        conn.close()
    for t in tasks:
        t["cells"] = db_sustain.derive_cells(t)
        t["overall_recomputed"] = db_sustain.derive_overall(
            t.get("due_today"), t["cells"])
        t["status"] = db_sustain.task_status(t)
        for d in t["details"]:
            d["entry"] = db_sustain.detail_result(d)
    day_links = [t for t in tabs if t["stream"] == stream]
    other_streams = sorted({t["stream"] for t in tabs
                            if t["day"] == day and t["stream"] != stream})
    return render_template(
        "sustain_day.html", day=day, stream=stream, tasks=tasks,
        counts=counts, day_links=day_links, other_streams=other_streams)


@bp.route("/summary")
@bp.route("/summary/<day>")
def sustain_summary(day=None):
    """Management summary (build plan step 5, v1 layout — to be reviewed
    with Marina): headline per stream for one day, the Attention list
    (verbatim issue notes = the discussion agenda), day-over-day trend
    and repeat offenders."""
    conn = _get_conn()
    try:
        ov = db_sustain.overview(conn)
        days = sorted({o["day"] for o in ov})
        if day is None and days:
            day = days[-1]   # default: latest imported day
        streams = []
        for o in ov:
            if o["day"] == day:
                # key must not be called "items" — dict.items() shadows
                # it in Jinja attribute lookup
                streams.append({
                    "stream": o["stream"], "counts": o["counts"],
                    "attention": db_sustain.attention_items(conn, day,
                                                            o["stream"]),
                    "comments": db_sustain.comment_items(conn, day,
                                                         o["stream"]),
                })
        offenders = db_sustain.repeat_offenders(conn)
    finally:
        conn.close()
    for o in ov:
        due = o["counts"]["due"]
        o["completion"] = round(100 * o["counts"]["completed"] / due) \
            if due else None
    return render_template(
        "sustain_summary.html", day=day, days=days, streams=streams,
        overview=ov, offenders=offenders)


@bp.route("/upload", methods=["POST"])
def sustain_upload():
    """A dated copy is kept in data/uploads (traceability; mirrored by the
    backup), then imported — same pattern as the Smoke upload."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return redirect(url_for("sustain.sustain_home", sustain_ok="0",
                                sustain_msg="No file selected."))
    name = f.filename.lower()
    if not name.endswith(".xlsx"):
        return redirect(url_for("sustain.sustain_home", sustain_ok="0",
                                sustain_msg="That is not an .xlsx file — pick"
                                            " the GBS Operations checklist"
                                            " workbook."))
    if _FILENAME_MARKER not in name:
        return redirect(url_for(
            "sustain.sustain_home", sustain_ok="0",
            sustain_msg="That doesn't look like the GBS Operations checklist"
                        " — expected a filename ending in"
                        " 'DTC_GBS Operations_checklist.xlsx'."))
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = _UPLOAD_FOLDER / f"sustain_{stamp}.xlsx"
    f.save(str(xlsx_path))
    result = run_sustain_import(_cfg, xlsx_path)
    if result["ok"]:
        msg = (f"{f.filename}: {result['tabs']} day tabs ·"
               f" {result['tasks']} tasks · {result['details']} detail rows"
               f" imported")
        return redirect(url_for("sustain.sustain_home", sustain_ok="1",
                                sustain_msg=msg))
    return redirect(url_for("sustain.sustain_home", sustain_ok="0",
                            sustain_msg=result["error"]))
