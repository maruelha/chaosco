"""Export dated HTML + PDF snapshots of both status reports to a folder on disk.

Called from the POST /export-reports route (must run inside a Flask app context
so that render_template works).
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from flask import render_template

from app import database
from app.pdf_utils import save_pdf
from app.reporter import compute_retail_report, load_status_mappings


def export_all_reports(conn: sqlite3.Connection, cfg: dict) -> list[Path]:
    """Render and save HTML + PDF for the Retail and Spillover reports.

    Returns the list of paths written (4 files: 2 HTML + 2 PDF).
    """
    folder = Path(cfg.get("report_export_folder", "report_export"))
    folder.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    saved: list[Path] = []

    # ------------------------------------------------------------------ Retail
    status_counts   = database.get_retail_status_counts(conn)
    mappings        = load_status_mappings()
    report          = compute_retail_report(status_counts, mappings)
    report_comments = database.list_report_comments(conn, "retail")

    retail_ctx = dict(
        report=report,
        today=today,
        report_comments=report_comments,
        total_test_cases=cfg.get("retail_total_test_cases", 646),
        missing_categories=cfg.get("retail_missing_categories", []),
    )
    retail_html = render_template("retail_report_download.html", **retail_ctx)

    retail_html_path = folder / f"retail_report_{today}.html"
    retail_html_path.write_text(retail_html, encoding="utf-8")
    saved.append(retail_html_path)

    retail_pdf_path = folder / f"retail_report_{today}.pdf"
    save_pdf(retail_html, retail_pdf_path)
    saved.append(retail_pdf_path)

    # --------------------------------------------------------------- Spillover
    items = database.get_spillover_report_items(conn)
    _crit_order = {"yes": 0, "slightly": 1, "no": 2}
    items = sorted(items, key=lambda r: _crit_order.get(r.get("critical_for_signoff") or "", 3))

    order_details: dict = {}
    for item in items:
        od = database.list_order_details(conn, "spillover", str(item["spillover_id"]))
        if od:
            order_details[item["spillover_id"]] = od

    spillover_comments = database.list_report_comments(conn, "spillover")

    spillover_ctx = dict(
        items=items,
        order_details=order_details,
        report_comments=spillover_comments,
        today=today,
    )
    spillover_html = render_template("spillover_report_view.html", **spillover_ctx)

    spillover_html_path = folder / f"spillover_report_{today}.html"
    spillover_html_path.write_text(spillover_html, encoding="utf-8")
    saved.append(spillover_html_path)

    spillover_pdf_path = folder / f"spillover_report_{today}.pdf"
    save_pdf(spillover_html, spillover_pdf_path)
    saved.append(spillover_pdf_path)

    return saved
