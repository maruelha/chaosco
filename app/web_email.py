"""Email reports — Blueprint (/email-report).

Send the selected status reports (HTML attachments) to DB-managed recipients
via GMX SMTP. Credentials come from settings.local.yaml (gitignored) — the
page shows a clear warning when they are missing.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for)

from app import database, emailer
from app.config_loader import load_config
from app.db import email as db_email

bp = Blueprint("email_report", __name__, url_prefix="/email-report")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def _wants_json() -> bool:
    """The page calls these endpoints with fetch() so a recipient change never
    reloads the form and throws away the typed text and the ticked reports
    [USER 2026-08-31]. Without the header they still redirect, so the page
    keeps working with JavaScript off."""
    return request.headers.get("X-Requested-With") == "fetch"


def _reply(payload: dict, **redirect_args):
    if _wants_json():
        return jsonify({"ok": True, **payload})
    return redirect(url_for("email_report.email_page", **redirect_args))


@bp.route("/")
def email_page():
    conn = _get_conn()
    try:
        recipients = db_email.list_recipients(conn)
        mailing_lists = db_email.list_email_lists(conn)
    finally:
        conn.close()
    # ?reports=key pre-ticks just that report (e.g. from a page's own "Send
    # via email" button) [USER 2026-08-06]. With no query param the page opens
    # with NOTHING ticked [USER 2026-08-31] — all-ticked meant unticking
    # eleven boxes for a two-report mail; use a group or the All/None buttons.
    requested = request.args.getlist("reports")
    checked_reports = set(requested)
    texts = emailer.default_texts(reports=[k for k, _ in emailer.REPORT_CHOICES
                                           if k in checked_reports])
    return render_template(
        "email_report.html",
        recipients=recipients, mailing_lists=mailing_lists,
        report_labels=dict(emailer.REPORT_CHOICES),
        report_choices=emailer.REPORT_CHOICES, checked_reports=checked_reports,
        configured=emailer.smtp_settings(_cfg) is not None,
        sender=_cfg.get("email_user", ""),
        today=texts["date"], subject=texts["subject"], body=texts["body"],
        result=request.args.get("result"), error=request.args.get("error"),
    )


@bp.route("/recipients/add", methods=["POST"])
def recipient_add():
    email = request.form.get("email", "").strip()
    if not email or "@" not in email:
        if _wants_json():
            return jsonify({"ok": False, "error": "Enter a valid email address."}), 400
        return redirect(url_for("email_report.email_page"))
    conn = _get_conn()
    try:
        db_email.add_recipient(conn, email, request.form.get("name", ""))
        row = next((r for r in db_email.list_recipients(conn)
                    if r["email"].lower() == email.lower()), None)
    finally:
        conn.close()
    return _reply({"recipient": row})


@bp.route("/recipients/<int:rid>/toggle", methods=["POST"])
def recipient_toggle(rid: int):
    conn = _get_conn()
    try:
        current = next((r for r in db_email.list_recipients(conn) if r["id"] == rid), None)
        active = None
        if current:
            active = not current["active"]
            db_email.set_recipient_active(conn, rid, active)
    finally:
        conn.close()
    return _reply({"id": rid, "active": bool(active)})


@bp.route("/recipients/<int:rid>/delete", methods=["POST"])
def recipient_delete(rid: int):
    conn = _get_conn()
    try:
        db_email.delete_recipient(conn, rid)
    finally:
        conn.close()
    return _reply({"id": rid})


@bp.route("/lists/save", methods=["POST"])
def list_save():
    """Save the CURRENT send as a GROUP (same name = replace): its recipients,
    its reports AND its subject/text [USER 2026-08-31] — management and the key
    users want different packs and different wording, one click each."""
    name = request.form.get("list_name", "").strip()
    ids = [int(x) for x in request.form.getlist("recipients")]
    reports = request.form.getlist("reports")
    error = None
    if not name:
        error = "Give the group a name."
    elif not ids:
        error = "Tick at least one recipient to save as a group."
    if error:
        if _wants_json():
            return jsonify({"ok": False, "error": error}), 400
        return redirect(url_for("email_report.email_page", error=error))
    conn = _get_conn()
    try:
        list_id = db_email.save_email_list(
            conn, name, ids, report_keys=reports,
            subject=request.form.get("subject", ""),
            body=request.form.get("body", ""))
        saved = next((g for g in db_email.list_email_lists(conn)
                      if g["id"] == list_id), None)
    finally:
        conn.close()
    msg = (f'Group "{name}" saved — {len(ids)} recipient(s), '
           f'{len(reports)} report(s) and its own text.')
    return _reply({"group": saved, "result": msg}, result=msg)


@bp.route("/lists/<int:list_id>/delete", methods=["POST"])
def list_delete(list_id: int):
    conn = _get_conn()
    try:
        db_email.delete_email_list(conn, list_id)
    finally:
        conn.close()
    return _reply({"id": list_id})


@bp.route("/text", methods=["POST"])
def regenerate_text():
    """Subject + body for the reports that are ticked RIGHT NOW
    [USER 2026-08-31]. The wording has one definition (emailer.default_texts);
    the page asks for it instead of rebuilding the sentence in JavaScript."""
    day = request.form.get("date", "").strip() or None
    return jsonify({"ok": True,
                    **emailer.default_texts(day, request.form.getlist("reports"))})


@bp.route("/send", methods=["POST"])
def send():
    settings = emailer.smtp_settings(_cfg)
    if settings is None:
        return redirect(url_for("email_report.email_page",
                                error="Email is not configured — set email_user and "
                                      "email_password in config/settings.local.yaml."))

    day = request.form.get("date", "").strip() or date.today().isoformat()
    subject = request.form.get("subject", "").strip() or emailer.default_texts(day)["subject"]
    body = request.form.get("body", "").strip() or emailer.default_texts(day)["body"]
    reports = request.form.getlist("reports")
    to_ids = {int(x) for x in request.form.getlist("recipients")}

    conn = _get_conn()
    try:
        recipients = [r["email"] for r in db_email.list_recipients(conn)
                      if r["id"] in to_ids]
        if not recipients:
            return redirect(url_for("email_report.email_page",
                                    error="Pick at least one recipient."))
        if not reports:
            return redirect(url_for("email_report.email_page",
                                    error="Pick at least one report."))
        from app.web_core import app as flask_app
        attachments = emailer.gather_attachments(conn, _cfg, flask_app, reports, day)
    finally:
        conn.close()

    msg = emailer.build_message(settings["user"], recipients, subject, body, attachments)
    try:
        emailer.send_message(settings, msg)
    except Exception as exc:
        return redirect(url_for("email_report.email_page",
                                error=f"Sending failed: {exc}"))

    # Auto-save the sent bucket numbers under the email date [USER 2026-08-05]
    # — a failed snapshot must never turn a successful send into an error.
    history_note = ""
    try:
        from app.report_history_importer import snapshot_reports
        conn = _get_conn()
        try:
            saved = snapshot_reports(conn, reports, day)
        finally:
            conn.close()
        if saved:
            history_note = f" History saved for {day}: {', '.join(saved)}."
    except Exception as exc:
        history_note = f" (History NOT saved: {exc})"

    return redirect(url_for("email_report.email_page",
                            result=f"Sent {len(attachments)} report(s) to "
                                   f"{len(recipients)} recipient(s).{history_note}"))
