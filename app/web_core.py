"""Flask app object + shared web-layer plumbing (refactoring step 4).

Feature route modules import `app` from here and register with @app.route —
endpoint names and URLs identical to the old monolith. This module must not
import any route module (they import us).
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template

from app import database
from app.config_loader import load_config

_HERE = Path(__file__).parent

app = Flask(
    __name__,
    template_folder=str(_HERE / "templates"),
    static_folder=str(_HERE / "static"),
)

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = _HERE.parent / "data" / "uploads"
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_ALLOWED_EXTS = _IMAGE_EXTS | {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                               ".txt", ".csv", ".msg", ".eml", ".zip", ".xml", ".json"}

# Create schema once at startup; routes use get_connection() after this.
database.init_db(_db_path).close()


def _get_conn():
    return database.get_connection(_db_path)


@app.template_filter("is_image")
def _is_image_filter(filename: str) -> bool:
    return Path(filename).suffix.lower() in _IMAGE_EXTS


def _not_found(defect_id: str):
    return render_template("404.html", defect_id=defect_id), 404
