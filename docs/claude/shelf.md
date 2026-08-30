# Shelf

**Type:** mini app
**URL:** `/shelf` (+ detail page)
**Storage:** `app/db/core.py` → `shelf`
**Routes:** `app/web_reference.py`
**Templates:** `shelf_list.html` · `shelf_detail.html`

## Purpose

The catch-all archive for notes that do not belong to a specific entity yet —
the counterpart to `[[topics]]`: **Shelf = parked, Topic = actively worked on**.

## Architecture

List / detail / combine (merge two shelf items). Carries the shared notes
section (registry key `shelf`) and is an inbox filing target.

## Related

`[[topics]]` · `[[inbox]]` · `[[notes]]`
