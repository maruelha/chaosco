"""Generic note routes — ONE add/edit/delete set for every entity type.

Replaces the ~10 copy-pasted per-module note route sets that used to live in
web.py (refactoring step 3). Driven by REGISTRY: each entity type declares how
to fetch its row, how to label it, and where its list/detail pages live —
everything else (validation, saving, redirects, the form templates) is shared.

The notes DATA layer was always unified (one `notes` table, entity_type +
entity_id); this brings the web layer up to the same standard.

URL shape:  /n/<entity_type>/<entity_id>/add | /<note_id>/edit | /<note_id>/delete

Quick-adds from list pages POST here too: pass a hidden `next` field and the
redirect goes back to that URL instead of the entity's detail page.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from app import database
from app.config_loader import load_config

bp = Blueprint("notes", __name__, url_prefix="/n")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


@dataclass(frozen=True)
class NoteEntity:
    """How the generic note routes see one entity type."""
    list_label: str                              # breadcrumb text
    list_endpoint: str                           # endpoint of the list page
    detail_endpoint: str | None                  # endpoint of the detail page (None = list only)
    detail_arg: str | None                       # kwarg name for the detail endpoint
    get_row: Callable | None                     # (conn, id) -> dict | None; None = skip 404 check
    label: Callable[[dict], str]                 # row -> heading text
    id_cast: Callable = str                      # notes.entity_id is TEXT; detail routes may need int


REGISTRY: dict[str, NoteEntity] = {
    "defect": NoteEntity(
        "Defects", "defects_list", "defect_detail", "defect_id",
        database.get_defect,
        lambda r: r["defect_id"] + (f" — {r['solman_name']}" if r.get("solman_name") else ""),
    ),
    "retail": NoteEntity(
        "Retail", "retail_list", "retail_detail", "retail_id",
        lambda c, i: database.get_retail_by_id(c, int(i)),
        lambda r: f"{r['test_case_id']} — {r['country']}", int,
    ),
    "spillover": NoteEntity(
        "Core South Spillover", "spillover_list", "spillover_detail", "spillover_id",
        lambda c, i: database.get_spillover_by_id(c, int(i)),
        lambda r: r.get("name") or f"Spillover #{r['spillover_id']}", int,
    ),
    "ecom": NoteEntity(
        "ECOM", "ecom.ecom_list", "ecom.ecom_detail", "ecom_id",
        lambda c, i: database.get_ecom_by_id(c, int(i)),
        lambda r: f"{r['test_case_id']} — {r['country']}", int,
    ),
    "followup": NoteEntity(
        "Follow-ups", "followup_list", "followup_detail", "followup_id",
        lambda c, i: database.get_followup_by_id(c, int(i)),
        lambda r: f"{r['with_whom']} — {r['topic']}", int,
    ),
    "shelf": NoteEntity(
        "Shelf", "shelf_list", "shelf_detail", "shelf_id",
        lambda c, i: database.get_shelf_item(c, int(i)),
        lambda r: r.get("heading") or f"Shelf item #{r['id']}", int,
    ),
    "test_learning": NoteEntity(
        "Test Learnings", "test_learning_list", "test_learning_detail", "learning_id",
        lambda c, i: database.get_test_learning(c, int(i)),
        lambda r: r.get("topic") or f"Learning #{r['id']}", int,
    ),
    "test_limitation": NoteEntity(
        "Test Limitations", "test_limitation_list", "test_limitation_detail", "limitation_id",
        lambda c, i: database.get_test_limitation(c, int(i)),
        lambda r: r.get("limitation") or f"Limitation #{r['id']}", int,
    ),
    "ecom_gatekeeper": NoteEntity(
        "ECOM Gatekeeper", "ecom_gatekeeper_list", "ecom_gatekeeper_detail", "row_id",
        lambda c, i: database.get_ecom_gatekeeper_row(c, int(i)),
        lambda r: r.get("testcase_name") or r.get("jira_id") or f"Row #{r['id']}", int,
    ),
    # gatekeeper JIRA tickets (the CURRENT gatekeeper, 2026-07-11) — notes hang
    # off the jira key, so they survive the gatekeeper -> ECOM handover
    "jira": NoteEntity(
        "Gatekeeper (Jira)", "ecom_gatekeeper_list", "gatekeeper_ticket_detail", "jira_key",
        lambda c, i: database.get_jira_issue(c, str(i)),
        lambda r: f"{r['jira_key']} — {r.get('summary') or ''}".rstrip(" —"), str,
    ),
    "cs_followup": NoteEntity(
        "CS Follow-Up Tracker", "cs_followup_list", "cs_followup_detail", "followup_id",
        lambda c, i: database.get_cs_followup(c, int(i)),
        lambda r: r.get("topic") or f"CS follow-up #{r['id']}", int,
    ),
    "topic": NoteEntity(
        "Topics", "topics.topics_list", "topics.topic_detail", "topic_id",
        lambda c, i: database.get_topic(c, int(i)),
        lambda r: r.get("title") or f"Topic #{r['id']}", int,
    ),
    "contact": NoteEntity(
        "Contacts", "contacts_list", "contact_detail", "contact_id",
        lambda c, i: database.get_contact(c, int(i)),
        lambda r: r.get("name") or f"Contact #{r['id']}", int,
    ),
    "link": NoteEntity(
        "Links", "links_list", "link_detail", "link_id",
        lambda c, i: database.get_link(c, int(i)),
        lambda r: r.get("description") or f"Link #{r['id']}", int,
    ),
    # list-only quick-add entities: no detail page, no 404 label lookup
    "meeting_prep": NoteEntity(
        "Meeting Prep", "meeting_prep_list", None, None, None,
        lambda r: "Meeting Prep item", int,
    ),
    "todo": NoteEntity(
        "To-Do", "todo_list", None, None, None,
        lambda r: "To-Do item", int,
    ),
}


def _entity_or_404(entity_type: str) -> NoteEntity:
    ent = REGISTRY.get(entity_type)
    if ent is None:
        abort(404)
    return ent


def _urls(ent: NoteEntity, entity_type: str, entity_id: str) -> dict:
    list_url = url_for(ent.list_endpoint)
    if ent.detail_endpoint:
        detail_url = url_for(ent.detail_endpoint, **{ent.detail_arg: ent.id_cast(entity_id)})
    else:
        detail_url = list_url
    return {"list_url": list_url, "detail_url": detail_url}


def _redirect_target(ent: NoteEntity, entity_type: str, entity_id: str, flag: str):
    nxt = request.form.get("next") or request.args.get("next")
    if nxt and nxt.startswith("/"):
        sep = "&" if "?" in nxt else "?"
        return redirect(f"{nxt}{sep}{flag}=1")
    urls = _urls(ent, entity_type, entity_id)
    base = urls["detail_url"] if request.values.get("return_to") != "list" else urls["list_url"]
    sep = "&" if "?" in base else "?"
    return redirect(f"{base}{sep}{flag}=1")


def _row_and_label(conn, ent: NoteEntity, entity_type: str, entity_id: str) -> str:
    if ent.get_row is None:
        return ent.label({})
    row = ent.get_row(conn, entity_id)
    if row is None:
        abort(404)
    return ent.label(row)


@bp.route("/<entity_type>/<entity_id>/list.json")
def note_list_json(entity_type: str, entity_id: str):
    """Notes as JSON — used by the expand-row UIs on list pages."""
    _entity_or_404(entity_type)
    conn = _get_conn()
    try:
        notes = database.list_notes(conn, entity_type, str(entity_id))
    finally:
        conn.close()
    return jsonify(notes)


@bp.route("/<entity_type>/<entity_id>/add.json", methods=["POST"])
def note_add_json(entity_type: str, entity_id: str):
    """Quick-add from list pages (no heading, plain text) — returns {ok, notes}."""
    _entity_or_404(entity_type)
    note_text = request.form.get("note", "").strip()
    if not note_text:
        return jsonify({"ok": False, "error": "empty"})
    heading = request.form.get("heading", "").strip() or None
    conn = _get_conn()
    try:
        database.add_note(conn, entity_type, str(entity_id), heading, note_text)
        notes = database.list_notes(conn, entity_type, str(entity_id))
    finally:
        conn.close()
    return jsonify({"ok": True, "notes": notes})


@bp.route("/<entity_type>/<entity_id>/add", methods=["GET", "POST"])
def note_add(entity_type: str, entity_id: str):
    ent = _entity_or_404(entity_type)
    conn = _get_conn()
    try:
        label = _row_and_label(conn, ent, entity_type, entity_id)
        if request.method == "POST":
            heading = request.form.get("heading", "").strip() or None
            note_text = request.form.get("note", "").strip() or None
            if note_text or heading:
                database.add_note(conn, entity_type, str(entity_id), heading, note_text)
                return _redirect_target(ent, entity_type, entity_id, "note_added")
            error = "A heading or note text is required."
        else:
            error = None
    finally:
        conn.close()
    urls = _urls(ent, entity_type, entity_id)
    return render_template(
        "note_form.html", mode="add",
        entity_label=label, list_label=ent.list_label,
        list_url=urls["list_url"], detail_url=urls["detail_url"],
        action_url=url_for("notes.note_add", entity_type=entity_type, entity_id=entity_id),
        cancel_url=urls["detail_url"],
        return_to=request.values.get("return_to", "detail"),
        heading=request.form.get("heading", ""), note_text=request.form.get("note", ""),
        error=error,
    )


@bp.route("/<entity_type>/<entity_id>/<int:note_id>/edit", methods=["GET", "POST"])
def note_edit(entity_type: str, entity_id: str, note_id: int):
    ent = _entity_or_404(entity_type)
    conn = _get_conn()
    try:
        note = database.get_note(conn, note_id)
        if note is None or note["entity_type"] != entity_type or note["entity_id"] != str(entity_id):
            abort(404)
        label = _row_and_label(conn, ent, entity_type, entity_id)
        if request.method == "POST":
            heading = request.form.get("heading", "").strip() or None
            note_text = request.form.get("note", "").strip() or None
            if note_text or heading:
                database.update_note(conn, note_id, heading, note_text)
                return _redirect_target(ent, entity_type, entity_id, "note_saved")
            error = "A heading or note text is required."
        else:
            error = None
    finally:
        conn.close()
    urls = _urls(ent, entity_type, entity_id)
    return render_template(
        "note_form.html", mode="edit",
        entity_label=label, list_label=ent.list_label,
        list_url=urls["list_url"], detail_url=urls["detail_url"],
        action_url=url_for("notes.note_edit", entity_type=entity_type,
                           entity_id=entity_id, note_id=note_id),
        cancel_url=urls["detail_url"], created_at=note["created_at"],
        heading=(request.form.get("heading") if request.method == "POST" else note["heading"]) or "",
        note_text=(request.form.get("note") if request.method == "POST" else note["note"]) or "",
        error=error,
    )


@bp.route("/<entity_type>/<entity_id>/<int:note_id>/delete", methods=["GET", "POST"])
def note_delete(entity_type: str, entity_id: str, note_id: int):
    ent = _entity_or_404(entity_type)
    conn = _get_conn()
    try:
        note = database.get_note(conn, note_id)
        if note is None or note["entity_type"] != entity_type or note["entity_id"] != str(entity_id):
            abort(404)
        if request.method == "POST":
            database.delete_note(conn, note_id)
            return _redirect_target(ent, entity_type, entity_id, "note_deleted")
        label = _row_and_label(conn, ent, entity_type, entity_id)
    finally:
        conn.close()
    urls = _urls(ent, entity_type, entity_id)
    return render_template(
        "note_confirm_delete.html", note=note,
        entity_label=label,
        cancel_url=urls["detail_url"],
        delete_url=url_for("notes.note_delete", entity_type=entity_type,
                           entity_id=entity_id, note_id=note_id),
    )
