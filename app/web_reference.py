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
        docs_s4_jira = database.get_docs_s4_entity_ids(conn, "jira")
        from app.db import teams_chats as db_tc
        chats_by_entity = db_tc.chats_by_entity(conn, "jira")
        from app.db import jira as db_jira   # direct import (facade-order safe)
        from app.db import gatekeeper as db_gk
        jira_issues = db_jira.list_jira_issues(conn, seen_in="gatekeeper")
        jira_comments = {i["jira_key"]: db_jira.list_jira_comments(conn, i["jira_key"])
                         for i in jira_issues}
        gk_next_steps = db_gk.get_gatekeeper_next_steps(conn)
        track_sales_keys = db_gk.get_track_sales_keys(conn)
        jira_note_counts = {i["jira_key"]: len(database.list_notes(conn, "jira", i["jira_key"]))
                            for i in jira_issues}
        board_keys = {k.strip().lower() for (k,) in conn.execute(
            "SELECT jira_id FROM ecom WHERE jira_id IS NOT NULL")}
    finally:
        conn.close()

    # work-context sections [USER 2026-07-12]: gatekeeper board = Sales-facing
    # work. Active = assigned to me & not in validation; Back with Sales =
    # assigned away; in-validation tickets belong to the ECOM board (MB work).
    me = (_cfg.get("jira_gatekeeper_assignee") or "").strip().lower()
    validation = {s.strip().lower()
                  for s in _cfg.get("jira_validation_statuses", ["In Validation"])}
    for i in jira_issues:
        i["mine"] = bool(me) and me in (i.get("jira_assignee") or "").lower()
        i["in_validation"] = (i.get("jira_status") or "").strip().lower() in validation
        i["on_board"] = i["jira_key"].strip().lower() in board_keys
    gk_sections = [
        ("Active gatekeeping — with me",
         [i for i in jira_issues if i["mine"] and not i["in_validation"]]),
        ("↩ Back with Sales",
         [i for i in jira_issues if not i["mine"]]),
    ]
    in_validation_count = sum(1 for i in jira_issues
                              if i["mine"] and i["in_validation"])
    # tripwire: in validation but NOT on the ECOM board -> invisible on both
    # boards without this warning
    validation_lost = [i["jira_key"] for i in jira_issues
                       if i["in_validation"] and not i["on_board"]]

    # order-number report [USER 2026-07-11]: acceptance criteria first,
    # newest order-carrying comment as fallback
    from app.jira_importer import extract_order_numbers
    jira_orders = {i["jira_key"]: extract_order_numbers(
                       i.get("acceptance_criteria"), jira_comments[i["jira_key"]])
                   for i in jira_issues}
    return render_template("ecom_gatekeeper.html", rows=rows,
                           docs_s4_ids=docs_s4_ids,
                           docs_s4_jira=docs_s4_jira,
                           chats_by_entity=chats_by_entity,
                           jira_issues=jira_issues, jira_comments=jira_comments,
                           gk_sections=gk_sections,
                           in_validation_count=in_validation_count,
                           validation_lost=validation_lost,
                           jira_orders=jira_orders,
                           gk_next_steps=gk_next_steps,
                           track_sales_keys=track_sales_keys,
                           jira_note_counts=jira_note_counts,
                           jira_ok=request.args.get("jira_ok"),
                           jira_msg=request.args.get("jira_msg"))


_EPIC_KEY_RE = None  # compiled lazily in _epic_link


def _epic_link(issue: dict) -> str | None:
    """Browse link for the ticket's epic — built from the ticket's own link
    with the key swapped; None when the epic field is not a Jira key."""
    global _EPIC_KEY_RE
    import re
    if _EPIC_KEY_RE is None:
        _EPIC_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
    epic = (issue.get("epic") or "").strip()
    link = (issue.get("link") or "").strip()
    key = (issue.get("jira_key") or "").strip()
    if epic and link and key and _EPIC_KEY_RE.match(epic) and key in link:
        return link.replace(key, epic)
    return None


@app.route("/ecom-gatekeeper/sales-report")
def gatekeeper_sales_report():
    """ECOM Sales report v2 [USER 2026-07-16]: THREE sections — "With Sales"
    (ticked track_sales checkbox AND no longer assigned to Marina), "With
    Marina" (assigned + status in jira_marina_statuses), "With MB" (assigned
    + any other status). Epic link column instead of SolMan ID; 🎉 on passed
    tickets (jira_passed_statuses). Layout kept from v1 [USER: "I like it
    better"] — next steps, extracted order numbers, editable call-outs
    (report_comments key 'sales'), print-ready."""
    from datetime import date
    from app.db import gatekeeper as db_gk
    from app.db import jira as db_jira
    from app.jira_importer import extract_order_numbers
    conn = _get_conn()
    try:
        issues = db_jira.list_jira_issues(conn)
        comments_map = {i["jira_key"]: db_jira.list_jira_comments(conn, i["jira_key"])
                        for i in issues}
        next_steps = db_gk.get_gatekeeper_next_steps(conn)
        tracked = db_gk.get_track_sales_keys(conn)
        report_comments = database.list_report_comments(conn, "sales")
        board_keys = {k.strip().lower() for (k,) in conn.execute(
            "SELECT jira_id FROM ecom WHERE jira_id IS NOT NULL")}
        # scenario per jira key from the ECOM board rows (tickets not on the
        # board have none) — feeds the new Scenario column + filter
        scenario_map: dict = {}
        for jira_id, scen in conn.execute(
                "SELECT jira_id, testcase_scenario FROM ecom"
                " WHERE TRIM(COALESCE(jira_id,'')) <> ''"):
            if (scen or "").strip():
                scenario_map.setdefault(jira_id.strip().lower(), set()).add(scen.strip())
    finally:
        conn.close()

    me = (_cfg.get("jira_gatekeeper_assignee") or "").strip().lower()
    marina_statuses = {s.strip().lower() for s in _cfg.get(
        "jira_marina_statuses",
        ["In Progress", "Ready for Verification", "In Verification"])}
    passed_statuses = {s.strip().lower() for s in _cfg.get(
        "jira_passed_statuses", ["Done", "Closed"])}

    def _mine(i):
        return me and me in (i.get("jira_assignee") or "").lower()

    def _status(i):
        return (i.get("jira_status") or "").strip().lower()

    with_sales  = [i for i in issues if i["jira_key"] in tracked and not _mine(i)]
    with_marina = [i for i in issues if _mine(i) and _status(i) in marina_statuses]
    with_mb     = [i for i in issues if _mine(i) and _status(i) not in marina_statuses]

    shown = with_sales + with_marina + with_mb
    for i in shown:
        i["on_board"] = i["jira_key"].strip().lower() in board_keys
        i["next_step"] = next_steps.get(i["jira_key"])
        i["orders"] = extract_order_numbers(i.get("acceptance_criteria"),
                                            comments_map[i["jira_key"]])["orders"]
        i["epic_link"] = _epic_link(i)
        i["passed"] = _status(i) in passed_statuses or _status(i).startswith("passed")
        i["scenario"] = " / ".join(sorted(
            scenario_map.get(i["jira_key"].strip().lower(), set())))
    sections = [
        ("With Sales", "sec-sales", with_sales),
        ("With Marina", "sec-gk", with_marina),
        ("With MB", "sec-val", with_mb),
    ]
    # filter dropdown options [USER 2026-07-16]: reporter / status / scenario
    filter_options = {
        "reporters": sorted({(i.get("reporter") or "").strip()
                             for i in shown if (i.get("reporter") or "").strip()}),
        "statuses": sorted({(i.get("jira_status") or "").strip()
                            for i in shown if (i.get("jira_status") or "").strip()}),
        "scenarios": sorted({i["scenario"] for i in shown if i["scenario"]}),
    }
    return render_template(
        "gatekeeper_sales_report.html",
        sections=sections,
        total=len(shown),
        filter_options=filter_options,
        report_comments=report_comments,
        today=date.today().strftime("%Y-%m-%d"),
    )


@app.route("/ecom-gatekeeper/ticket/<jira_key>/next-step", methods=["POST"])
def gatekeeper_ticket_next_step(jira_key: str):
    """Inline blur-save of the authored next step on the tickets table."""
    database_conn = _get_conn()
    try:
        database.set_gatekeeper_next_step(
            database_conn, jira_key,
            request.form.get("next_step", "").strip() or None)
    finally:
        database_conn.close()
    return jsonify({"ok": True})


@app.route("/ecom-gatekeeper/ticket/<jira_key>/track-sales", methods=["POST"])
def gatekeeper_ticket_track_sales(jira_key: str):
    """AJAX toggle of the 'track on Sales report' checkbox [USER 2026-07-16]
    — tickable on ANY ticket (both views); shows under 'With Sales' on the
    report once the ticket is no longer assigned to Marina."""
    from app.db import gatekeeper as db_gk
    track = 1 if request.form.get("track") == "1" else 0
    conn = _get_conn()
    try:
        db_gk.set_track_sales(conn, jira_key, track)
    finally:
        conn.close()
    return jsonify({"ok": True, "track": track})


@app.route("/ecom-gatekeeper/ticket/<jira_key>", methods=["GET", "POST"])
def gatekeeper_ticket_detail(jira_key: str):
    """Detail page per gatekeeper JIRA ticket [USER 2026-07-11] — the current
    gatekeeper working object: read-only Jira data + authored next step
    (gatekeeper_annotations, archive component) + notes (entity 'jira')."""
    from app.db import jira as db_jira
    from app.jira_importer import extract_order_numbers
    conn = _get_conn()
    try:
        issue = db_jira.get_jira_issue(conn, jira_key)
        if issue is None:
            conn.close()
            return _not_found(jira_key)
        if request.method == "POST":
            database.set_gatekeeper_next_step(
                conn, jira_key, request.form.get("next_step", "").strip() or None)
            conn.close()
            return redirect(url_for("gatekeeper_ticket_detail",
                                    jira_key=jira_key, saved="1"))
        comments = db_jira.list_jira_comments(conn, jira_key)
        next_step = database.get_gatekeeper_next_step(conn, jira_key)
        notes = database.list_notes(conn, "jira", jira_key)
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    return render_template(
        "gatekeeper_ticket.html",
        issue=issue, comments=comments,
        orders=extract_order_numbers(issue.get("acceptance_criteria"), comments),
        next_step=next_step,
        notes=notes, attachments_by_note=attachments_by_note,
        saved=request.args.get("saved") == "1",
        note_added=request.args.get("note_added") == "1",
        note_saved=request.args.get("note_saved") == "1",
        note_deleted=request.args.get("note_deleted") == "1",
    )


# --- Jira acceptance-criteria takeover for order details [USER 2026-07-16]
# AC-only, archived counts as present, takeover only ADDS missing numbers.


def _jira_missing_orders(conn, jira_key: str) -> list[dict]:
    """AC (type, number) pairs whose number is in NO order row of
    ('jira', jira_key) — live or archived. A row counts as covering a
    number when its order_number equals or contains it (case-insensitive)."""
    from app.db import jira as db_jira
    from app.db import order_archive as db_oa
    from app.jira_importer import extract_ac_order_pairs
    issue = db_jira.get_jira_issue(conn, jira_key)
    if issue is None:
        return []
    present = {n.casefold() for n in db_oa.all_order_numbers(conn, "jira", jira_key)}
    missing = []
    for pair in extract_ac_order_pairs(issue.get("acceptance_criteria")):
        num = pair["order_number"].casefold()
        if not any(num == have or num in have for have in present):
            missing.append(pair)
    return missing


@app.route("/order-details/jira/<jira_key>/jira-suggestions")
def order_details_jira_suggestions(jira_key: str):
    conn = _get_conn()
    try:
        missing = _jira_missing_orders(conn, jira_key)
    finally:
        conn.close()
    return jsonify({"ok": True, "missing": missing})


@app.route("/order-details/jira/<jira_key>/take-over-jira", methods=["POST"])
def order_details_take_over_jira(jira_key: str):
    """Insert the missing AC numbers as order rows — recomputed server-side,
    never modifies or deletes existing rows, idempotent when nothing is missing."""
    conn = _get_conn()
    try:
        added = []
        for pair in _jira_missing_orders(conn, jira_key):
            detail_id = database.add_order_detail_full(
                conn, "jira", jira_key, pair["order_type"], pair["order_number"])
            added.append({"id": detail_id, "order_type": pair["order_type"],
                          "order_number": pair["order_number"],
                          "comment": "", "docs_in_s4": 0})
    finally:
        conn.close()
    return jsonify({"ok": True, "added": added})


@app.route("/ecom-gatekeeper/import-jira", methods=["POST"])
def ecom_gatekeeper_import_jira():
    """'Update from Jira' — ONE unified import [USER 2026-07-12]: refresh
    everything tracked, enter new tickets assigned to me or on the board."""
    from pathlib import Path as _Path
    from app.jira_importer import run_jira_import
    result = run_jira_import(_cfg)
    if result["ok"]:
        msg = (f"{_Path(result['xml_path']).name}: {result['parsed']} in file — "
               f"{result['refreshed']} tracked refreshed · "
               f"{result['new_gatekeeper']} new (assigned to you) · "
               f"{result['new_board']} new (on the board) · "
               f"{result['ignored']} ignored · {result['comments']} comments")
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
        incoming = database.list_incoming_notes(conn, "link")
    finally:
        conn.close()
    return render_template("links.html", rows=rows, options=options,
                           incoming=incoming,
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
        incoming = database.list_incoming_notes(conn, "contact")
    finally:
        conn.close()
    return render_template("contacts.html", rows=rows, options=options,
                           incoming=incoming,
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
        auto_filed=request.args.get("auto_filed"),
    )


def _inbox_ref_fields():
    return (request.form.get("order_number", "").strip() or None,
            request.form.get("solman_id", "").strip() or None,
            request.form.get("jira_id", "").strip() or None,
            request.form.get("route_to", "").strip() or None)


@app.route("/inbox/add", methods=["POST"])
def inbox_add():
    heading   = request.form.get("heading", "").strip() or None
    note_text = request.form.get("note", "").strip() or None
    if heading or note_text:
        conn = _get_conn()
        try:
            database.add_inbox_item(conn, heading, note_text, *_inbox_ref_fields())
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
                database.set_inbox_refs(conn, note_id, *_inbox_ref_fields())
        finally:
            conn.close()
    return redirect(url_for("inbox", note_saved="1"))


# --- Auto-file [USER 2026-07-16]: fields-only matching, preview-then-confirm


@app.route("/inbox/autofile/preview")
def inbox_autofile_preview():
    conn = _get_conn()
    try:
        result = database.preview_autofile(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, **result})


@app.route("/inbox/autofile/apply", methods=["POST"])
def inbox_autofile_apply():
    ids = [int(i) for i in request.form.get("ids", "").split(",")
           if i.strip().isdigit()]
    if not ids:
        return jsonify({"ok": False, "error": "no items selected"})
    conn = _get_conn()
    try:
        result = database.apply_autofile(conn, ids)
    finally:
        conn.close()
    return jsonify({"ok": True, **result})


# --- Incoming buckets [USER 2026-07-16]: (contact|link|followup, 'incoming')
# — sorted manually on the module page, never auto-connected to a row.

_INCOMING_LIST_URLS = {"contact": "contacts_list", "link": "links_list",
                       "followup": "followup_list"}


def _incoming_redirect(note):
    endpoint = _INCOMING_LIST_URLS.get(note["entity_type"] if note else "", "inbox")
    return redirect(url_for(endpoint))


@app.route("/incoming-notes/<int:note_id>/file", methods=["POST"])
def incoming_note_file(note_id: int):
    target_id = request.form.get("target_id", "").strip()
    conn = _get_conn()
    try:
        note = database.get_note(conn, note_id)
        database.file_incoming_note(conn, note_id, target_id)
    finally:
        conn.close()
    return _incoming_redirect(note)


@app.route("/incoming-notes/<int:note_id>/delete", methods=["POST"])
def incoming_note_delete(note_id: int):
    conn = _get_conn()
    try:
        note = database.get_note(conn, note_id)
        filenames = database.delete_incoming_note(conn, note_id)
    finally:
        conn.close()
    for fname in filenames:
        fp = _UPLOAD_FOLDER / fname
        if fp.exists():
            fp.unlink()
    return _incoming_redirect(note)


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

