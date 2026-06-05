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
    action_needed = request.args.get("action_needed", "")

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
    )


@app.route("/defects/<defect_id>")
def defect_detail(defect_id: str):
    conn = _get_conn()
    defect = database.get_defect(conn, defect_id)
    conn.close()
    if defect is None:
        return render_template("404.html", defect_id=defect_id), 404
    return render_template("defect_detail.html", defect=defect)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import threading
    import webbrowser

    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, host="127.0.0.1", port=5000)
