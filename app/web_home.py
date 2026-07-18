"""Home — dashboard, import, SolMan sync, report export, uploads & attachments

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

from app import db_retail_tracker
from app.importer import run_import
from app.report_exporter import export_all_reports
from app.solman_sync import run_solman_sync

@app.route("/")
def dashboard():
    conn = _get_conn()
    try:
        inbox_count       = database.count_inbox_items(conn)
        open_enhancements = len(database.get_enhancements(conn))
        to_deliver        = database.count_encouragements_to_deliver(conn)
        shelf_count       = database.count_shelf_items(conn)
        tracker_unresolved = db_retail_tracker.requirement_counts(conn)["unresolved"]
        active_topics     = database.count_active_topics(conn)
        prod_defect_count = len(database.list_known_prod_defects(conn))
    finally:
        conn.close()
    return render_template("dashboard.html", inbox_count=inbox_count,
                           open_enhancements=open_enhancements,
                           to_deliver=to_deliver,
                           shelf_count=shelf_count,
                           tracker_unresolved=tracker_unresolved,
                           active_topics=active_topics,
                           prod_defect_count=prod_defect_count)


@app.route("/import", methods=["POST"])
def do_import():
    result = run_import(_cfg)
    return render_template("import_result.html", r=result)


@app.route("/solman-sync", methods=["POST"])
def do_solman_sync():
    result = run_solman_sync(_cfg)
    return render_template("solman_sync_result.html", r=result)


@app.route("/export-reports", methods=["POST"])
def export_reports():
    conn = _get_conn()
    try:
        saved = export_all_reports(conn, _cfg)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        conn.close()
    return jsonify({"ok": True, "files": [str(p) for p in saved]})


# ---------------------------------------------------------------------------
# Signoff reports


@app.route("/uploads/<path:filename>")
def serve_upload(filename: str):
    return send_from_directory(str(_UPLOAD_FOLDER), filename)


@app.route("/notes/<int:note_id>/attachments/add", methods=["POST"])
def attachment_add(note_id: int):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no file"})
    ext = Path(f.filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        return jsonify({"ok": False, "error": f"File type {ext!r} not allowed."})
    _UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    from datetime import datetime as _dt
    timestamp = _dt.now().strftime("%Y%m%d%H%M%S")
    filename = f"{note_id}_{timestamp}_{secure_filename(f.filename)}"
    f.save(str(_UPLOAD_FOLDER / filename))
    conn = _get_conn()
    try:
        att = database.add_attachment(conn, note_id, filename, f.filename)
    finally:
        conn.close()
    return jsonify({"ok": True, "attachment": att})


@app.route("/notes/<int:note_id>/attachments/<int:attachment_id>/delete", methods=["POST"])
def attachment_delete(note_id: int, attachment_id: int):
    conn = _get_conn()
    try:
        filename = database.delete_attachment(conn, attachment_id)
    finally:
        conn.close()
    if filename:
        fp = _UPLOAD_FOLDER / filename
        if fp.exists():
            fp.unlink()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import threading
    import webbrowser

    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8010")).start()
    app.run(debug=False, host="127.0.0.1", port=8010)

