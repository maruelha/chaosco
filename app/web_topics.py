"""Topics — Blueprint (/topics). Active working topics.

List (filter by title search / category / priority, done hidden by default)
and a big working page per topic: next steps (checkable, done ones archived
into a collapsed section), the shared notes module, and a screen-filling
formatted-text workpad (contenteditable, stored as HTML, autosaved).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config
from app.db import topics as db_topics

bp = Blueprint("topics", __name__, url_prefix="/topics")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])
_UPLOAD_FOLDER = Path(__file__).parent.parent / "data" / "uploads"


def _get_conn():
    return database.get_connection(_db_path)


@bp.route("/")
def topics_list():
    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    show_done = request.args.get("show_done") == "1"
    conn = _get_conn()
    try:
        items = db_topics.list_topics(conn, q=q or None, category=category or None,
                                      priority=priority or None, include_done=show_done)
        categories = db_topics.get_topic_categories(conn)
    finally:
        conn.close()
    return render_template("topics_list.html",
                           items=items, categories=categories,
                           priorities=db_topics.TOPIC_PRIORITIES,
                           q=q, f_category=category, f_priority=priority,
                           show_done=show_done)


@bp.route("/add", methods=["POST"])
def topic_add():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("topics.topics_list"))
    conn = _get_conn()
    try:
        topic_id = db_topics.create_topic(
            conn, title,
            category=request.form.get("category", ""),
            priority=request.form.get("priority", "Medium"))
    finally:
        conn.close()
    return redirect(url_for("topics.topic_detail", topic_id=topic_id))


@bp.route("/<int:topic_id>")
def topic_detail(topic_id: int):
    conn = _get_conn()
    try:
        topic = db_topics.get_topic(conn, topic_id)
        if topic is None:
            abort(404)
        steps = db_topics.list_steps(conn, topic_id)
        notes = database.list_notes(conn, "topic", str(topic_id))
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
        categories = db_topics.get_topic_categories(conn)
    finally:
        conn.close()
    return render_template("topic_detail.html",
                           topic=topic,
                           open_steps=[s for s in steps if not s["done"]],
                           done_steps=[s for s in steps if s["done"]],
                           notes=notes, attachments_by_note=attachments_by_note,
                           categories=categories,
                           priorities=db_topics.TOPIC_PRIORITIES)


@bp.route("/<int:topic_id>/update", methods=["POST"])
def topic_update(topic_id: int):
    conn = _get_conn()
    try:
        if db_topics.get_topic(conn, topic_id) is None:
            abort(404)
        db_topics.update_topic(
            conn, topic_id,
            title=request.form.get("title", "").strip() or "(untitled)",
            category=request.form.get("category", ""),
            priority=request.form.get("priority", "Medium"),
            status=request.form.get("status", "active"))
    finally:
        conn.close()
    return redirect(url_for("topics.topic_detail", topic_id=topic_id, saved="1"))


@bp.route("/<int:topic_id>/workpad", methods=["POST"])
def topic_workpad(topic_id: int):
    conn = _get_conn()
    try:
        if db_topics.get_topic(conn, topic_id) is None:
            abort(404)
        db_topics.save_workpad(conn, topic_id, request.form.get("workpad", ""))
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/<int:topic_id>/delete", methods=["POST"])
def topic_delete(topic_id: int):
    conn = _get_conn()
    try:
        filenames = db_topics.delete_topic(conn, topic_id)
    finally:
        conn.close()
    for fname in filenames:
        fp = _UPLOAD_FOLDER / fname
        if fp.exists():
            fp.unlink()
    return redirect(url_for("topics.topics_list"))


# ---- next steps (AJAX) ----------------------------------------------------

@bp.route("/<int:topic_id>/steps/add", methods=["POST"])
def step_add(topic_id: int):
    step = request.form.get("step", "").strip()
    if not step:
        return jsonify({"ok": False, "error": "empty"})
    conn = _get_conn()
    try:
        if db_topics.get_topic(conn, topic_id) is None:
            abort(404)
        step_id = db_topics.add_step(conn, topic_id, step)
    finally:
        conn.close()
    return jsonify({"ok": True, "id": step_id, "step": step})


@bp.route("/steps/<int:step_id>/toggle", methods=["POST"])
def step_toggle(step_id: int):
    done = request.form.get("done") == "1"
    conn = _get_conn()
    try:
        db_topics.set_step_done(conn, step_id, done)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/steps/<int:step_id>/update", methods=["POST"])
def step_update(step_id: int):
    text = request.form.get("step", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "empty"})
    conn = _get_conn()
    try:
        db_topics.update_step(conn, step_id, text)
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/steps/<int:step_id>/delete", methods=["POST"])
def step_delete(step_id: int):
    conn = _get_conn()
    try:
        db_topics.delete_step(conn, step_id)
    finally:
        conn.close()
    return jsonify({"ok": True})
