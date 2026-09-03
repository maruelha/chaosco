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

## Links per mini app (2026-09-03 [USER])

[USER: "link links to specific mini apps - and in those mini apps have a
button I can click that opens these links in a way I can either copy them
out or click on them to open"]. Planned in chat, dialog chosen over a page
(a two-second action should not leave the board).

- **Registry `app/mini_apps.py`** (`APPS`: slug → title, home endpoint;
  Flask-free like `note_pages.py`) — the FIRST code list of mini apps.
  Two to start [USER: "delegated testing and core south sustain - more I
  can add later"]: `delegated`, `sustain`. Adding an app = one entry +
  `{{ ui.app_links_button(slug, count) }}` in its page header + the count
  (`database.count_links_for_app`) in its route.
- **Table `link_apps`** (`link_id`, `app_slug`, PK both; in `db/core.py`
  next to `links`) — a link may belong to several apps; `set_link_apps`
  replaces the set and drops unknown slugs, `delete_link` cascades,
  `link_apps_by_link` (one query for the list page), `list_links_for_app`,
  `count_links_for_app` (tolerant of a missing table). `list_links` gained
  an `apps=` filter and lost its `COLLATE NOCASE` (`ORDER BY LOWER(...)`,
  rule 7).
- **Links card**: the edit form has a "Show in mini app" checkbox row; the
  list has a "Mini app" filter dialog + a Mini app column with 🔗 chips.
- **The 🔗 button + dialog**: `ui.app_links_button(slug, count)` renders
  "🔗 Links (n)" (dimmed without links); ONE `<dialog id="app-links-dialog">`
  lives in `base.html`, opened by any `.js-open-app-links[data-app-slug]`
  button and fed by `GET /links/for/<slug>.json` (404 for unknown slugs).
  Per link: open ↗ + copy; **📋 Copy all** writes both clipboard flavors
  (HTML = a bullet list of clickable names for Teams/Outlook; plain =
  "• name — url" lines), same technique as the delegated Teams lists.
  "Manage on the Links card…" is the only way to edit — nothing is edited
  in the dialog.
- **Not merged with the Teams-chat dialog** (component question asked
  and answered): different registries, different keys, and the chat dialog
  registers new chats inline, which links do not need. A third "attach
  registry rows to X" dialog would be the moment to generalize.
- Tests: `tests/test_link_apps.py`.

## Rules & gotchas

- The old "Teams Channel" link rows were MIGRATED OUT of this table into
  `teams_chats` (kind='channel') at startup on 2026-07-16. Teams channels
  belong to `[[teams-chats]]`, not here — do not re-add them as links.

## Related

`[[teams-chats]]` · `[[entity-links]]` · `[[inbox]]` · `[[contacts]]`
