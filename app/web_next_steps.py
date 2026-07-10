"""Next-step archive — generic Blueprint (/next-steps), registry-driven like
the notes module (2026-07-10).

"New next step" [USER]: archive the CURRENT stored next step of an entity
into next_step_history and clear the live field. One registry entry per
entity type says how to READ and how to CLEAR its next-step field —
everything else (history list, archive, delete) is shared. UI is the
drop-in component _next_step_history.html.

Adding the component to a new module:
    1. add an NSEntity to REGISTRY below
    2. include '_next_step_history.html' once on the page
    3. give the buttons class js-ns-archive / js-ns-history +
       data-entity-type / data-entity-id
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from flask import Blueprint, jsonify, request

from app import database
from app.config_loader import load_config
from app.db import next_steps as db_ns

bp = Blueprint("next_steps", __name__, url_prefix="/next-steps")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@dataclass(frozen=True)
class NSEntity:
    get_current: Callable      # (conn, entity_id) -> str | None
    clear: Callable            # (conn, entity_id) -> None


def _ecom_get(conn, ecom_id):
    row = database.get_ecom_by_id(conn, int(ecom_id))
    return row["next_step"] if row else None


def _ecom_clear(conn, ecom_id):
    row = database.get_ecom_by_id(conn, int(ecom_id))
    if row:  # annotations are keyed by jira_id, the pages by ecom_id
        database.set_ecom_next_step(conn, row["jira_id"], None)


REGISTRY: dict[str, NSEntity] = {
    "spillover": NSEntity(
        lambda c, i: (database.get_spillover_annotation(c, int(i)) or {}).get("next_step"),
        lambda c, i: database.set_spillover_next_step(c, int(i), None),
    ),
    "retail": NSEntity(
        lambda c, i: (database.get_retail_annotation(c, int(i)) or {}).get("next_step"),
        lambda c, i: database.set_retail_next_step(c, int(i), None),
    ),
    "defect": NSEntity(
        lambda c, i: database.get_defect_next_step(c, str(i)),
        lambda c, i: database.set_defect_next_step(c, str(i), None),
    ),
    "ecom": NSEntity(_ecom_get, _ecom_clear),
}


@bp.route("/<entity_type>/<entity_id>/archive", methods=["POST"])
def ns_archive(entity_type: str, entity_id: str):
    ent = REGISTRY.get(entity_type)
    if ent is None:
        return jsonify({"ok": False, "error": f"unknown entity type {entity_type!r}"}), 404
    conn = _get_conn()
    try:
        current = (ent.get_current(conn, entity_id) or "").strip()
        if not current:
            return jsonify({"ok": False, "error": "the next-step field is already empty"})
        db_ns.archive_next_step(conn, entity_type, entity_id, current)
        ent.clear(conn, entity_id)
        count = len(db_ns.list_next_step_history(conn, entity_type, entity_id))
    finally:
        conn.close()
    return jsonify({"ok": True, "archived": current, "count": count})


@bp.route("/<entity_type>/<entity_id>/list.json")
def ns_list(entity_type: str, entity_id: str):
    if entity_type not in REGISTRY:
        return jsonify({"ok": False, "error": "unknown entity type"}), 404
    conn = _get_conn()
    try:
        items = db_ns.list_next_step_history(conn, entity_type, entity_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "count": len(items), "items": items})


@bp.route("/entry/<int:entry_id>/delete", methods=["POST"])
def ns_entry_delete(entry_id: int):
    conn = _get_conn()
    try:
        db_ns.delete_next_step_entry(conn, entry_id)
    finally:
        conn.close()
    return jsonify({"ok": True})
