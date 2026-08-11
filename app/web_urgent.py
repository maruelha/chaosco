"""Deadlines & Burning — routes (Flask Blueprint, 2026-08-11).

The nag list plus the dashboard popup's mark-done endpoint. No SQL here —
storage in app/db/urgent.py.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import urgent as db_urgent

bp = Blueprint("urgent", __name__, url_prefix="/urgent")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def urgent_list():
    show_done = request.args.get("show_done") == "1"
    conn = _get_conn()
    try:
        grouped = db_urgent.list_by_category(conn)
        counts = db_urgent.urgent_counts(conn)
        done_items = (db_urgent.list_urgent(conn, include_done=True)
                      if show_done else [])
    finally:
        conn.close()
    return render_template(
        "urgent.html",
        grouped=grouped, counts=counts,
        categories=db_urgent.URGENT_CATEGORIES,
        done_items=[i for i in done_items if i["done"]],
        show_done=show_done,
        msg=request.args.get("msg"),
    )


@bp.route("/add", methods=["POST"])
def urgent_add():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("urgent.urgent_list"))
    conn = _get_conn()
    try:
        db_urgent.create_urgent(
            conn,
            category=request.form.get("category", ""),
            title=title,
            due_date=request.form.get("due_date"),
            note=request.form.get("note"),
        )
    finally:
        conn.close()
    return redirect(url_for("urgent.urgent_list", msg="Added."))


@bp.route("/<int:item_id>/update", methods=["POST"])
def urgent_update(item_id: int):
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("urgent.urgent_list"))
    conn = _get_conn()
    try:
        db_urgent.update_urgent(
            conn, item_id,
            category=request.form.get("category", ""),
            title=title,
            due_date=request.form.get("due_date"),
            note=request.form.get("note"),
        )
    finally:
        conn.close()
    return redirect(url_for("urgent.urgent_list", msg="Saved."))


@bp.route("/<int:item_id>/done", methods=["POST"])
def urgent_done(item_id: int):
    """Used by the list AND by the dashboard popup (AJAX)."""
    done = request.form.get("done", "1") == "1"
    conn = _get_conn()
    try:
        db_urgent.set_done(conn, item_id, done)
        counts = db_urgent.urgent_counts(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "done": done, "counts": counts})


@bp.route("/<int:item_id>/delete", methods=["POST"])
def urgent_delete(item_id: int):
    conn = _get_conn()
    try:
        db_urgent.delete_urgent(conn, item_id)
    finally:
        conn.close()
    return jsonify({"ok": True})
