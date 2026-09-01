"""Working-notes pages — routes (Flask Blueprint, 2026-09-01).

One generic route pair serves EVERY singleton notes page in
app/note_pages.PAGES (Ways of Working, Testing Insights, …): the page
itself (shared _notes_section.html — headings, text, attachments, Ctrl+V)
and a dated standalone HTML download. The registry is the only place a
page exists; buttons live wherever Marina wants them. No SQL here.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Blueprint, render_template

from app import database
from app.config_loader import load_config
from app.note_pages import PAGES

bp = Blueprint("note_pages", __name__, url_prefix="/notes-page")

_cfg = load_config()
_db_path = Path(_cfg["database_path"])


def _get_conn():
    return database.get_connection(_db_path)


def _page_or_404(slug: str):
    page = PAGES.get(slug)
    if page is None:
        from app.web_core import _not_found
        return None, _not_found(slug)
    return page, None


def _load_notes(slug: str, page: dict):
    conn = _get_conn()
    try:
        notes = database.list_notes(conn, "note_page", slug)
        attachments_by_note = database.get_attachments_for_notes(
            conn, [n["id"] for n in notes])
    finally:
        conn.close()
    if page.get("heading_mode") == "date":
        # date pages [USER 2026-09-01, Meeting Summaries] sort by the
        # note's date heading, newest first — NOT by when it was saved,
        # so pasting yesterday's summary today still lands under
        # yesterday's date. Same date twice is fine [USER] — ties keep
        # list_notes' created_at-desc order (Python sort is stable).
        notes = sorted(notes, key=lambda n: n.get("heading") or n["created_at"],
                       reverse=True)
    return notes, attachments_by_note


@bp.route("/<slug>")
def note_page(slug: str):
    page, err = _page_or_404(slug)
    if err:
        return err
    notes, attachments_by_note = _load_notes(slug, page)
    return render_template("note_page.html", slug=slug, page=page,
                           notes=notes,
                           attachments_by_note=attachments_by_note)


@bp.route("/<slug>/download")
def note_page_download(slug: str):
    """Dated standalone HTML snapshot — self-contained template (inline
    CSS, no app chrome); attachments are listed by name only."""
    page, err = _page_or_404(slug)
    if err:
        return err
    notes, attachments_by_note = _load_notes(slug, page)
    today = date.today().strftime("%Y-%m-%d")
    html = render_template("note_page_download.html", page=page,
                           notes=notes,
                           attachments_by_note=attachments_by_note,
                           today=today)
    return html, 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition":
            f'attachment; filename="{page["download_stem"]}_{today}.html"',
    }
