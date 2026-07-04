"""Entity links — Blueprint (/elinks). Generic per-entity URL lists.

AJAX-only routes serving the drop-in component _entity_links.html:

    {% with el_entity_type='topic', el_entity_id=topic.id %}
      {% include '_entity_links.html' %}
    {% endwith %}

That include is ALL a card needs — no route or context changes.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from app import database
from app.config_loader import load_config
from app.db import entity_links as db_links

bp = Blueprint("entity_links", __name__, url_prefix="/elinks")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/<entity_type>/<entity_id>/list.json")
def links_json(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        rows = db_links.list_entity_links(conn, entity_type, entity_id)
    finally:
        conn.close()
    return jsonify([{"id": r["id"], "label": r["label"], "url": r["url"]} for r in rows])


@bp.route("/<entity_type>/<entity_id>/add", methods=["POST"])
def link_add(entity_type: str, entity_id: str):
    label = request.form.get("label", "").strip()
    url = request.form.get("url", "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return jsonify({"ok": False, "error": "The link must start with http(s)://"})
    if not label:
        label = url.split("//", 1)[1][:60]
    conn = _get_conn()
    try:
        db_links.add_entity_link(conn, entity_type, entity_id, label, url)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:link_id>/delete", methods=["POST"])
def link_delete(link_id: int):
    conn = _get_conn()
    try:
        db_links.delete_entity_link(conn, link_id)
    finally:
        conn.close()
    return jsonify({"ok": True})
