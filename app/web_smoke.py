"""CORE SOUTH Smoke Testing — routes (Flask Blueprint, build plan step 3,
2026-08-27). File-picker upload of the EU CS Smoke Test execution workbook
(no folder config, like the Delegated upload); import via
app.smoke_importer.run_smoke_import. No SQL here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for)

from app import database
from app.config_loader import load_config
from app.db import smoke as db_smoke
from app.smoke_importer import run_smoke_import

bp = Blueprint("smoke", __name__, url_prefix="/smoke")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = Path(__file__).parent.parent / "data" / "uploads"


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def smoke_home():
    conn = _get_conn()
    try:
        counts = db_smoke.overview_counts(conn)
    finally:
        conn.close()
    total_scenarios = sum(g["total"] for g in counts.values())
    return render_template(
        "smoke.html",
        counts=counts,
        total_scenarios=total_scenarios,
        ecom_url=url_for("smoke.smoke_ecom"),
        retail_url=url_for("smoke.smoke_retail"),
        smoke_ok=request.args.get("smoke_ok"),
        smoke_msg=request.args.get("smoke_msg"),
    )


def _attach_annotations(scenarios: list[dict], annotations: dict) -> None:
    """Merge Marina's authored comment/next step onto the scenario dicts
    (key user_comment — 'comment' is taken by the imported Excel column)."""
    for s in scenarios:
        ann = annotations.get(s.get("row_id")) or {}
        s["user_comment"] = ann.get("comment")
        s["next_step"] = ann.get("next_step")
        s["kt_done"] = ann.get("kt_done") or False
        s["kt_date"] = ann.get("kt_date")


@bp.route("/ecom")
def smoke_ecom():
    conn = _get_conn()
    try:
        all_ecom = db_smoke.list_scenarios(conn, "eCOM")
        annotations = db_smoke.get_smoke_annotations(conn)
    finally:
        conn.close()
    _attach_annotations(all_ecom, annotations)
    omni = [s for s in all_ecom if db_smoke.is_omni_package(s.get("package"))]
    ecom = [s for s in all_ecom if not db_smoke.is_omni_package(s.get("package"))]
    return render_template("smoke_ecom.html", omni=omni, ecom=ecom)


@bp.route("/retail")
def smoke_retail():
    conn = _get_conn()
    try:
        retail = db_smoke.list_scenarios(conn, "Retail")
        annotations = db_smoke.get_smoke_annotations(conn)
    finally:
        conn.close()
    _attach_annotations(retail, annotations)
    return render_template("smoke_retail.html", retail=retail)


@bp.route("/scenario/<int:row_id>/comment", methods=["POST"])
def smoke_comment(row_id: int):
    """Save Marina's scenario comment (inline, onblur — delegated-board
    pattern). Keyed by Excel RowID, survives re-imports."""
    value = (request.get_json(silent=True) or {}).get("comment", "")
    conn = _get_conn()
    try:
        db_smoke.set_smoke_comment(conn, row_id, value.strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/scenario/<int:row_id>/kt", methods=["POST"])
def smoke_kt(row_id: int):
    """Save the scenario's KT (knowledge transfer) checkbox + date."""
    data = request.get_json(silent=True) or {}
    conn = _get_conn()
    try:
        db_smoke.set_smoke_kt(conn, row_id, bool(data.get("kt_done")),
                              data.get("kt_date"))
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/scenario/<int:row_id>/next-step", methods=["POST"])
def smoke_next_step(row_id: int):
    """Save the scenario's next step (inline; ↻ archive runs via the
    generic /next-steps 'smoke' entity)."""
    value = (request.get_json(silent=True) or {}).get("next_step", "")
    conn = _get_conn()
    try:
        db_smoke.set_smoke_next_step(conn, row_id, value.strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/upload", methods=["POST"])
def smoke_upload():
    """A dated copy is kept in data/uploads (traceability; mirrored by the
    backup), then imported — same pattern as the Delegated upload."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return redirect(url_for("smoke.smoke_home", smoke_ok="0",
                                smoke_msg="No file selected."))
    if not f.filename.lower().endswith(".xlsx"):
        return redirect(url_for("smoke.smoke_home", smoke_ok="0",
                                smoke_msg="That is not an .xlsx file — pick the"
                                          " smoke test execution workbook."))
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = _UPLOAD_FOLDER / f"smoke_{stamp}.xlsx"
    f.save(str(xlsx_path))
    result = run_smoke_import(_cfg, xlsx_path)
    if result["ok"]:
        msg = (f"{f.filename}: {result['scenarios']} scenarios ·"
               f" {result['steps']} steps imported")
        return redirect(url_for("smoke.smoke_home", smoke_ok="1", smoke_msg=msg))
    return redirect(url_for("smoke.smoke_home", smoke_ok="0",
                            smoke_msg=result["error"]))
