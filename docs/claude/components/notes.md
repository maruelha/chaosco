# Notes (the one notes system)

**Type:** component
**URL:** `/n/<entity_type>/<entity_id>/add | /<note_id>/edit | /<note_id>/delete` (+ `list.json`, `add.json`)
**Storage:** `app/db/notes.py` → `notes`, `attachments`
**Routes:** `app/web_notes.py` (Blueprint `notes`)
**Templates:** `_notes_section.html` · `note_form.html` · `note_confirm_delete.html` · `static/notes.js`
**Tests:** `tests/test_notes_generic.py`

## Purpose

Every entity in chaosco can carry a running note history. There is exactly ONE
implementation of that — one table, one web layer, one template, one JS file —
because the notes data layer was always unified while the web layer used to be
copy-pasted per module. This is architecture rule 3 in `CLAUDE.md`, and it is
non-negotiable.

## Architecture

- **Table** `notes`: `entity_type`, `entity_id` (TEXT — the string form of the
  parent PK), `created_at`, `heading`, `note`, `source`. Index on
  (entity_type, entity_id).
- **Routes** `app/web_notes.py` — generic add/edit/delete plus `list.json` /
  `add.json` for the expand-row UIs. A new entity type registers ONE
  `NoteEntity` in its `REGISTRY` (label, list/detail endpoints, row getter,
  id cast) — that is all a new module needs.
- **Template** `{% include '_notes_section.html' %}` with `entity_type`,
  `entity_id`, `notes`, `attachments_by_note` in context.
- **JS** `static/notes.js`, loaded globally: attachment upload, delete,
  Ctrl+V paste — via event delegation. Never inline a copy.
- **Data access** `app.db.notes`: add_note / list_notes / update_note /
  delete_note, the inbox helpers, the attachment helpers.
- **Quick-adds from list pages** POST here too: a hidden `next` field
  redirects back to that URL instead of the entity's detail page.

### Attachments

`attachments` (note_id FK, filename, original_name); files live in
`data/uploads/`. Routes: `/uploads/<filename>`,
`POST /notes/<note_id>/attachments/add`, `…/<id>/delete` (in `web_home.py`).
Images render as thumbnails, documents as download links (`is_image` filter).

## Rules & gotchas

- **Never** create a module-specific notes table, route set, or attachment
  script. Adding notes to a module = a REGISTRY entry + the include.
- **List-only entities (no detail page)** — `todo`, `meeting_prep` —
  render a lightweight expandable notes row inline (plain textarea via
  the generic `list.json` / `add.json` endpoints, small page-local
  script). **This is the LESSER pattern**: no heading, no attachments.
  `sustain_callout` used it too until 2026-09-01, when Marina asked
  where her headings/screenshots were [USER: "what you gave me was a
  simple text filed"] — its rows now include the full
  `_notes_section.html` instead (one instance per row). Copy the full
  component, not the quick-add widget, unless plain-text-only is a
  deliberate choice.
- **Multiple instances on ONE page** work since 2026-09-01: the wrapper
  id is `notes-{entity_type}-{entity_id}` (was a hardcoded `notes` —
  update anchors accordingly), and the add/edit/delete redirects carry
  `note_entity=<id>` so `_notes_section.html` shows the "saved" banner
  only on the instance that was actually touched.
- **`heading_mode='date'`** (2026-09-01, working-notes pages): if an
  entity's `get_row` dict carries `heading_mode: "date"`, the shared
  `note_form.html` renders the heading as a native date picker ONLY
  (prefilled with today on a fresh add). Generic — any registered
  entity's row may set it; everyone else keeps the free-text heading.
- A whole PAGE can be one notes thread: the **working-notes pages**
  (`('note_page', slug)`, 2026-09-01 — Ways of Working, Testing
  Insights, …) share ONE registry entry whose `get_row` looks the slug
  up in `app/note_pages.PAGES` (unknown slug → 404); the generic page
  template is a header plus the include. See `note-pages.md`. No new
  table, ever. (The first version was a hand-made singleton
  `('delegated_wow','main')`; it was generalized the same day.)
- `entity_id` is TEXT on purpose (jira keys as well as integer PKs) —
  `id_cast` in the registry entry converts back for the detail route.
- Notes-capable entities include `contact` and `link`, so inbox items can be
  filed onto them.
- Some entities deliberately share a notes thread and some deliberately do
  not: the gatekeeper and ECOM boards share `('jira', key)`, while Delegated
  Testing keeps its OWN thread (`delegated`) for the same jira key.

## Related

`[[inbox]]` (unfiled items are notes with `entity_type='input'`) ·
`[[next-steps]]` · `[[connections]]` · `[[entity-links]]` ·
`[[order-details]]` — the other drop-in components built on the same pattern.
