"""Local web UI — run with:  python -m app.web

Opens http://127.0.0.1:5000 in the browser automatically.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

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


def _get_conn():
    return database.init_db(Path(_cfg["database_path"]))


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
    defects = database.list_defects(
        conn,
        search=search or None,
        channel=channel or None,
        status=status or None,
        action_needed=action_needed or None,
    )
    options = database.get_filter_options(conn)
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
    defect = database.get_defect(conn, defect_id)
    if defect is None:
        conn.close()
        return render_template("404.html", defect_id=defect_id), 404

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
        conn.close()
        return redirect(url_for("defect_detail", defect_id=defect_id, saved="1"))

    notes = database.list_notes_for_defect(conn, defect_id)
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
# Note routes
# ---------------------------------------------------------------------------

@app.route("/defects/<defect_id>/notes/add")
def note_add_form(defect_id: str):
    conn = _get_conn()
    defect = database.get_defect(conn, defect_id)
    conn.close()
    if defect is None:
        return render_template("404.html", defect_id=defect_id), 404
    return_to = request.args.get("return_to", "detail")
    return render_template("note_add.html", defect=defect, return_to=return_to)


@app.route("/defects/<defect_id>/notes", methods=["POST"])
def note_add(defect_id: str):
    conn = _get_conn()
    defect = database.get_defect(conn, defect_id)
    if defect is None:
        conn.close()
        return render_template("404.html", defect_id=defect_id), 404
    heading = request.form.get("heading", "").strip() or None
    note_text = request.form.get("note", "").strip() or None
    return_to = request.form.get("return_to", "detail")
    if not note_text:
        conn.close()
        return render_template("note_add.html", defect=defect, return_to=return_to,
                               heading=heading or "", error="Note text is required.")
    database.add_note(conn, defect_id, heading, note_text)
    conn.close()
    if return_to == "list":
        return redirect(url_for("defects_list", note_added="1"))
    return redirect(url_for("defect_detail", defect_id=defect_id, note_added="1"))


@app.route("/defects/<defect_id>/notes/<int:note_id>/edit", methods=["GET", "POST"])
def note_edit(defect_id: str, note_id: int):
    conn = _get_conn()
    note = database.get_note(conn, note_id)
    if note is None or note["defect_id"] != defect_id:
        conn.close()
        return render_template("404.html", defect_id=defect_id), 404
    if request.method == "POST":
        heading = request.form.get("heading", "").strip() or None
        note_text = request.form.get("note", "").strip() or None
        database.update_note(conn, note_id, heading, note_text)
        conn.close()
        return redirect(url_for("defect_detail", defect_id=defect_id, note_saved="1"))
    conn.close()
    return render_template("note_edit.html", defect_id=defect_id, note=note)


@app.route("/defects/<defect_id>/notes/<int:note_id>/delete", methods=["GET", "POST"])
def note_delete(defect_id: str, note_id: int):
    conn = _get_conn()
    note = database.get_note(conn, note_id)
    if note is None or note["defect_id"] != defect_id:
        conn.close()
        return render_template("404.html", defect_id=defect_id), 404
    if request.method == "POST":
        database.delete_note(conn, note_id)
        conn.close()
        return redirect(url_for("defect_detail", defect_id=defect_id, note_deleted="1"))
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
