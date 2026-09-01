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
- **List-only entities (no detail page)** — `todo`, `meeting_prep`,
  `sustain_callout` — don't use `_notes_section.html` (it assumes a
  detail-page layout): each renders an expandable notes row inline in its
  list table instead, via the SAME generic `list.json` / `add.json`
  endpoints, with a small page-local script (not `static/notes.js`, which
  assumes that page's own `.js-notes-toggle` markup). The DATA layer stays
  unified either way — only the inline-row rendering is per-page glue.
- A whole PAGE can be one notes thread: a **singleton entity** with a
  fixed id (first: `('delegated_wow', 'main')`, the Delegated Ways of
  Working page, 2026-09-01) — registry entry with `detail_endpoint=None`
  and `get_row=None`, the page template is just a header plus the
  include. No new table, ever.
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
