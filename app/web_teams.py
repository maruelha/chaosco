"""Teams ping — Blueprint (/teams-ping), registry-driven like the notes module.

Opens a pre-filled Teams chat via deep link (see app/teams_link.py). Any card
can offer a ping button by adding ONE registry entry below: how to fetch the
row, whom to ping, what the topic is, and where "back" points. The page
pre-fills the recipient from the contacts table and can save typed addresses
back to it. Nothing is sent by the app — the user reviews in Teams and
presses Enter.

Adding a ping button to a new module:
    1. add a PingEntity to REGISTRY
    2. link to url_for('teams_ping.ping', entity_type='<key>', entity_id=id)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from app import database, teams_link
from app.config_loader import load_config

bp = Blueprint("teams_ping", __name__, url_prefix="/teams-ping")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@dataclass(frozen=True)
class PingEntity:
    get_row: Callable                       # (conn, id) -> dict | None
    person: Callable[[dict], str]           # row -> whom to ping (name text)
    topic: Callable[[dict], str]            # row -> what it is about
    back_endpoint: str                      # detail/list page endpoint
    back_arg: str | None                    # kwarg name for back_endpoint (None = no arg)
    list_label: str                         # breadcrumb text


REGISTRY: dict[str, PingEntity] = {
    "followup": PingEntity(
        lambda c, i: database.get_followup_by_id(c, int(i)),
        lambda r: r["with_whom"], lambda r: r["topic"],
        "followup_detail", "followup_id", "Follow-ups",
    ),
    "cs_followup": PingEntity(
        lambda c, i: database.get_cs_followup(c, int(i)),
        lambda r: r.get("with_whom") or "", lambda r: r.get("topic") or "",
        "cs_followup_detail", "followup_id", "CS Follow-Up Tracker",
    ),
    "defect": PingEntity(
        lambda c, i: database.get_defect(c, str(i)),
        lambda r: r.get("assigned_to") or "",
        lambda r: f"defect {r['defect_id']}" + (f" — {r['solman_name']}" if r.get("solman_name") else ""),
        "defect_detail", "defect_id", "Defects",
    ),
}


def _entity_and_row(conn, entity_type: str, entity_id: str):
    ent = REGISTRY.get(entity_type)
    if ent is None:
        abort(404)
    row = ent.get_row(conn, entity_id)
    if row is None:
        abort(404)
    return ent, row


# ---------------------------------------------------------------------------
# Teams channels — saved as Links with tool = TEAMS_CHANNEL_TOOL (no parallel
# table; they also appear on /links). The picker component
# (_teams_channels.html) is fully AJAX-driven, so ANY card can include it
# without route/context changes: {% include '_teams_channels.html' %}
# ---------------------------------------------------------------------------

TEAMS_CHANNEL_TOOL = "Teams Channel"


@bp.route("/channels.json")
def channels_json():
    conn = _get_conn()
    try:
        rows = database.list_links(conn, tools=[TEAMS_CHANNEL_TOOL])
    finally:
        conn.close()
    return jsonify([{"id": r["id"], "name": r["description"], "url": r["url"]}
                    for r in rows])


@bp.route("/channels/add", methods=["POST"])
def channel_add():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    if not name or not url.startswith("https://teams.microsoft.com/"):
        return jsonify({"ok": False,
                        "error": "Need a name and a link copied from Teams "
                                 "(starts with https://teams.microsoft.com/)."})
    conn = _get_conn()
    try:
        database.create_link(conn, description=name, url=url,
                             area=None, tool=TEAMS_CHANNEL_TOOL, tags=None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/channels/<int:link_id>/delete", methods=["POST"])
def channel_delete(link_id: int):
    conn = _get_conn()
    try:
        row = database.get_link(conn, link_id)
        if row is None or row.get("tool") != TEAMS_CHANNEL_TOOL:
            return jsonify({"ok": False, "error": "not a Teams channel link"}), 404
        database.delete_link(conn, link_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<entity_type>/<entity_id>")
def ping(entity_type: str, entity_id: str):
    conn = _get_conn()
    try:
        ent, row = _entity_and_row(conn, entity_type, entity_id)
        person, topic = ent.person(row), ent.topic(row)
        email = database.find_contact_email(conn, person) or ""
        contacts = [c for c in database.list_contacts(conn) if c.get("email")]
    finally:
        conn.close()
    message = teams_link.default_message(person, topic,
                                         _cfg.get("teams_message_template"))
    back_kw = {ent.back_arg: row.get(ent.back_arg) or entity_id} if ent.back_arg else {}
    return render_template(
        "teams_ping.html",
        entity_type=entity_type, entity_id=entity_id,
        person=person, topic=topic,
        back_url=url_for(ent.back_endpoint, **back_kw), list_label=ent.list_label,
        email=email, message=message, contacts=contacts,
        contact_saved=request.args.get("contact_saved"),
    )


@bp.route("/<entity_type>/<entity_id>/save-contact", methods=["POST"])
def save_contact(entity_type: str, entity_id: str):
    if entity_type not in REGISTRY:
        abort(404)
    name = request.form.get("contact_name", "").strip()
    # group chats: save only the first address under this name
    email = request.form.get("email", "").split(",")[0].strip()
    if name and email and "@" in email:
        conn = _get_conn()
        try:
            outcome = database.upsert_contact_email(conn, name, email)
        finally:
            conn.close()
        return redirect(url_for("teams_ping.ping", entity_type=entity_type,
                                entity_id=entity_id, contact_saved=outcome))
    return redirect(url_for("teams_ping.ping", entity_type=entity_type,
                            entity_id=entity_id))
