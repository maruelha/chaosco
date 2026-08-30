# Links

**Type:** mini app
**URL:** `/links` (+ detail page)
**Storage:** `app/db/core.py` → `links`
**Routes:** `app/web_reference.py`
**Templates:** `links.html` · `link_detail.html` · `_incoming_section.html`

## Purpose

The useful-URL directory: filter by area / tool / tag, one-click copy. The
global counterpart to `[[entity-links]]`, which hangs URLs off ONE entity.

## Architecture

List with filters + a detail page carrying the shared notes section (registry
key `link`, so inbox items can be filed onto a link). Incoming inbox items
routed to `link` show in the amber "Incoming" section.

## Rules & gotchas

- The old "Teams Channel" link rows were MIGRATED OUT of this table into
  `teams_chats` (kind='channel') at startup on 2026-07-16 — Teams channels
  belong to `[[teams-chats]]`, not here.

## Related

`[[teams-chats]]` · `[[entity-links]]` · `[[inbox]]`
