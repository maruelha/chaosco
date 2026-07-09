"""Retail Requirements Tracker — routes (Flask Blueprint).

Own file by design: new verticals get their own Blueprint instead of growing
web.py (see docs/project_review_2026-07-04.md). No SQL here — everything goes
through db_retail_tracker.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import database
from app import db_retail_tracker as db
from app.config_loader import load_config
from app.retail_tracker_counting import compute_from_db
from app.retail_tracker_importer import run_tracker_import

# No payment area (user decision 2026-07-04): the Payment methods tab is
# duplicative; its two unique rows are folded into Return by the importer.
_AREA_ORDER = [("sales", "Tracking Sales"), ("return", "Tracking Return")]

bp = Blueprint("retail_tracker", __name__, url_prefix="/retail-tracker")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def _render_home(result=None):
    conn = _get_conn()
    try:
        counts = db.requirement_counts(conn)
        unresolved = db.list_requirements(conn, unresolved_only=True)
        needs_decision = db.list_needs_decision(conn)
        test_options = db.get_retail_test_options(conn)
        countries = db.list_countries(conn)
        cpm_counts = db.cpm_counts(conn)
        cpm_unknown = db.list_cpm(conn, unknown_category_only=True)
        tab4_tests = db.list_tab4_tests(conn)
        coverage = db.get_passed_test_coverage(conn)
        clarify_ids = db.clarify_requirement_ids(conn)
        parked_count = len(db.list_parked_tests(conn))
    finally:
        conn.close()
    default_path = "report_export/TRACKING_Retail ROE UAT Testcases DTC (1).xlsx"
    return render_template(
        "retail_tracker.html",
        counts=counts, unresolved=unresolved, needs_decision=needs_decision,
        test_options=test_options, countries=countries, result=result,
        cpm_counts=cpm_counts, cpm_unknown=cpm_unknown, tab4_tests=tab4_tests,
        coverage=coverage, clarify_ids=clarify_ids, parked_count=parked_count,
        excel_path=_cfg.get("retail_tracker_excel", default_path),
    )


@bp.route("/")
def tracker_home():
    return _render_home()


@bp.route("/import", methods=["POST"])
def tracker_import():
    result = run_tracker_import(_cfg)
    return _render_home(result=result)


@bp.route("/requirements/<int:req_id>/resolve", methods=["POST"])
def tracker_resolve(req_id: int):
    test_case_id = request.form.get("test_case_id", "").strip() or None
    conn = _get_conn()
    try:
        db.resolve_requirement(conn, req_id, test_case_id)
    finally:
        conn.close()
    return redirect(url_for("retail_tracker.tracker_home"))


@bp.route("/requirements/add", methods=["POST"])
def tracker_req_add():
    """Manual requirement (the Excel was only the first seeding). Born
    unresolved; the test link is made via the pick dropdowns afterwards."""
    area = request.form.get("area", "").strip()
    name = request.form.get("name", "").strip()
    required_raw = request.form.get("required", "").strip()
    if area in ("sales", "return") and name:
        conn = _get_conn()
        try:
            db.add_manual_requirement(
                conn, area, name,
                request.form.get("scenario_label", "").strip() or None,
                required_raw)
        finally:
            conn.close()
    return redirect(url_for("retail_tracker.tracker_home") + "#unresolved")


@bp.route("/requirements/<int:req_id>/edit", methods=["POST"])
def tracker_req_edit(req_id: int):
    """Edit the user-ownable fields (board pencil). test_name / test_case_id
    stay dropdown-only by design [USER 2026-07-06]."""
    name = request.form.get("name", "").strip()
    if name:
        conn = _get_conn()
        try:
            db.update_requirement_fields(
                conn, req_id, name,
                request.form.get("scenario_label", "").strip() or None,
                request.form.get("required", "").strip())
        finally:
            conn.close()
    # back to the edited row, not the top of the board
    return redirect(url_for("retail_tracker.tracker_board") + f"#req-{req_id}")


@bp.route("/clarify/add", methods=["POST"])
def tracker_clarify_add():
    req_id = request.form.get("req_id", type=int)
    if req_id:
        conn = _get_conn()
        try:
            db.add_clarify(conn, req_id)
        finally:
            conn.close()
    return redirect(url_for("retail_tracker.tracker_home") + "#unresolved")


@bp.route("/clarify/<int:item_id>/delete", methods=["POST"])
def tracker_clarify_delete(item_id: int):
    conn = _get_conn()
    try:
        db.delete_clarify(conn, item_id)
    finally:
        conn.close()
    return redirect(url_for("retail_tracker.tracker_board") + "#clarify")


@bp.route("/coverage/park", methods=["POST"])
def tracker_park():
    test_case_id = request.form.get("test_case_id", "").strip()
    if test_case_id:
        conn = _get_conn()
        try:
            db.park_test(conn, test_case_id)
        finally:
            conn.close()
    return redirect(url_for("retail_tracker.tracker_home") + "#coverage")


@bp.route("/parked/<int:item_id>/unpark", methods=["POST"])
def tracker_unpark(item_id: int):
    conn = _get_conn()
    try:
        db.unpark_test(conn, item_id)
    finally:
        conn.close()
    return redirect(url_for("retail_tracker.tracker_board") + "#parked")


@bp.route("/parked/<int:item_id>/comment", methods=["POST"])
def tracker_parked_comment(item_id: int):
    conn = _get_conn()
    try:
        db.set_parked_comment(conn, item_id,
                              request.form.get("comment", "").strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/coverage/assign", methods=["POST"])
def tracker_coverage_assign():
    """Reverse manual pick from the coverage check: attach an unmatched passed
    dashboard test to a still-unresolved requirement (same stored link as the
    unresolved-side pick; survives re-imports the same way)."""
    req_id = request.form.get("req_id", type=int)
    test_case_id = request.form.get("test_case_id", "").strip()
    if req_id and test_case_id:
        conn = _get_conn()
        try:
            db.assign_test_to_unresolved(conn, req_id, test_case_id)
        finally:
            conn.close()
    return redirect(url_for("retail_tracker.tracker_home") + "#coverage")


@bp.route("/board")
def tracker_board():
    """The requirements board — mirrors the tracking Excel: rows sorted by
    test case, country columns in the Excel's column order, live ✓ marks."""
    conn = _get_conn()
    try:
        result = compute_from_db(conn)
        countries = db.list_countries(conn, active_only=True)
        status_map = {(t, c.strip().casefold()): s
                      for t, c, s in db.get_passed_status_rows(conn)}
        missing_tests = db.list_missing_tests(conn)
        clarify_items = db.list_clarify(conn)
        parked_tests = db.list_parked_tests(conn)
        # display names with original casing (test_name on the row is normalized)
        display_names = {}
        for t in db.get_retail_test_options(conn):
            name = t["testcase_name"]
            display_names[t["test_case_id"]] = (
                name.split("_", 1)[1].strip() if "_" in name else name)
    finally:
        conn.close()

    areas = []
    for area, label in _AREA_ORDER:
        items = [i for i in result["requirements"]["items"] if i["area"] == area]
        # Excel row order — the board reads like the tab (payment-tab rows,
        # keyed +1000, land at the end of their section)
        items.sort(key=lambda i: i["excel_row"])
        rows = []
        for i in items:
            i["display_test_name"] = (display_names.get(i["test_case_id"])
                                      or i["test_name"] or "")
            targets_keyed = {t.strip().casefold() for t in (i["targets"] or [])}
            counted_keyed = {c.strip().casefold() for c in i["counted"]}
            cells = []
            for c in countries:
                ckey = c["name"].strip().casefold()
                status = status_map.get((i["test_case_id"], ckey)) if i["test_case_id"] else None
                if ckey in counted_keyed:
                    state = "pass"
                elif status:
                    state = "other"
                else:
                    state = "none"
                cells.append({"state": state, "status": status or "no execution",
                              "target": ckey in targets_keyed})
            rows.append({"item": i, "cells": cells})
        areas.append({"area": area, "label": label, "rows": rows,
                      "scenarios": sorted({i["scenario_label"] for i in items
                                           if i["scenario_label"]}),
                      "summary": result["by_area"].get(area,
                                 {"total": 0, "done": 0, "open": 0, "unresolved": 0})})

    cpm_items = sorted(result["cpm"]["items"],
                       key=lambda r: (r["country"], r["method_name"]))
    for r in cpm_items:
        kinds = r["kinds"]
        sale = kinds.get("sale_card") or kinds.get("sale_voucher")
        ret = kinds.get("return_card") or kinds.get("return_voucher")
        r["sale_ok"] = bool(sale and sale["checked"])
        r["return_ok"] = bool(ret and ret["checked"])

    return render_template(
        "retail_tracker_board.html",
        areas=areas, countries=countries,
        req_summary=result["requirements"]["summary"],
        cpm_items=cpm_items, cpm_summary=result["cpm"]["summary"],
        cpm_countries=sorted({r["country"] for r in cpm_items}),
        missing_tests=missing_tests,
        clarify_items=clarify_items, parked_tests=parked_tests,
        as_of=datetime.now().strftime("%Y-%m-%d %H:%M"),
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@bp.route("/missing/add", methods=["POST"])
def missing_add():
    text = request.form.get("text", "").strip()
    if text:
        conn = _get_conn()
        try:
            db.add_missing_test(conn, text)
        finally:
            conn.close()
    return redirect(url_for("retail_tracker.tracker_board") + "#missing-tests")


@bp.route("/missing/<int:item_id>/delete", methods=["POST"])
def missing_delete(item_id: int):
    conn = _get_conn()
    try:
        db.delete_missing_test(conn, item_id)
    finally:
        conn.close()
    return redirect(url_for("retail_tracker.tracker_board") + "#missing-tests")


@bp.route("/payment-methods")
def tracker_payment_methods():
    """Tab-4 management: per (country x method x test kind) manual check-off.
    The four fixed tests pass once per country; a human confirms per method
    whether that run covered it."""
    conn = _get_conn()
    try:
        result = compute_from_db(conn)
        tab4_tests = db.list_tab4_tests(conn)
    finally:
        conn.close()
    items = sorted(result["cpm"]["items"],
                   key=lambda r: (r["country"], r["method_name"]))
    fcountries = sorted({r["country"] for r in items})
    return render_template(
        "retail_tracker_payment.html",
        items=items, summary=result["cpm"]["summary"],
        tab4_tests=tab4_tests, fcountries=fcountries,
        as_of=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@bp.route("/payment-methods/<int:cpm_id>/category", methods=["POST"])
def tracker_cpm_category(cpm_id: int):
    category = request.form.get("category", "").strip() or None
    if category not in (None, "card", "voucher"):
        category = None
    conn = _get_conn()
    try:
        db.set_cpm_category(conn, cpm_id, category)
    finally:
        conn.close()
    return redirect(url_for("retail_tracker.tracker_payment_methods"))


@bp.route("/payment-methods/<int:cpm_id>/check", methods=["POST"])
def tracker_cpm_check(cpm_id: int):
    kind = request.form.get("kind", "")
    value = request.form.get("value") == "1"
    if kind not in ("sale_card", "sale_voucher", "return_card", "return_voucher"):
        return jsonify({"ok": False, "error": "bad kind"}), 400
    conn = _get_conn()
    try:
        db.set_cpm_check(conn, cpm_id, kind, value)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/requirements/<int:req_id>/comment", methods=["POST"])
def tracker_req_comment(req_id: int):
    conn = _get_conn()
    try:
        db.set_requirement_user_comment(
            conn, req_id, request.form.get("user_comment", "").strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/payment-methods/<int:cpm_id>/comment", methods=["POST"])
def tracker_cpm_comment(cpm_id: int):
    conn = _get_conn()
    try:
        db.set_cpm_user_comment(conn, cpm_id,
                                request.form.get("user_comment", "").strip() or None)
    finally:
        conn.close()
    return jsonify({"ok": True})
