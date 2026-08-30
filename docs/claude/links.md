# Links

**Type:** mini app
**URL:** `/links` · `/links/new` · `/links/<id>` (+ `/delete`)
**Storage:** `app/db/reference.py` over `db/core.py` → `links`
**Routes:** `app/web_reference.py`
**Templates:** `links.html` · `link_detail.html` · `_incoming_section.html`

## Purpose

The useful-URL directory: the Confluence pages, dashboards and tools you need
again and again, filterable and copyable. The GLOBAL counterpart to
`[[entity-links]]`, which hangs URLs off one entity.

## Architecture

**Columns**: `description` (NOT NULL — the display name), `url` (NOT NULL),
`area`, `tool`, `tags`, timestamps.

- **List**: multi-select filters for area, tool and tags plus a free-text
  search; options from the values in use (`get_link_options`). One-click copy
  per row.
- **Detail**: the form plus the shared notes section (registry key `link`).
- **Incoming**: inbox items routed to `link` appear in the amber
  `_incoming_section.html` block at the top of the list — attach one to a link
  or delete it there; nothing is auto-connected (`[[inbox]]`).

## Rules & gotchas

- The old "Teams Channel" link rows were MIGRATED OUT of this table into
  `teams_chats` (kind='channel') at startup on 2026-07-16. Teams channels
  belong to `[[teams-chats]]`, not here — do not re-add them as links.

## Related

`[[teams-chats]]` · `[[entity-links]]` · `[[inbox]]` · `[[contacts]]`
