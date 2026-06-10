"""Local web UI — run with:  python -m app.web

Opens http://127.0.0.1:5000 in the browser automatically.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.importer import run_import

_HERE = Path(__file__).parent

app = Flask(
    __name__,
    template_folder=str(_HERE / "templates"),
    static_folder=str(_HERE / "static"),
)

_cfg = load_config()
_db_path = Path(_cfg["database_path"])

# Create schema once at startup; routes use get_connection() after this.
database.init_db(_db_path).close()


def _get_conn():
    return database.get_connection(_db_path)


def _not_found(defect_id: str):
    return render_template("404.html", defect_id=defect_id), 404


def _render_note_add_form(defect_id, solman_name, return_to, *, heading="", error=None):
    return render_template(
        "note_form.html", mode="add", defect_id=defect_id,
        solman_name=solman_name, return_to=return_to,
        action_url=url_for("note_add", defect_id=defect_id),
        cancel_url=(url_for("defects_list") if return_to == "list"
                    else url_for("defect_detail", defect_id=defect_id)),
        heading=heading, error=error,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/import", methods=["POST"])
def do_import():
    result = run_import(_cfg)
    return render_template("import_result.html", r=result)


@app.route("/defects")
def defects_list():
    search = request.args.get("search", "").strip()
    channel = request.args.get("channel", "")
    status = request.args.get("status", "")
    action_needed = request.args.get("action_needed", "no")
    note_added = request.args.get("note_added") == "1"

    conn = _get_conn()
    try:
        defects = database.list_defects(
            conn,
            search=search or None,
            channel=channel or None,
            status=status or None,
            action_needed=action_needed or None,
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
        status=status,
        action_needed=action_needed,
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
            )
            return redirect(url_for("defect_detail", defect_id=defect_id, saved="1"))

        notes = database.list_notes_for_defect(conn, defect_id)
    finally:
        conn.close()

    saved = request.args.get("saved") == "1"
    note_added = request.args.get("note_added") == "1"
    note_saved = request.args.get("note_saved") == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    return render_template(
        "defect_detail.html",
        defect=defect,
        saved=saved,
        notes=notes,
        note_added=note_added,
        note_saved=note_saved,
        note_deleted=note_deleted,
    )


# ---------------------------------------------------------------------------
# Spillover routes
# ---------------------------------------------------------------------------

@app.route("/spillover")
def spillover_list():
    area        = request.args.getlist("area")
    type_       = request.args.getlist("type")
    status      = request.args.getlist("status")
    assigned_to = request.args.getlist("assigned_to")
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
            exclude_statuses=exclude or None,
        )
        options = database.get_spillover_filter_options(conn)
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
        show_all=show_all,
        hidden_statuses=hidden,
    )


@app.route("/spillover/<int:spillover_id>/annotation", methods=["POST"])
def spillover_annotation_save(spillover_id: int):
    importance        = request.form.get("importance_for_signoff", "").strip() or None
    next_step         = request.form.get("next_step", "").strip() or None
    comment_for_signoff = request.form.get("comment_for_signoff", "").strip() or None
    conn = _get_conn()
    try:
        existing        = database.get_spillover_annotation(conn, spillover_id)
        comment_history = existing["comment_history"] if existing else None
        critical        = existing["critical_for_signoff"] if existing else None
        database.upsert_spillover_annotation(
            conn, spillover_id, importance, next_step, comment_history, critical, comment_for_signoff)
        ann = database.get_spillover_annotation(conn, spillover_id)
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "importance_for_signoff": ann["importance_for_signoff"] or "",
        "next_step":              ann["next_step"] or "",
        "comment_for_signoff":    ann["comment_for_signoff"] or "",
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
        database.upsert_spillover_annotation(
            conn, spillover_id, importance, next_step, comment_history, critical, comment_for_signoff)
        ann = database.get_spillover_annotation(conn, spillover_id)
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "comment_history": ann["comment_history"] or "",
    })


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
        database.upsert_spillover_annotation(
            conn, spillover_id, importance, next_step, comment_history, critical, comment_for_signoff)
        ann = database.get_spillover_annotation(conn, spillover_id)
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "critical_for_signoff": ann["critical_for_signoff"] or "",
    })


# ---------------------------------------------------------------------------
# Signoff reports
# ---------------------------------------------------------------------------

def _sort_for_report(rows: list) -> list:
    def key(r):
        imp = r.get("importance_for_signoff") or ""
        return (0 if imp else 1, imp.lower(), (r.get("name") or "").lower())
    return sorted(rows, key=key)


@app.route("/report/retail")
def retail_report():
    hidden = _cfg.get("spillover_hidden_statuses", [])
    conn = _get_conn()
    try:
        rows = database.get_spillover(conn, exclude_statuses=hidden or None)
    finally:
        conn.close()
    return render_template("report.html",
        title="Retail Spillover Report",
        report_date=date.today().isoformat(),
        rows=_sort_for_report(rows))


@app.route("/report/ecom")
def ecom_report():
    hidden = _cfg.get("spillover_hidden_statuses", [])
    ecom_areas = {"ecom", "omni"}
    conn = _get_conn()
    try:
        rows = database.get_spillover(conn, exclude_statuses=hidden or None)
    finally:
        conn.close()
    rows = [r for r in rows if (r.get("area") or "").lower() in ecom_areas]
    return render_template("report.html",
        title="ECOM / Omni Spillover Report",
        report_date=date.today().isoformat(),
        rows=_sort_for_report(rows))


# ---------------------------------------------------------------------------
# Note routes
# ---------------------------------------------------------------------------

@app.route("/defects/<defect_id>/notes/add")
def note_add_form(defect_id: str):
    conn = _get_conn()
    try:
        defect = database.get_defect(conn, defect_id)
    finally:
        conn.close()
    if defect is None:
        return _not_found(defect_id)
    return_to = request.args.get("return_to", "detail")
    return _render_note_add_form(defect_id, defect.get("solman_name"), return_to)


@app.route("/defects/<defect_id>/notes", methods=["POST"])
def note_add(defect_id: str):
    conn = _get_conn()
    try:
        defect = database.get_defect(conn, defect_id)
        if defect is None:
            return _not_found(defect_id)
        heading = request.form.get("heading", "").strip() or None
        note_text = request.form.get("note", "").strip() or None
        return_to = request.form.get("return_to", "detail")
        if not note_text:
            return _render_note_add_form(
                defect_id, defect.get("solman_name"), return_to,
                heading=heading or "", error="Note text is required.",
            )
        database.add_note(conn, defect_id, heading, note_text)
    finally:
        conn.close()
    if return_to == "list":
        return redirect(url_for("defects_list", note_added="1"))
    return redirect(url_for("defect_detail", defect_id=defect_id, note_added="1"))


@app.route("/defects/<defect_id>/notes/<int:note_id>/edit", methods=["GET", "POST"])
def note_edit(defect_id: str, note_id: int):
    conn = _get_conn()
    try:
        note = database.get_note(conn, note_id)
        if note is None or note["defect_id"] != defect_id:
            return _not_found(defect_id)
        defect = database.get_defect(conn, defect_id)
        if request.method == "POST":
            heading = request.form.get("heading", "").strip() or None
            note_text = request.form.get("note", "").strip() or None
            if note_text:
                database.update_note(conn, note_id, heading, note_text)
                return redirect(url_for("defect_detail", defect_id=defect_id, note_saved="1"))
    finally:
        conn.close()
    solman_name = defect.get("solman_name") if defect else None
    if request.method == "POST":
        return render_template(
            "note_form.html", mode="edit", defect_id=defect_id,
            solman_name=solman_name,
            action_url=url_for("note_edit", defect_id=defect_id, note_id=note_id),
            cancel_url=url_for("defect_detail", defect_id=defect_id),
            heading=heading or "", note_text="",
            created_at=note["created_at"],
            error="Note text is required.",
        )
    return render_template(
        "note_form.html", mode="edit", defect_id=defect_id,
        solman_name=solman_name,
        action_url=url_for("note_edit", defect_id=defect_id, note_id=note_id),
        cancel_url=url_for("defect_detail", defect_id=defect_id),
        heading=note["heading"] or "", note_text=note["note"] or "",
        created_at=note["created_at"],
    )


@app.route("/defects/<defect_id>/notes/<int:note_id>/delete", methods=["GET", "POST"])
def note_delete(defect_id: str, note_id: int):
    conn = _get_conn()
    try:
        note = database.get_note(conn, note_id)
        if note is None or note["defect_id"] != defect_id:
            return _not_found(defect_id)
        if request.method == "POST":
            database.delete_note(conn, note_id)
            return redirect(url_for("defect_detail", defect_id=defect_id, note_deleted="1"))
    finally:
        conn.close()
    return render_template("note_confirm_delete.html", defect_id=defect_id, note=note)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import threading
    import webbrowser

    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, host="127.0.0.1", port=5000)
