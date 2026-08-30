# Enhancements (about chaosco itself)

**Type:** mini app
**URL:** `/enhancements/page` + the floating panel on every page
**Storage:** `app/db/core.py` → `enhancements`
**Routes:** `app/web_planning.py`
**Templates:** `enhancements_page.html` + the `#enh-widget` panel in `base.html`

## Purpose

Ideas for improving chaosco, captured where they occur — on the page that just
annoyed you — instead of being lost between sessions.

## Architecture

The floating panel (bottom right, stacked with the 🔍 and 💬 widgets) adds an
item from anywhere with area, priority and status; `/enhancements/page` is the
full list with filters. Closed items are hidden by default; the dashboard badge
counts open ones.

## Rules & gotchas

- This is the idea capture. The agreed, planned work lives in
  `docs/build_plan.md` — an enhancement is not a to-do until it is written
  there.

## Related

`[[todo]]` · `[[topics]]`
