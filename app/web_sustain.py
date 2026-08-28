"""Core South Sustainphase Monitoring — routes (Flask Blueprint, build
plan step 3, 2026-08-27). File-picker upload of the daily GBS Operations
checklist workbook (`…DTC_GBS Operations_checklist.xlsx`, prefix varies —
matched on the name containing 'DTC_GBS Operations_checklist' so browser
'(1)' double-download copies still work); import via
app.sustain_importer.run_sustain_import. No SQL here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import sustain as db_sustain
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
    conn = _get_conn()
    try:
        tabs = db_sustain.list_tabs(conn)
    finally:
        conn.close()
    return render_template(
        "sustain.html",
        tabs=tabs,
        sustain_ok=request.args.get("sustain_ok"),
        sustain_msg=request.args.get("sustain_msg"),
    )


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
