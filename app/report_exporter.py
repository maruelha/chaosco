"""Export dated HTML + PowerPoint snapshots of both status reports to disk.

Called from the POST /export-reports route (must run inside a Flask app context
so that render_template works). PDF export is retired (WeasyPrint removed);
PowerPoint uses the same builders as the download buttons on the reports.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from flask import render_template

from app import database
from app.ppt_retail import build_retail_ppt
from app.ppt_spillover import build_spillover_ppt
from app.reporter import compute_retail_report, load_status_mappings


def export_all_reports(conn: sqlite3.Connection, cfg: dict) -> list[Path]:
    """Render and save HTML + PPTX for the Retail and Spillover reports.

    Returns the list of paths written (4 files: 2 HTML + 2 PPTX).
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
    blocked_defects = database.get_retail_defects_blocked(conn)

    retail_ctx = dict(
        report=report,
        today=today,
        report_comments=report_comments,
        total_test_cases=cfg.get("retail_total_test_cases", 646),
        missing_categories=cfg.get("retail_missing_categories", []),
    )
    retail_html_path = folder / f"retail_report_{today}.html"
    retail_html_path.write_text(
        render_template("retail_report_download.html", **retail_ctx),
        encoding="utf-8")
    saved.append(retail_html_path)

    blocked_total = sum(d["blocked_tc_count"] for d in blocked_defects)
    dtco2c_total  = sum(d["blocked_tc_count"] for d in blocked_defects if d["dtco2c"])
    sales_total   = sum(d["blocked_tc_count"] for d in blocked_defects if not d["dtco2c"])
    retail_pptx_path = folder / f"retail_report_{today}.pptx"
    retail_pptx_path.write_bytes(build_retail_ppt(
        report=report,
        blocked_defects=blocked_defects,
        dtco2c_total=dtco2c_total,
        sales_total=sales_total,
        blocked_total=blocked_total,
        total_test_cases=cfg.get("retail_total_test_cases", 646),
        today=today,
        missing_categories=cfg.get("retail_missing_categories", []),
    ))
    saved.append(retail_pptx_path)

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
    spillover_html_path = folder / f"spillover_report_{today}.html"
    spillover_html_path.write_text(
        render_template("spillover_report_view.html", **spillover_ctx),
        encoding="utf-8")
    saved.append(spillover_html_path)

    spillover_pptx_path = folder / f"spillover_report_{today}.pptx"
    spillover_pptx_path.write_bytes(
        build_spillover_ppt(items=items, order_details=order_details, today=today))
    saved.append(spillover_pptx_path)

    return saved
