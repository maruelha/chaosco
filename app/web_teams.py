"""Teams ping — Blueprint (/teams-ping).

Opens a pre-filled Teams chat via deep link (see app/teams_link.py). The page
shows the follow-up context, an editable recipient list (pre-filled from the
contacts table when the name matches) and an editable message; the "Open in
Teams" button hands the link to the locally installed Teams client. Nothing
is sent by the app itself — the user reviews and presses Enter in Teams.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import database, teams_link
from app.config_loader import load_config

bp = Blueprint("teams_ping", __name__, url_prefix="/teams-ping")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/followup/<int:followup_id>")
def followup_ping(followup_id: int):
    conn = _get_conn()
    try:
        row = database.get_followup_by_id(conn, followup_id)
        if row is None:
            abort(404)
        email = database.find_contact_email(conn, row["with_whom"]) or ""
        contacts = [c for c in database.list_contacts(conn) if c.get("email")]
    finally:
        conn.close()
    message = teams_link.default_message(
        row["with_whom"], row["topic"], _cfg.get("teams_message_template"))
    return render_template(
        "teams_ping.html",
        row=row, email=email, message=message, contacts=contacts,
        contact_saved=request.args.get("contact_saved"),
    )


@bp.route("/followup/<int:followup_id>/save-contact", methods=["POST"])
def save_contact(followup_id: int):
    name = request.form.get("contact_name", "").strip()
    # group chats: save only the first address under this name
    email = request.form.get("email", "").split(",")[0].strip()
    if name and email and "@" in email:
        conn = _get_conn()
        try:
            outcome = database.upsert_contact_email(conn, name, email)
        finally:
            conn.close()
        return redirect(url_for("teams_ping.followup_ping",
                                followup_id=followup_id, contact_saved=outcome))
    return redirect(url_for("teams_ping.followup_ping", followup_id=followup_id))
