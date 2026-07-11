"""Reference — ecom gatekeeper, links, contacts, encouragements, learnings, limitations, inbox, shelf

Routes module (refactoring step 4) — registers on the shared app from
app.web_core; endpoint names and URLs are unchanged from the old monolith.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
from flask import jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app import database
from app.web_core import (app, _cfg, _get_conn, _not_found,
                          _UPLOAD_FOLDER, _IMAGE_EXTS, _ALLOWED_EXTS)

@app.route("/ecom-gatekeeper")
def ecom_gatekeeper_list():
    conn = _get_conn()
    try:
        rows = database.list_ecom_gatekeeper_rows(conn)
        docs_s4_ids = database.get_docs_s4_entity_ids(conn, "ecom_gatekeeper")
        jira_issues = database.list_jira_issues(conn)
        jira_comments = {i["jira_key"]: database.list_jira_comments(conn, i["jira_key"])
                         for i in jira_issues}
    finally:
        conn.close()
    return render_template("ecom_gatekeeper.html", rows=rows,
                           docs_s4_ids=docs_s4_ids,
                           jira_issues=jira_issues, jira_comments=jira_comments,
                           jira_ok=request.args.get("jira_ok"),
                           jira_msg=request.args.get("jira_msg"))


@app.route("/ecom-gatekeeper/import-jira", methods=["POST"])
def ecom_gatekeeper_import_jira():
    """'Update from Jira' — newest .xml from jira_gatekeeper_folder into the
    shared jira store (step 2 code; re-import refreshes status/assignee/
    comments only)."""
    from pathlib import Path as _Path
    from app.jira_importer import run_jira_import
    result = run_jira_import(_cfg, "gatekeeper")
    if result["ok"]:
        msg = (f"{_Path(result['xml_path']).name}: {result['parsed']} tickets — "
               f"{result['inserted']} new · {result['updated']} refreshed · "
               f"{result['comments']} comments")
        return redirect(url_for("ecom_gatekeeper_list", jira_ok="1", jira_msg=msg))
    return redirect(url_for("ecom_gatekeeper_list", jira_ok="0", jira_msg=result["error"]))


@app.route("/ecom-gatekeeper/add", methods=["POST"])
def ecom_gatekeeper_add():
    conn = _get_conn()
    try:
        row_id = database.add_ecom_gatekeeper_row(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "id": row_id})


@app.route("/ecom-gatekeeper/<int:row_id>/update", methods=["POST"])
def ecom_gatekeeper_update(row_id: int):
    jira_id       = request.form.get("jira_id",       "").strip()
    solman_id     = request.form.get("solman_id",     "").strip()
    testcase_name = request.form.get("testcase_name", "").strip()
    status        = request.form.get("status",        "open").strip()
    next_step     = request.form.get("next_step",     "").strip()
    conn = _get_conn()
    try:
        database.update_ecom_gatekeeper_row(conn, row_id, jira_id, solman_id, testcase_name, status, next_step)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/ecom-gatekeeper/<int:row_id>/delete", methods=["POST"])
def ecom_gatekeeper_delete(row_id: int):
    conn = _get_conn()
    try:
        database.delete_ecom_gatekeeper_row(conn, row_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/ecom-gatekeeper/<int:row_id>")
def ecom_gatekeeper_detail(row_id: int):
    note_added   = request.args.get("note_added")   == "1"
    note_saved   = request.args.get("note_saved")   == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    conn = _get_conn()
    try:
        row = database.get_ecom_gatekeeper_row(conn, row_id)
        if row is None:
            return render_template("404.html"), 404
        notes = database.list_notes(conn, "ecom_gatekeeper", str(row_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "ecom_gatekeeper_detail.html", row=row,
        notes=notes, attachments_by_note=attachments_by_note,
        note_added=note_added, note_saved=note_saved, note_deleted=note_deleted,
    )


@app.route("/links")
def links_list():
    areas       = request.args.getlist("area")
    tools       = request.args.getlist("tool")
    tags        = request.args.getlist("tag")
    search      = request.args.get("search", "").strip()
    conn = _get_conn()
    try:
        rows    = database.list_links(conn, areas=areas or None, tools=tools or None,
                                      tags=tags or None, search=search or None)
        options = database.get_link_options(conn)
    finally:
        conn.close()
    return render_template("links.html", rows=rows, options=options,
                           areas=areas, tools=tools, tags=tags, search=search)


@app.route("/links/new", methods=["GET", "POST"])
def link_new():
    if request.method == "POST":
        def _f(name): return request.form.get(name, "").strip() or None
        conn = _get_conn()
        try:
            row = database.create_link(
                conn,
                description=_f("description"),
                url=_f("url"),
                area=_f("area"),
                tool=_f("tool"),
                tags=_f("tags"),
            )
        finally:
            conn.close()
        return redirect(url_for("link_detail", link_id=row["id"], saved="1"))
    return render_template("link_detail.html", record={}, is_new=True, saved=False)


@app.route("/links/<int:link_id>", methods=["GET", "POST"])
def link_detail(link_id: int):
    saved = request.args.get("saved") == "1"
    conn = _get_conn()
    try:
        record = database.get_link(conn, link_id)
        if record is None:
            return render_template("404.html"), 404
        if request.method == "POST":
            def _f(name): return request.form.get(name, "").strip() or None
            database.update_link(
                conn, link_id,
                description=_f("description"),
                url=_f("url"),
                area=_f("area"),
                tool=_f("tool"),
                tags=_f("tags"),
            )
        notes = database.list_notes(conn, "link", str(link_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("link_detail", link_id=link_id, saved="1"))
    return render_template("link_detail.html", record=record, is_new=False, saved=saved,
                           notes=notes, attachments_by_note=attachments_by_note)


@app.route("/links/<int:link_id>/delete", methods=["POST"])
def link_delete(link_id: int):
    conn = _get_conn()
    try:
        database.delete_link(conn, link_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Contacts routes


@app.route("/contacts")
def contacts_list():
    areas  = request.args.getlist("area")
    topics = request.args.getlist("topic")
    tags   = request.args.getlist("tag")
    search = request.args.get("search", "").strip()
    conn = _get_conn()
    try:
        rows    = database.list_contacts(conn, areas=areas or None, topics=topics or None,
                                         tags=tags or None, search=search or None)
        options = database.get_contact_options(conn)
    finally:
        conn.close()
    return render_template("contacts.html", rows=rows, options=options,
                           areas=areas, topics=topics, tags=tags, search=search)


@app.route("/contacts/new", methods=["GET", "POST"])
def contact_new():
    if request.method == "POST":
        def _f(name): return request.form.get(name, "").strip() or None
        conn = _get_conn()
        try:
            row = database.create_contact(
                conn,
                name=_f("name") or "",
                email=_f("email"),
                area=_f("area"),
                topic=_f("topic"),
                comments=_f("comments"),
                tags=_f("tags"),
            )
        finally:
            conn.close()
        return redirect(url_for("contact_detail", contact_id=row["id"], saved="1"))
    return render_template("contact_detail.html", record={}, is_new=True, saved=False)


@app.route("/contacts/<int:contact_id>", methods=["GET", "POST"])
def contact_detail(contact_id: int):
    saved = request.args.get("saved") == "1"
    conn = _get_conn()
    try:
        record = database.get_contact(conn, contact_id)
        if record is None:
            return render_template("404.html"), 404
        if request.method == "POST":
            def _f(name): return request.form.get(name, "").strip() or None
            database.update_contact(
                conn, contact_id,
                name=_f("name") or "",
                email=_f("email"),
                area=_f("area"),
                topic=_f("topic"),
                comments=_f("comments"),
                tags=_f("tags"),
            )
        notes = database.list_notes(conn, "contact", str(contact_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("contact_detail", contact_id=contact_id, saved="1"))
    return render_template("contact_detail.html", record=record, is_new=False, saved=saved,
                           notes=notes, attachments_by_note=attachments_by_note)


@app.route("/contacts/<int:contact_id>/delete", methods=["POST"])
def contact_delete(contact_id: int):
    conn = _get_conn()
    try:
        database.delete_contact(conn, contact_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Encouragements


@app.route("/encouragements")
def encouragements_list():
    person_id = request.args.get("person_id", type=int)
    added     = request.args.get("added") == "1"
    conn = _get_conn()
    try:
        people = database.list_encouragement_people(conn)
        items  = database.list_encouragements(conn, person_id=person_id)
        person = next((p for p in people if p["id"] == person_id), None) if person_id else None
    finally:
        conn.close()
    return render_template(
        "encouragements.html",
        people=people,
        items=items,
        person=person,
        person_id=person_id,
        today=date.today().isoformat(),
        added=added,
    )


@app.route("/encouragements/add", methods=["POST"])
def encouragement_add():
    name     = request.form.get("person_name", "").strip()
    text     = request.form.get("text", "").strip()
    enc_date = request.form.get("date", "").strip() or date.today().isoformat()
    if not name or not text:
        return redirect(url_for("encouragements_list"))
    conn = _get_conn()
    try:
        person_id = database.get_or_create_encouragement_person(conn, name)
        database.add_encouragement(conn, person_id, text, enc_date)
    finally:
        conn.close()
    return redirect(url_for("encouragements_list", person_id=person_id, added="1"))


@app.route("/encouragements/<int:enc_id>/delivered", methods=["POST"])
def encouragement_toggle_delivered(enc_id: int):
    value = request.json.get("value", False) if request.is_json else bool(request.form.get("value"))
    conn = _get_conn()
    try:
        database.set_encouragement_delivered(conn, enc_id, value)
    finally:
        conn.close()
    return {"ok": True}


@app.route("/encouragements/<int:enc_id>/delete", methods=["POST"])
def encouragement_delete(enc_id: int):
    conn = _get_conn()
    try:
        database.delete_encouragement(conn, enc_id)
    finally:
        conn.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Test Learnings routes


@app.route("/test_learnings")
def test_learning_list():
    channels = request.args.getlist("channel")
    tags     = request.args.getlist("tag")
    conn = _get_conn()
    try:
        rows    = database.list_test_learnings(conn, channels=channels or None, tags=tags or None)
        options = database.get_test_learning_options(conn)
    finally:
        conn.close()
    return render_template("test_learning_list.html", rows=rows, options=options,
                           channels=channels, tags=tags)


@app.route("/test_learnings/new", methods=["GET", "POST"])
def test_learning_new():
    if request.method == "POST":
        def _f(n): return request.form.get(n, "").strip() or None
        channel  = request.form.get("channel", "").strip() or "Retail"
        learning = request.form.get("learning", "").strip()
        conn = _get_conn()
        try:
            row = database.create_test_learning(
                conn, channel=channel, topic=_f("topic"), learning=learning,
                scenario=_f("scenario"), tags=_f("tags"),
            )
        finally:
            conn.close()
        return redirect(url_for("test_learning_detail", learning_id=row["id"], saved="1"))
    prefill_channel = request.args.get("channel", "Retail")
    return render_template("test_learning_detail.html", record={"channel": prefill_channel},
                           is_new=True, saved=False)


@app.route("/test_learnings/<int:learning_id>", methods=["GET", "POST"])
def test_learning_detail(learning_id: int):
    saved        = request.args.get("saved")        == "1"
    note_added   = request.args.get("note_added")   == "1"
    note_saved   = request.args.get("note_saved")   == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    conn = _get_conn()
    try:
        record = database.get_test_learning(conn, learning_id)
        if record is None:
            return render_template("404.html"), 404
        if request.method == "POST":
            def _f(n): return request.form.get(n, "").strip() or None
            channel  = request.form.get("channel", "").strip() or "Retail"
            learning = request.form.get("learning", "").strip()
            database.update_test_learning(
                conn, learning_id, channel=channel, topic=_f("topic"), learning=learning,
                scenario=_f("scenario"), tags=_f("tags"),
            )
        notes = database.list_notes(conn, "test_learning", str(learning_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("test_learning_detail", learning_id=learning_id, saved="1"))
    return render_template(
        "test_learning_detail.html", record=record, is_new=False, saved=saved,
        notes=notes, attachments_by_note=attachments_by_note,
        note_added=note_added, note_saved=note_saved, note_deleted=note_deleted,
    )


@app.route("/test_learnings/<int:learning_id>/delete", methods=["POST"])
def test_learning_delete(learning_id: int):
    conn = _get_conn()
    try:
        database.delete_test_learning(conn, learning_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/test_limitations")
def test_limitation_list():
    channels = request.args.getlist("channel")
    conn = _get_conn()
    try:
        rows    = database.list_test_limitations(conn, channels=channels or None)
        options = database.get_test_limitation_options(conn)
    finally:
        conn.close()
    return render_template("test_limitation_list.html", rows=rows, options=options,
                           channels=channels)


@app.route("/test_limitations/new", methods=["GET", "POST"])
def test_limitation_new():
    if request.method == "POST":
        def _f(n): return request.form.get(n, "").strip() or None
        channel = request.form.get("channel", "").strip() or "Retail"
        limitation = request.form.get("limitation", "").strip()
        conn = _get_conn()
        try:
            row = database.create_test_limitation(
                conn, channel=channel, limitation=limitation,
                scenario=_f("scenario"), comment=_f("comment"),
            )
        finally:
            conn.close()
        return redirect(url_for("test_limitation_detail", limitation_id=row["id"], saved="1"))
    prefill_channel = request.args.get("channel", "Retail")
    return render_template("test_limitation_detail.html", record={"channel": prefill_channel},
                           is_new=True, saved=False)


@app.route("/test_limitations/<int:limitation_id>", methods=["GET", "POST"])
def test_limitation_detail(limitation_id: int):
    saved = request.args.get("saved") == "1"
    conn = _get_conn()
    try:
        record = database.get_test_limitation(conn, limitation_id)
        if record is None:
            return render_template("404.html"), 404
        if request.method == "POST":
            def _f(n): return request.form.get(n, "").strip() or None
            channel    = request.form.get("channel", "").strip() or "Retail"
            limitation = request.form.get("limitation", "").strip()
            database.update_test_limitation(
                conn, limitation_id, channel=channel, limitation=limitation,
                scenario=_f("scenario"), comment=_f("comment"),
            )
        notes = database.list_notes(conn, "test_limitation", str(limitation_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if request.method == "POST":
        return redirect(url_for("test_limitation_detail", limitation_id=limitation_id, saved="1"))
    return render_template("test_limitation_detail.html", record=record, is_new=False, saved=saved,
                           notes=notes, attachments_by_note=attachments_by_note)


@app.route("/test_limitations/<int:limitation_id>/delete", methods=["POST"])
def test_limitation_delete(limitation_id: int):
    conn = _get_conn()
    try:
        database.delete_test_limitation(conn, limitation_id)
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/inbox")
def inbox():
    conn = _get_conn()
    try:
        items = database.list_inbox_items(conn)
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in items])
    finally:
        conn.close()
    note_added   = request.args.get("note_added") == "1"
    note_saved   = request.args.get("note_saved") == "1"
    note_deleted = request.args.get("note_deleted") == "1"
    note_filed   = request.args.get("note_filed")
    return render_template(
        "inbox.html", items=items, attachments_by_note=attachments_by_note,
        note_added=note_added, note_saved=note_saved,
        note_deleted=note_deleted, note_filed=note_filed,
    )


@app.route("/inbox/add", methods=["POST"])
def inbox_add():
    heading   = request.form.get("heading", "").strip() or None
    note_text = request.form.get("note", "").strip() or None
    if heading or note_text:
        conn = _get_conn()
        try:
            database.add_inbox_item(conn, heading, note_text)
        finally:
            conn.close()
    return redirect(url_for("inbox", note_added="1"))


@app.route("/inbox/<int:note_id>/edit", methods=["POST"])
def inbox_edit(note_id: int):
    heading   = request.form.get("heading", "").strip() or None
    note_text = request.form.get("note", "").strip() or None
    if heading or note_text:
        conn = _get_conn()
        try:
            note = database.get_note(conn, note_id)
            if note and note["entity_type"] == "input":
                database.update_note(conn, note_id, heading, note_text)
        finally:
            conn.close()
    return redirect(url_for("inbox", note_saved="1"))


@app.route("/inbox/<int:note_id>/delete", methods=["POST"])
def inbox_delete(note_id: int):
    conn = _get_conn()
    try:
        filenames = database.delete_inbox_item(conn, note_id)
    finally:
        conn.close()
    for fname in filenames:
        fp = _UPLOAD_FOLDER / fname
        if fp.exists():
            fp.unlink()
    return redirect(url_for("inbox", note_deleted="1"))


@app.route("/inbox/<int:note_id>/file", methods=["POST"])
def inbox_file(note_id: int):
    target_type = request.form.get("target_type", "").strip()
    target_id   = request.form.get("target_id", "").strip()
    conn = _get_conn()
    try:
        ok = database.file_inbox_item(conn, note_id, target_type, target_id)
    finally:
        conn.close()
    if ok:
        return redirect(url_for("inbox", note_filed=target_type))
    return redirect(url_for("inbox"))


@app.route("/inbox/<int:note_id>/file-to-shelf", methods=["POST"])
def inbox_file_to_shelf(note_id: int):
    conn = _get_conn()
    try:
        note = database.get_inbox_item(conn, note_id)
        if note is None:
            return redirect(url_for("inbox"))
        area     = request.form.get("shelf_area", "").strip() or None
        category = request.form.get("shelf_category", "").strip() or None
        shelf_id = database.create_shelf_item(conn, note["heading"], area, category)
        database.file_inbox_item(conn, note_id, "shelf", str(shelf_id))
    finally:
        conn.close()
    return redirect(url_for("inbox", note_filed="Shelf"))


@app.route("/inbox/targets")
def inbox_targets():
    target_type = request.args.get("type", "").strip()
    q           = request.args.get("q", "").strip()
    conn = _get_conn()
    try:
        results = database.search_targets(conn, target_type, q)
    finally:
        conn.close()
    return jsonify(results)


# ---------------------------------------------------------------------------
# Shelf â€” catch-all store for inbox items without a specific home


@app.route("/shelf")
def shelf_list():
    areas      = request.args.getlist("area")
    categories = request.args.getlist("category")
    conn = _get_conn()
    try:
        items   = database.list_shelf_items(conn, areas or None, categories or None)
        options = database.get_shelf_filter_options(conn)
    finally:
        conn.close()
    return render_template(
        "shelf_list.html",
        items=items, options=options,
        sel_areas=areas, sel_categories=categories,
        item_added=request.args.get("item_added"),
        item_deleted=request.args.get("item_deleted"),
    )


@app.route("/shelf/<int:shelf_id>")
def shelf_detail(shelf_id: int):
    conn = _get_conn()
    try:
        item  = database.get_shelf_item(conn, shelf_id)
        if item is None:
            return render_template("404.html"), 404
        notes = database.list_notes(conn, "shelf", str(shelf_id))
        attachments_by_note = database.get_attachments_for_notes(conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "shelf_detail.html",
        item=item, notes=notes, attachments_by_note=attachments_by_note,
        note_added=request.args.get("note_added"),
        note_saved=request.args.get("note_saved"),
        note_deleted=request.args.get("note_deleted"),
        item_saved=request.args.get("item_saved"),
    )


@app.route("/shelf/combine", methods=["POST"])
def shelf_combine():
    primary_id  = request.form.get("primary_id", "").strip()
    item_ids    = request.form.getlist("item_ids")
    if not primary_id or not item_ids:
        return redirect(url_for("shelf_list"))
    try:
        primary_id = int(primary_id)
        item_ids   = [int(i) for i in item_ids]
    except ValueError:
        return redirect(url_for("shelf_list"))
    secondary_ids = [i for i in item_ids if i != primary_id]
    conn = _get_conn()
    try:
        database.combine_shelf_items(conn, primary_id, secondary_ids)
    finally:
        conn.close()
    return redirect(url_for("shelf_detail", shelf_id=primary_id))


@app.route("/shelf/add", methods=["POST"])
def shelf_add():
    heading  = request.form.get("heading", "").strip() or None
    area     = request.form.get("area", "").strip() or None
    category = request.form.get("category", "").strip() or None
    conn = _get_conn()
    try:
        database.create_shelf_item(conn, heading, area, category)
    finally:
        conn.close()
    return redirect(url_for("shelf_list", item_added="1"))


@app.route("/shelf/<int:shelf_id>/update", methods=["POST"])
def shelf_update(shelf_id: int):
    heading  = request.form.get("heading", "").strip() or None
    area     = request.form.get("area", "").strip() or None
    category = request.form.get("category", "").strip() or None
    conn = _get_conn()
    try:
        database.update_shelf_item(conn, shelf_id, heading, area, category)
    finally:
        conn.close()
    return redirect(url_for("shelf_detail", shelf_id=shelf_id, item_saved="1"))


@app.route("/shelf/<int:shelf_id>/delete", methods=["POST"])
def shelf_delete(shelf_id: int):
    conn = _get_conn()
    try:
        filenames = database.delete_shelf_item(conn, shelf_id)
    finally:
        conn.close()
    for fn in filenames:
        fp = _UPLOAD_FOLDER / fn
        if fp.exists():
            fp.unlink()
    return redirect(url_for("shelf_list", item_deleted="1"))

