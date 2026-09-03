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
        if hit_type == "jira":
            return url_for("gatekeeper_ticket_detail", jira_key=hit_id)
        if hit_type == "retail":
            return url_for("retail_detail", retail_id=hit_id)
        if hit_type == "defect":
            return url_for("defect_detail", defect_id=hit_id)
        if hit_type == "sustain_incident":
            return url_for("sustain_issues.sustain_issues_home")
        if hit_type == "delegated":
            return url_for("delegated.delegated_ticket_detail",
                           jira_key=hit_id)
    except Exception:
        return None
    return None


def _note_hit_url(entity_type: str, entity_id) -> tuple[str | None, str | None]:
    """(url, where-label) for a note hit — inbox items go to the inbox,
    everything else to its entity page via the notes REGISTRY."""
    if entity_type == "input":
        try:
            return url_for("inbox"), "Inbox"
        except Exception:
            return None, None
    from app.web_notes import REGISTRY, _urls
    ent = REGISTRY.get(entity_type)
    if ent is None:
        return None, None
    try:
        return _urls(ent, entity_type, entity_id)["detail_url"], ent.list_label
    except Exception:
        return None, None


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
            if h["type"] == "note":
                url, where = _note_hit_url(h["entity_type"], h["entity_id"])
                if url:
                    hits.append({"label": f"{h['label']} · {where}",
                                 "match": h["match"], "url": url})
                continue
            if h["type"] == "smoke":
                # ws picks the page (there is no per-scenario detail page)
                try:
                    url = url_for("smoke.smoke_retail") if h.get("ws") == "Retail" \
                        else url_for("smoke.smoke_ecom")
                except Exception:
                    url = None
                if url:
                    hits.append({"label": h["label"], "match": h["match"],
                                 "url": url})
                continue
            url = _url_for_hit(h["type"], h["id"])
            if url:
                hits.append({"label": h["label"], "match": h["match"], "url": url})
        if hits:
            out.append({"group": g["group"], "hits": hits})
    return jsonify({"ok": True, "q": q, "groups": out})
