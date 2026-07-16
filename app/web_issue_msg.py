"""Issue messages — Blueprint (2026-07-16).

Two halves:
- /message-types — the editable reference card (name · TIBCO API · IIB API
  · comment per message type; dashboard card)
- /issue-msg/... — JSON for the ✉️ builder dialog (_issue_message.html) on
  the Retail / Spillover / ECOM / Gatekeeper rows and detail pages:
  meta (types + fixed special texts), per-entity context (identifier +
  labeled order numbers), and save-as-note.

Context per entity type [USER 2026-07-16]:
- jira (gatekeeper ticket + ECOM board): SolMan ID (fallback jira key) +
  order_details at ('jira', key)
- retail: "test_case_id / country" + the imported order/S4 number fields
- spillover: item name (+ external id) + order_details + the imported
  order_numbers cell
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from app import database
from app.config_loader import load_config
from app.db import message_types as db_mt
from app.issue_messages import SPECIAL_TEXTS

bp = Blueprint("issue_msg", __name__)

_cfg = load_config()
_db_path = Path(_cfg["database_path"])

# note-able entity types the builder may save to (all three exist in the
# notes registry)
_SAVE_TYPES = {"jira", "retail", "spillover"}


def _get_conn():
    return database.get_connection(_db_path)


# ---------------------------------------------------------------------------
# management card
# ---------------------------------------------------------------------------


@bp.route("/message-types")
def message_types_page():
    conn = _get_conn()
    try:
        types = db_mt.list_message_types(conn)
    finally:
        conn.close()
    return render_template("message_types.html", types=types)


@bp.route("/message-types/add", methods=["POST"])
def message_type_add():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"})
    conn = _get_conn()
    try:
        type_id = db_mt.create_message_type(
            conn, name, request.form.get("tibco_api", "").strip(),
            request.form.get("iib_api", "").strip(),
            request.form.get("comment", "").strip())
    finally:
        conn.close()
    return jsonify({"ok": True, "id": type_id})


@bp.route("/message-types/<int:type_id>/update", methods=["POST"])
def message_type_update(type_id: int):
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"})
    conn = _get_conn()
    try:
        db_mt.update_message_type(
            conn, type_id, name, request.form.get("tibco_api", "").strip(),
            request.form.get("iib_api", "").strip(),
            request.form.get("comment", "").strip())
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/message-types/<int:type_id>/delete", methods=["POST"])
def message_type_delete(type_id: int):
    conn = _get_conn()
    try:
        db_mt.delete_message_type(conn, type_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# builder dialog JSON
# ---------------------------------------------------------------------------


@bp.route("/issue-msg/meta.json")
def issue_msg_meta():
    conn = _get_conn()
    try:
        types = db_mt.list_message_types(conn)
    finally:
        conn.close()
    return jsonify({
        "types": [{"id": t["id"], "name": t["name"], "tibco_api": t["tibco_api"],
                   "iib_api": t["iib_api"], "comment": t["comment"]}
                  for t in types],
        "templates": SPECIAL_TEXTS,
    })


def _labeled(label: str, value) -> dict | None:
    value = (value or "").strip() if isinstance(value, str) else value
    return {"label": label, "number": str(value)} if value else None


def _entity_context(conn, entity_type: str, entity_id: str) -> dict | None:
    if entity_type == "jira":
        issue = database.get_jira_issue(conn, entity_id)
        ident = ((issue or {}).get("solman_id") or "").strip() or entity_id
        orders = [{"label": r["order_type"] or "Order", "number": r["order_number"]}
                  for r in database.list_order_details(conn, "jira", entity_id)
                  if (r["order_number"] or "").strip()]
        return {"ident": ident, "orders": orders}
    if entity_type == "retail":
        row = database.get_retail_by_id(conn, int(entity_id))
        if row is None:
            return None
        orders = [o for o in (
            _labeled("Order", row.get("order_number")),
            _labeled("S4 sales order", row.get("s4_sales_order")),
            _labeled("S4 billing", row.get("s4_billing_documents")),
            _labeled("S4 journal/invoice", row.get("s4_journal_invoice_entry")),
            _labeled("Delivery note", row.get("delivery_note")),
        ) if o]
        return {"ident": f"{row['test_case_id']} / {row['country']}", "orders": orders}
    if entity_type == "spillover":
        row = database.get_spillover_by_id(conn, int(entity_id))
        if row is None:
            return None
        ident = (row.get("name") or f"Spillover #{entity_id}").strip()
        if (row.get("external_id") or "").strip():
            ident += f" ({row['external_id'].strip()})"
        orders = [{"label": r["order_type"] or "Order", "number": r["order_number"]}
                  for r in database.list_order_details(conn, "spillover", entity_id)
                  if (r["order_number"] or "").strip()]
        imported = _labeled("Imported orders", row.get("order_numbers"))
        if imported:
            orders.append(imported)
        return {"ident": ident, "orders": orders}
    return None


@bp.route("/issue-msg/context/<entity_type>/<entity_id>")
def issue_msg_context(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        ctx = _entity_context(conn, entity_type, entity_id)
    finally:
        conn.close()
    if ctx is None:
        return jsonify({"ok": False, "error": "unknown entity"}), 404
    return jsonify({"ok": True, **ctx})


@bp.route("/issue-msg/<entity_type>/<entity_id>/save-note", methods=["POST"])
def issue_msg_save_note(entity_type: str, entity_id: str):
    if entity_type not in _SAVE_TYPES:
        return jsonify({"ok": False, "error": "unknown entity type"}), 404
    heading = request.form.get("heading", "").strip() or "Issue message"
    text = request.form.get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "empty message"})
    conn = _get_conn()
    try:
        database.add_note(conn, entity_type, entity_id, heading, text,
                          source="issue-msg")
    finally:
        conn.close()
    return jsonify({"ok": True})
