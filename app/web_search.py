"""Global search — Blueprint (/search) behind the floating 🔍 widget.

v1: order numbers (see app/db/search.py — source registry; new sources are
one block there + one URL mapping here). The widget lives in base.html so
the search hovers over every page, board included.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request, url_for

from app import database
from app.config_loader import load_config
from app.db import search as db_search

bp = Blueprint("search", __name__, url_prefix="/search")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def _url_for_hit(hit_type: str, hit_id) -> str | None:
    try:
        if hit_type == "spillover":
            return url_for("spillover_detail", spillover_id=hit_id)
        if hit_type == "ecom_gatekeeper":
            return url_for("ecom_gatekeeper_detail", row_id=hit_id)
        if hit_type == "ecom":
            return url_for("ecom.ecom_detail", ecom_id=hit_id)
        if hit_type == "retail":
            return url_for("retail_detail", retail_id=hit_id)
        if hit_type == "defect":
            return url_for("defect_detail", defect_id=hit_id)
    except Exception:
        return None
    return None


@bp.route("/orders.json")
def orders_json():
    q = request.args.get("q", "").strip()
    if len(q) < 3:
        return jsonify({"ok": False, "error": "type at least 3 characters"})
    conn = _get_conn()
    try:
        groups = db_search.search_order_number(conn, q)
    finally:
        conn.close()
    out = []
    for g in groups:
        hits = []
        for h in g["hits"]:
            url = _url_for_hit(h["type"], h["id"])
            if url:
                hits.append({"label": h["label"], "match": h["match"], "url": url})
        if hits:
            out.append({"group": g["group"], "hits": hits})
    return jsonify({"ok": True, "q": q, "groups": out})
