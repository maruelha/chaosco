"""Entity connections — Blueprint (/connections) [USER 2026-07-18].

AJAX routes serving the drop-in component _connections.html (many-to-many
topic ↔ defect / retail / ecom / spillover links, detail pages only):

    {% with conn_entity_type='topic', conn_entity_id=topic.id %}
      {% include '_connections.html' %}
    {% endwith %}

The picker's search reuses GET /inbox/targets (the inbox filing search
already covers every connectable type). Storage db/entity_connections.py.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request, url_for

from app import database
from app.config_loader import load_config
from app.db import entity_connections as db_conn
from app.db.entity_connections import CONNECTABLE_TYPES

bp = Blueprint("connections", __name__, url_prefix="/connections")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])

TYPE_LABELS = {"topic": "Topic", "defect": "Defect", "retail": "Retail TC",
               "ecom": "ECOM", "spillover": "Spillover"}


def _get_conn():
    return database.get_connection(_db_path)


def _detail_url(entity_type: str, entity_id: str) -> str:
    return {
        "topic":     lambda: url_for("topics.topic_detail", topic_id=entity_id),
        "defect":    lambda: url_for("defect_detail", defect_id=entity_id),
        "retail":    lambda: url_for("retail_detail", retail_id=entity_id),
        "ecom":      lambda: url_for("ecom.ecom_detail", ecom_id=entity_id),
        "spillover": lambda: url_for("spillover_detail", spillover_id=entity_id),
    }[entity_type]()


@bp.route("/<entity_type>/<entity_id>/list.json")
def connections_json(entity_type: str, entity_id: str):
    if entity_type not in CONNECTABLE_TYPES:
        return jsonify([]), 404
    conn = _get_conn()
    try:
        items = db_conn.list_connections_for(conn, entity_type, entity_id)
        for it in items:
            it["label"] = (db_conn.resolve_label(conn, it["type"], it["entity_id"])
                           or f"(missing {it['type']} {it['entity_id']})")
            it["type_label"] = TYPE_LABELS[it["type"]]
            it["url"] = _detail_url(it["type"], it["entity_id"])
    finally:
        conn.close()
    return jsonify(items)


@bp.route("/<entity_type>/<entity_id>/add", methods=["POST"])
def connection_add(entity_type: str, entity_id: str):
    target_type = request.form.get("target_type", "").strip()
    target_id = request.form.get("target_id", "").strip()
    if entity_type not in CONNECTABLE_TYPES or target_type not in CONNECTABLE_TYPES:
        return jsonify({"ok": False, "error": "unknown entity type"}), 404
    if not target_id:
        return jsonify({"ok": False, "error": "pick a target first"})
    conn = _get_conn()
    try:
        if db_conn.resolve_label(conn, target_type, target_id) is None:
            return jsonify({"ok": False, "error": "target does not exist"})
        created = db_conn.add_connection(conn, entity_type, entity_id,
                                         target_type, target_id)
    finally:
        conn.close()
    if not created:
        return jsonify({"ok": False, "error": "already connected (or self)"})
    return jsonify({"ok": True})


@bp.route("/<int:connection_id>/delete", methods=["POST"])
def connection_delete(connection_id: int):
    conn = _get_conn()
    try:
        db_conn.delete_connection(conn, connection_id)
    finally:
        conn.close()
    return jsonify({"ok": True})
