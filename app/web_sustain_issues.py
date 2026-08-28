"""Sustainphase Issues — routes (Flask Blueprint, build plan step 2,
2026-08-28). File-picker upload of the `DTC_Sustainphase_Tracking….xlsx`
workbook (name-contains guard so browser "(1)" copies work); Defects tab
upserted via app.sustain_issues_importer. No SQL here.
"""
from __future__ import annotations

from datetime import datetime
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

_FILENAME_MARKER = "dtc_sustainphase_tracking"


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def sustain_issues_home():
    conn = _get_conn()
    try:
        issues = db_si.list_issues(conn)
        annotations = db_si.get_sustain_issue_annotations(conn)
    finally:
        conn.close()
    for i in issues:
        ann = annotations.get(i["issue_key"]) or {}
        i["callouts"] = ann.get("callouts")
        i["next_step"] = ann.get("next_step")
    return render_template(
        "sustain_issues.html",
        issues=issues,
        si_ok=request.args.get("si_ok"),
        si_msg=request.args.get("si_msg"),
    )


@bp.route("/upload", methods=["POST"])
def sustain_issues_upload():
    """Dated copy in data/uploads (traceability; mirrored by the backup),
    then upsert-import — same pattern as the other card uploads."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return redirect(url_for("sustain_issues.sustain_issues_home",
                                si_ok="0", si_msg="No file selected."))
    name = f.filename.lower()
    if not name.endswith(".xlsx"):
        return redirect(url_for(
            "sustain_issues.sustain_issues_home", si_ok="0",
            si_msg="That is not an .xlsx file — pick the Sustainphase"
                   " tracking workbook."))
    if _FILENAME_MARKER not in name:
        return redirect(url_for(
            "sustain_issues.sustain_issues_home", si_ok="0",
            si_msg="That doesn't look like the Sustainphase tracking"
                   " workbook — expected a filename containing"
                   " 'DTC_Sustainphase_Tracking'."))
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = _UPLOAD_FOLDER / f"sustain_issues_{stamp}.xlsx"
    f.save(str(xlsx_path))
    result = run_sustain_issues_import(_cfg, xlsx_path)
    if result["ok"]:
        msg = (f"{f.filename}: {result['rows']} rows —"
               f" {result['inserted']} new · {result['updated']} updated"
               f" · {result['promoted']} got their ASPEN id")
        return redirect(url_for("sustain_issues.sustain_issues_home",
                                si_ok="1", si_msg=msg))
    return redirect(url_for("sustain_issues.sustain_issues_home",
                            si_ok="0", si_msg=result["error"]))


@bp.route("/issue/<issue_key>/callouts", methods=["POST"])
def sustain_issue_callouts(issue_key: str):
    """Save Marina's call-outs/comment for one issue (inline, onblur)."""
    value = (request.get_json(silent=True) or {}).get("callouts", "")
    conn = _get_conn()
    try:
        db_si.set_sustain_issue_callouts(conn, issue_key, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/issue/<issue_key>/next-step", methods=["POST"])
def sustain_issue_next_step(issue_key: str):
    """Save the issue's next step (inline; ↻ archive via the generic
    /next-steps 'sustain_issue' entity)."""
    value = (request.get_json(silent=True) or {}).get("next_step", "")
    conn = _get_conn()
    try:
        db_si.set_sustain_issue_next_step(conn, issue_key, value)
    finally:
        conn.close()
    return jsonify({"ok": True})
