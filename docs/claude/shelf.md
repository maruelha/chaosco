# Shelf

**Type:** mini app
**URL:** `/shelf` · `/shelf/<id>` (+ `/add`, `/<id>/update`, `/<id>/delete`, `/combine`)
**Storage:** `app/db/reference.py` over `db/core.py` → `shelf`
**Routes:** `app/web_reference.py`
**Templates:** `shelf_list.html` · `shelf_detail.html`

## Purpose

The catch-all archive for notes that do not belong to a specific entity yet —
the counterpart to `[[topics]]`: **Shelf = parked, Topic = actively worked on.**
An inbox item that is worth keeping but has no home goes here.

## Architecture

`shelf` is deliberately thin — `heading`, `area`, `category`, `created_at`. The
CONTENT lives in the shared notes module (`entity_type='shelf'`), so a shelf
item is really "a heading with a note thread and attachments".

- **List**: multi-select filters for area and category, both built from the
  values in use (`get_shelf_filter_options`).
- **Detail**: the heading/area/category form plus the full notes section.
- **Filing in**: `POST /inbox/<id>/file-to-shelf` and the normal inbox picker.
- **Combine** (`POST /shelf/combine`): pick a primary item and any number of
  others — `combine_shelf_items` re-parents every note of the secondaries onto
  the primary (`UPDATE notes SET entity_id = <primary>`) and then DELETES the
  secondary shelf rows. Attachments follow automatically because they reference
  `note_id`, not the shelf row. The user lands on the primary's detail page.

## Rules & gotchas

- Combine is the merge tool for "I filed the same thing three times" — it moves
  notes, it never copies them, and the secondary rows are gone afterwards.
- Deleting a shelf item does NOT cascade its notes automatically; combine first
  if the content should survive.

## Related

`[[topics]]` · `[[inbox]]` · `[[notes]]`
