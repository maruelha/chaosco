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
from app.web_core import _not_found

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
        # day-note count per imported tab (2026-09-02 [USER]) — one query
        day_note_counts = database.note_counts(conn, db_sustain.DAY_NOTES_ENTITY)
        for t in tabs:
            t["note_count"] = day_note_counts.get(
                db_sustain.day_key(t["day"], t["stream"]), 0)
        callouts = db_sc.list_callouts(conn, include_closed=show_closed)
        app_links_count = database.count_links_for_app(conn, "sustain")
        for c in callouts:
            c["notes"] = database.list_notes(conn, "sustain_callout", str(c["id"]))
            c["note_count"] = len(c["notes"])
        all_note_ids = [n["id"] for c in callouts for n in c["notes"]]
        attachments_by_note = database.get_attachments_for_notes(conn, all_note_ids)
    finally:
        conn.close()
    return render_template(
        "sustain.html",
        tabs=tabs,
        callouts=callouts,
        app_links_count=app_links_count,
        attachments_by_note=attachments_by_note,
        show_closed=show_closed,
        callout_channels=db_sc.CALLOUT_CHANNELS,
        callout_types=db_sc.CALLOUT_TYPES,
        sustain_ok=request.args.get("sustain_ok"),
        sustain_msg=request.args.get("sustain_msg"),
    )


@bp.route("/callouts/add", methods=["POST"])
def sustain_callout_add():
    """Quick add from the list: name (+ optional ticket no / responsible);
    topic and impact are filled on the detail page."""
    name = request.form.get("name", "").strip()
    if not name:
        return redirect(url_for("sustain.sustain_home"))
    conn = _get_conn()
    try:
        db_sc.create_callout(
            conn,
            channel=request.form.get("channel", ""),
            type_=request.form.get("type", ""),
            name=name,
            responsible=request.form.get("responsible"),
            ticket_no=request.form.get("ticket_no"),
        )
    finally:
        conn.close()
    return redirect(url_for("sustain.sustain_home"))


@bp.route("/callouts/<int:callout_id>", methods=["GET", "POST"])
def sustain_callout_detail(callout_id: int):
    """Detail page (planning chat 2026-09-02 [USER]): the list shows only
    the short name; topic, ticket no, impact and responsible are edited
    here, with the next step and the shared notes component below —
    same shape as the Blocker detail page. POST = the full-row save."""
    conn = _get_conn()
    try:
        record = db_sc.get_callout(conn, callout_id)
        if record is None:
            return _not_found(str(callout_id))
        error = None
        if request.method == "POST":
            fields = {
                "channel": request.form.get("channel", ""),
                "type_": request.form.get("type", ""),
                "name": request.form.get("name", "").strip(),
                "responsible": request.form.get("responsible"),
                "topic": request.form.get("topic"),
                "ticket_no": request.form.get("ticket_no"),
                "impact": request.form.get("impact"),
            }
            if not fields["name"]:
                error = "The name (the short line in the list) is required."
                record = {**record, **fields, "type": fields["type_"]}
            else:
                db_sc.update_callout(conn, callout_id, **fields)
                return redirect(url_for("sustain.sustain_callout_detail",
                                        callout_id=callout_id, saved="1"))
        notes = database.list_notes(conn, "sustain_callout", str(callout_id))
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "sustain_callout_detail.html", record=record, error=error,
        saved=request.args.get("saved") == "1",
        callout_channels=db_sc.CALLOUT_CHANNELS,
        callout_types=db_sc.CALLOUT_TYPES,
        notes=notes, attachments_by_note=attachments_by_note,
    )


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
        # day notes (2026-09-02 [USER]) — the shared notes component on the
        # day report, keyed "<day>|<stream>"; nothing flows into call-outs
        notes = database.list_notes(conn, db_sustain.DAY_NOTES_ENTITY,
                                    db_sustain.day_key(day, stream))
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
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
        counts=counts, day_links=day_links, other_streams=other_streams,
        day_notes_entity=db_sustain.DAY_NOTES_ENTITY,
        day_notes_key=db_sustain.day_key(day, stream),
        notes=notes, attachments_by_note=attachments_by_note)


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
                    "callouts": db_sc.list_open_for_channel(conn,
                                                            o["stream"]),
                    # day notes (2026-09-02 [USER]) — read-only bullets
                    "day_notes": database.list_notes(
                        conn, db_sustain.DAY_NOTES_ENTITY,
                        db_sustain.day_key(day, o["stream"])),
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
