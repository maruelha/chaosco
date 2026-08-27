"""CORE SOUTH Smoke Testing — routes (Flask Blueprint, build plan step 3,
2026-08-27). File-picker upload of the EU CS Smoke Test execution workbook
(no folder config, like the Delegated upload); import via
app.smoke_importer.run_smoke_import. No SQL here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, redirect, render_template, request, url_for

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


@bp.route("/ecom")
def smoke_ecom():
    conn = _get_conn()
    try:
        all_ecom = db_smoke.list_scenarios(conn, "eCOM")
    finally:
        conn.close()
    omni = [s for s in all_ecom if db_smoke.is_omni_package(s.get("package"))]
    ecom = [s for s in all_ecom if not db_smoke.is_omni_package(s.get("package"))]
    return render_template("smoke_ecom.html", omni=omni, ecom=ecom)


@bp.route("/retail")
def smoke_retail():
    conn = _get_conn()
    try:
        retail = db_smoke.list_scenarios(conn, "Retail")
    finally:
        conn.close()
    return render_template("smoke_retail.html", retail=retail)


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
