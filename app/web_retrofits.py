"""Retrofits — routes (Flask Blueprint, 2026-08-10).

Hand-maintained list of coming system changes per channel; the ECOM and
Retail status reports render it at the bottom. No SQL here — storage in
app/db/retrofits.py.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import retrofits as db_retrofits
from app.db import topics as db_topics

bp = Blueprint("retrofits", __name__, url_prefix="/retrofits")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def _topic_id(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


@bp.route("/")
def retrofits_list():
    channel = request.args.get("channel", "").strip()
    conn = _get_conn()
    try:
        items = db_retrofits.list_retrofits(conn, channel=channel or None)
        counts = db_retrofits.retrofit_counts(conn)
        topics = db_topics.list_topics(conn)
    finally:
        conn.close()
    return render_template(
        "retrofits.html",
        items=items, counts=counts, topics=topics,
        channels=db_retrofits.RETROFIT_CHANNELS,
        statuses=db_retrofits.RETROFIT_STATUSES,
        sel_channel=channel,
        added=request.args.get("added") == "1",
    )


@bp.route("/add", methods=["POST"])
def retrofit_add():
    channel = request.form.get("channel", "").strip()
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("retrofits.retrofits_list", channel=channel))
    conn = _get_conn()
    try:
        db_retrofits.create_retrofit(
            conn, channel, title,
            description=request.form.get("description"),
            status=request.form.get("status", "Confirmed"),
            expected=request.form.get("expected"),
            topic_id=_topic_id(request.form.get("topic_id")),
            test_coverage_note=request.form.get("test_coverage_note"),
        )
    finally:
        conn.close()
    return redirect(url_for("retrofits.retrofits_list",
                            channel=request.form.get("channel_filter", ""),
                            added="1"))


@bp.route("/<int:retrofit_id>/update", methods=["POST"])
def retrofit_update(retrofit_id: int):
    title = request.form.get("title", "").strip()
    if not title:
        return jsonify({"ok": False, "error": "title is required"}), 400
    conn = _get_conn()
    try:
        db_retrofits.update_retrofit(
            conn, retrofit_id,
            channel=request.form.get("channel", ""),
            title=title,
            description=request.form.get("description"),
            status=request.form.get("status", "Confirmed"),
            expected=request.form.get("expected"),
            topic_id=_topic_id(request.form.get("topic_id")),
        )
    finally:
        conn.close()
    return redirect(url_for("retrofits.retrofits_list",
                            channel=request.form.get("channel_filter", "")))


@bp.route("/<int:retrofit_id>/note", methods=["POST"])
def retrofit_note_save(retrofit_id: int):
    """Test coverage note — authored HERE [USER 2026-08-30]; the Missing Test
    Cases page and the Retail Requirements board only display it."""
    conn = _get_conn()
    try:
        db_retrofits.set_coverage_note(conn, retrofit_id, request.form.get("note"))
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:retrofit_id>/delete", methods=["POST"])
def retrofit_delete(retrofit_id: int):
    conn = _get_conn()
    try:
        db_retrofits.delete_retrofit(conn, retrofit_id)
    finally:
        conn.close()
    return jsonify({"ok": True})
