"""Teams chats & channels — Blueprint (/teams-chats).

Management page (the ONE place to add/edit/delete chats and channels
[USER 2026-07-16]) + JSON APIs for the floating 💬 widget (pinned only) and
the drop-in per-ticket component _teams_chat_links.html.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from app import database
from app.config_loader import load_config
from app.db import teams_chats as db_tc

bp = Blueprint("teams_chats", __name__, url_prefix="/teams-chats")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def manage():
    conn = _get_conn()
    try:
        chats = db_tc.list_teams_chats(conn)
    finally:
        conn.close()
    return render_template("teams_chats.html", chats=chats)


@bp.route("/add", methods=["POST"])
def add():
    name = request.form.get("name", "").strip()
    link = request.form.get("link", "").strip()
    emails = request.form.get("emails", "").strip()
    if not name or not (link or emails):
        return jsonify({"ok": False,
                        "error": "Need a name and a Teams link OR member emails."})
    if link and not link.startswith("https://teams.microsoft.com/"):
        return jsonify({"ok": False,
                        "error": "The link must be copied from Teams "
                                 "(starts with https://teams.microsoft.com/)."})
    conn = _get_conn()
    try:
        chat_id = db_tc.create_teams_chat(
            conn, name, request.form.get("kind", "chat"), link, emails,
            request.form.get("description", "").strip(),
            1 if request.form.get("pinned") == "1" else 0)
        chat = db_tc.get_teams_chat(conn, chat_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "chat": chat})


@bp.route("/<int:chat_id>/update", methods=["POST"])
def update(chat_id: int):
    name = request.form.get("name", "").strip()
    link = request.form.get("link", "").strip()
    emails = request.form.get("emails", "").strip()
    if not name or not (link or emails):
        return jsonify({"ok": False,
                        "error": "Need a name and a Teams link OR member emails."})
    conn = _get_conn()
    try:
        db_tc.update_teams_chat(
            conn, chat_id, name, request.form.get("kind", "chat"), link, emails,
            request.form.get("description", "").strip(),
            1 if request.form.get("pinned") == "1" else 0)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:chat_id>/delete", methods=["POST"])
def delete(chat_id: int):
    conn = _get_conn()
    try:
        db_tc.delete_teams_chat(conn, chat_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/pinned.json")
def pinned_json():
    """Feeds the floating 💬 widget — pinned chats only [USER 2026-07-16]."""
    conn = _get_conn()
    try:
        chats = db_tc.list_teams_chats(conn, pinned_only=True)
    finally:
        conn.close()
    return jsonify([{"id": c["id"], "name": c["name"], "url": c["url"],
                     "kind": c["kind"]} for c in chats])


@bp.route("/all.json")
def all_json():
    """Search for the attach picker in _teams_chat_links.html."""
    q = request.args.get("q", "").strip()
    conn = _get_conn()
    try:
        chats = db_tc.list_teams_chats(conn, q=q)
    finally:
        conn.close()
    return jsonify([{"id": c["id"], "name": c["name"], "url": c["url"],
                     "kind": c["kind"], "pinned": c["pinned"]} for c in chats])


# --- per-ticket references (generic entity_type/entity_id address) ---------


@bp.route("/refs/<entity_type>/<entity_id>")
def refs_list(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        refs = db_tc.list_chat_refs(conn, entity_type, entity_id)
    finally:
        conn.close()
    return jsonify([{"id": r["id"], "name": r["name"], "url": r["url"],
                     "kind": r["kind"]} for r in refs])


@bp.route("/refs/<entity_type>/<entity_id>/attach", methods=["POST"])
def refs_attach(entity_type: str, entity_id: str):
    chat_id = request.form.get("chat_id", "")
    if not chat_id.isdigit():
        return jsonify({"ok": False, "error": "chat_id missing"})
    conn = _get_conn()
    try:
        ok = db_tc.attach_chat(conn, entity_type, entity_id, int(chat_id))
    finally:
        conn.close()
    return jsonify({"ok": ok} if ok else
                   {"ok": False, "error": "chat does not exist"})


@bp.route("/refs/<entity_type>/<entity_id>/detach", methods=["POST"])
def refs_detach(entity_type: str, entity_id: str):
    chat_id = request.form.get("chat_id", "")
    if chat_id.isdigit():
        conn = _get_conn()
        try:
            db_tc.detach_chat(conn, entity_type, entity_id, int(chat_id))
        finally:
            conn.close()
    return jsonify({"ok": True})
