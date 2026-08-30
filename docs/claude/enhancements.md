# Enhancements (about chaosco itself)

**Type:** mini app
**URL:** `/enhancements/page` + the floating panel on every page (`/enhancements/list.json`, `/add`, `/<id>/status`, `/<id>/update`, `/<id>/delete`)
**Storage:** `app/db/planning.py` over `db/core.py` → `enhancements`
**Routes:** `app/web_planning.py`
**Templates:** `enhancements_page.html` + the `#enh-widget` panel in `base.html`

## Purpose

Ideas for improving chaosco, captured on the page that just annoyed you instead
of being lost between sessions. This is the CAPTURE list — agreed work lives in
`docs/build_plan.md`.

## Architecture

**Columns**: `area`, `enhancement` (the text, NOT NULL), `priority`, `status`,
timestamps.

- `ENHANCEMENT_PRIORITIES` = `High` · `Medium` · `Low` (default Medium)
- `ENHANCEMENT_STATUSES` = `not_started` · `in_progress` · `closed`

Two surfaces over the same data:

- **The floating panel** (`#enh-widget` in `base.html`, bottom right, stacked
  with the 🔍 and 💬 widgets) — fully AJAX: `list.json` feeds it, `add` takes
  area + text + priority, `<id>/status` flips the status inline. Because it
  lives in the base template it is available on EVERY page, board included.
- **`/enhancements/page`** — the full list with sortable columns: `?sort=` one
  of `priority` / `status` / `area` plus `?dir=asc|desc`. Sorting happens in
  PYTHON over explicit rank maps (`{High:0, Medium:1, Low:2}`,
  `{not_started:0, in_progress:1, closed:2}`), not in SQL, so the order is the
  logical one rather than alphabetical. `?closed=1` includes closed items,
  hidden by default.

The dashboard badge counts the open ones.

## Rules & gotchas

- An enhancement is not a to-do until it is written into `docs/build_plan.md` —
  that is the agreed-work document, this is the idea inbox.
- `area` is free text built from what has been typed before
  (`get_enhancement_areas`), not a maintained list.

## Related

`[[todo]]` · `[[topics]]`
