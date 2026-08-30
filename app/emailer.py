"""Email reports via GMX SMTP.

Credentials are NEVER in code or in the repo: `email_user` / `email_password`
(+ optional `email_smtp_host`, `email_smtp_port`) belong in the gitignored
`config/settings.local.yaml`. Recipients live in the DB (app.db.email).

The attachable reports (chosen per send via checkboxes):
    spillover — rendered like the Export Reports snapshot
    retail    — rendered like the Export Reports snapshot
    board     — the Requirements Board, rendered server-side and made
                standalone (CSS inlined, scripts/chrome stripped) the same
                way the board's Download HTML button does client-side
    ecom / manual_retail / manual_ecom — the live report pages rendered
                through the app and made standalone the same way
"""
from __future__ import annotations

import re
import smtplib
import sqlite3
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from flask import render_template

from app import database
from app.reporter import compute_retail_report, load_status_mappings

_HERE = Path(__file__).parent

REPORT_CHOICES = [
    ("spillover", "Spillover Status Report"),
    ("retail", "Retail Status Report"),
    ("board", "Retail Requirements Board"),
    ("ecom", "ECOM Status Report"),
    ("manual_retail", "Manual Test Cases Retail Report"),
    ("manual_ecom", "Manual Test Cases ECOM Report"),
    ("known_prod_defects", "Known Production Issues"),
    ("known_prod_defects_review", "Known Production Issues — Review Copy"),
    ("known_prod_defects_report", "Known Production Issues — Management Report"),
    ("missing_tests", "Missing Test Cases (Retail)"),
    ("delegated", "Delegated Testing Report"),
    ("delegated_numbers", "Delegated Testing — Management Summary"),
]

DEFAULT_SUBJECT = "UAT status reports — {date}"
DEFAULT_BODY = """Hi all,

please find attached the UAT status reports from {date}:
{report_list}

The reports reflect the status of the day.

Best regards
Marina
"""


def smtp_settings(cfg: dict) -> dict | None:
    """Return SMTP settings, or None if credentials are not configured."""
    user, password = cfg.get("email_user"), cfg.get("email_password")
    if not user or not password:
        return None
    return {
        "host": cfg.get("email_smtp_host", "mail.gmx.net"),
        "port": int(cfg.get("email_smtp_port", 587)),
        "user": user,
        "password": password,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def standalone_html(html: str) -> str:
    """Make a rendered page self-contained for an email attachment:
    inline style.css, strip all scripts, hide interactive chrome, open all
    collapsed sections. Mirrors the board's client-side Download HTML."""
    css = (_HERE / "static" / "style.css").read_text(encoding="utf-8")
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S)
    html = re.sub(r'<link rel="stylesheet"[^>]*>', "", html)
    html = re.sub(r"<details(?![^>]*\bopen\b)", "<details open", html)
    hide = ("<style>" + css + "\n"
            ".rt-topbar,.rt-filterbar,.ui-filterbar,.pm-filterbar,dialog,"
            "#enh-widget,.btn,.btn-row,form,.rt-cbtn{display:none!important}"
            ".comment-input,.rt-comment,.pm-comment{border:none}"
            ".rpt-cmt,.co-input{border:none;background:transparent;padding:0}"
            ".co-empty{display:none!important}</style>")
    return html.replace("</head>", hide + "</head>", 1)


def render_spillover_html(conn: sqlite3.Connection, today: str) -> str:
    items = database.get_spillover_report_items(conn)
    order = {"yes": 0, "slightly": 1, "no": 2}
    items = sorted(items, key=lambda r: order.get(r.get("critical_for_signoff") or "", 3))
    details = {}
    for item in items:
        od = database.list_order_details(conn, "spillover", str(item["spillover_id"]))
        if od:
            details[item["spillover_id"]] = od
    return render_template(
        "spillover_report_view.html", items=items, order_details=details,
        report_comments=database.list_report_comments(conn, "spillover"), today=today)


def render_retail_html(conn: sqlite3.Connection, cfg: dict, today: str) -> str:
    """Same content as GET /retail/report/download.

    The impacted-defects context used to be missing here, so every EMAILED
    Retail report claimed "No active Retail defects found" while the live page
    listed them [fixed 2026-08-10]. Keep this in sync with
    web_retail.retail_report_download."""
    from app.db import retrofits as db_retrofits
    from app.reporter import compute_impacted_totals, passed_family
    mappings = load_status_mappings()
    status_counts = database.get_retail_status_counts(conn)
    report = compute_retail_report(status_counts, mappings)
    impacted_defects = database.get_retail_defects_impacted(
        conn, passed_family(mappings))
    totals = compute_impacted_totals(impacted_defects)
    return render_template(
        "retail_report_download.html", report=report, today=today,
        impacted_defects=impacted_defects,
        impacted_total=totals["total"],
        mb_total=totals["mb"],
        sales_total=totals["sales"],
        report_comments=database.list_report_comments(conn, "retail"),
        retrofits=db_retrofits.list_retrofits(conn, channel="Retail"),
        total_test_cases=cfg.get("retail_total_test_cases", 646),
        missing_categories=cfg.get("retail_missing_categories", []))


def gather_attachments(conn: sqlite3.Connection, cfg: dict, flask_app,
                       reports: list[str], day: str) -> list[tuple[str, str]]:
    """Render the selected reports. Returns [(filename, html), ...]."""
    out: list[tuple[str, str]] = []
    if "spillover" in reports:
        out.append((f"spillover_report_{day}.html",
                    render_spillover_html(conn, day)))
    if "retail" in reports:
        out.append((f"retail_report_{day}.html",
                    render_retail_html(conn, cfg, day)))
    if "board" in reports:
        # render the live board through the app itself, then make it standalone
        resp = flask_app.test_client().get("/retail-tracker/board")
        out.append((f"retail_requirements_board_{day}.html",
                    standalone_html(resp.get_data(as_text=True))))
    if "ecom" in reports:
        resp = flask_app.test_client().get("/ecom/report")
        out.append((f"ecom_report_{day}.html",
                    standalone_html(resp.get_data(as_text=True))))
    for stream in ("retail", "ecom"):
        if f"manual_{stream}" in reports:
            resp = flask_app.test_client().get(f"/manual/{stream}/report")
            out.append((f"manual_{stream}_report_{day}.html",
                        standalone_html(resp.get_data(as_text=True))))
    if "known_prod_defects" in reports:
        resp = flask_app.test_client().get("/prod_defects")
        out.append((f"known_prod_defects_{day}.html",
                    standalone_html(resp.get_data(as_text=True))))
    if "known_prod_defects_review" in reports:
        # already a self-contained interactive copy — its scripts (Detail
        # dialogs, comment widget) are the point, so NO standalone_html
        resp = flask_app.test_client().get("/prod_defects/download-review")
        out.append((f"known_prod_defects_review_{day}.html",
                    resp.get_data(as_text=True)))
    if "known_prod_defects_report" in reports:
        # management report download is already clean standalone HTML
        resp = flask_app.test_client().get("/prod_defects/report/download")
        out.append((f"known_prod_defects_report_{day}.html",
                    resp.get_data(as_text=True)))
    if "missing_tests" in reports:
        # the download route already returns clean standalone HTML
        resp = flask_app.test_client().get("/missing-tests/report/download")
        out.append((f"missing_test_cases_retail_{day}.html", resp.get_data(as_text=True)))
    # the delegated download routes already return clean standalone HTML
    # (toolbar/scripts stripped, call-outs static) — no standalone_html needed
    if "delegated" in reports:
        resp = flask_app.test_client().get("/delegated/report/download")
        out.append((f"delegated_report_{day}.html", resp.get_data(as_text=True)))
    if "delegated_numbers" in reports:
        resp = flask_app.test_client().get("/delegated/numbers/download")
        out.append((f"delegated_numbers_{day}.html",
                    resp.get_data(as_text=True)))
    return out


# ---------------------------------------------------------------------------
# Message assembly + sending
# ---------------------------------------------------------------------------

def build_message(sender: str, recipients: list[str], subject: str, body: str,
                  attachments: list[tuple[str, str]]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, html in attachments:
        msg.add_attachment(html.encode("utf-8"), maintype="text",
                           subtype="html", filename=filename)
    return msg


def send_message(settings: dict, msg: EmailMessage) -> None:
    with smtplib.SMTP(settings["host"], settings["port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings["user"], settings["password"])
        smtp.send_message(msg)


def default_texts(day: str | None = None, reports: list[str] | None = None) -> dict:
    day = day or date.today().isoformat()
    picked = reports or [k for k, _ in REPORT_CHOICES]
    labels = dict(REPORT_CHOICES)
    report_list = "\n".join(f"  - {labels[k]}" for k in picked if k in labels)
    return {
        "date": day,
        "subject": DEFAULT_SUBJECT.format(date=day),
        "body": DEFAULT_BODY.format(date=day, report_list=report_list),
    }
