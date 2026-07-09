"""Email reports — Blueprint (/email-report).

Send the selected status reports (HTML attachments) to DB-managed recipients
via GMX SMTP. Credentials come from settings.local.yaml (gitignored) — the
page shows a clear warning when they are missing.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Blueprint, redirect, render_template, request, url_for

from app import database, emailer
from app.config_loader import load_config
from app.db import email as db_email

bp = Blueprint("email_report", __name__, url_prefix="/email-report")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def email_page():
    conn = _get_conn()
    try:
        recipients = db_email.list_recipients(conn)
        mailing_lists = db_email.list_email_lists(conn)
    finally:
        conn.close()
    texts = emailer.default_texts()
    return render_template(
        "email_report.html",
        recipients=recipients, mailing_lists=mailing_lists,
        report_choices=emailer.REPORT_CHOICES,
        configured=emailer.smtp_settings(_cfg) is not None,
        sender=_cfg.get("email_user", ""),
        today=texts["date"], subject=texts["subject"], body=texts["body"],
        result=request.args.get("result"), error=request.args.get("error"),
    )


@bp.route("/recipients/add", methods=["POST"])
def recipient_add():
    email = request.form.get("email", "").strip()
    if email and "@" in email:
        conn = _get_conn()
        try:
            db_email.add_recipient(conn, email, request.form.get("name", ""))
        finally:
            conn.close()
    return redirect(url_for("email_report.email_page"))


@bp.route("/recipients/<int:rid>/toggle", methods=["POST"])
def recipient_toggle(rid: int):
    conn = _get_conn()
    try:
        current = next((r for r in db_email.list_recipients(conn) if r["id"] == rid), None)
        if current:
            db_email.set_recipient_active(conn, rid, not current["active"])
    finally:
        conn.close()
    return redirect(url_for("email_report.email_page"))


@bp.route("/recipients/<int:rid>/delete", methods=["POST"])
def recipient_delete(rid: int):
    conn = _get_conn()
    try:
        db_email.delete_recipient(conn, rid)
    finally:
        conn.close()
    return redirect(url_for("email_report.email_page"))


@bp.route("/lists/save", methods=["POST"])
def list_save():
    """Save the CURRENT selection as a mailing list (same name = replace)."""
    name = request.form.get("list_name", "").strip()
    ids = [int(x) for x in request.form.getlist("recipients")]
    if not name:
        return redirect(url_for("email_report.email_page",
                                error="Give the mailing list a name."))
    if not ids:
        return redirect(url_for("email_report.email_page",
                                error="Tick at least one recipient to save as a list."))
    conn = _get_conn()
    try:
        db_email.save_email_list(conn, name, ids)
    finally:
        conn.close()
    return redirect(url_for("email_report.email_page",
                            result=f'Mailing list "{name}" saved ({len(ids)} member(s)).'))


@bp.route("/lists/<int:list_id>/delete", methods=["POST"])
def list_delete(list_id: int):
    conn = _get_conn()
    try:
        db_email.delete_email_list(conn, list_id)
    finally:
        conn.close()
    return redirect(url_for("email_report.email_page"))


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
    return redirect(url_for("email_report.email_page",
                            result=f"Sent {len(attachments)} report(s) to {len(recipients)} recipient(s)."))
