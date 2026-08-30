# Teams Chats & channels registry

**Type:** mini app
**URL:** `/teams-chats/` (+ `add`, `<id>/update`, `<id>/delete`, `all.json`, `pinned.json`, `refs/<etype>/<eid>[/attach|/detach]`)
**Storage:** `app/db/teams_chats.py` → `teams_chats`, `teams_chat_refs`
**Routes:** `app/web_teams_chats.py`
**Templates:** `teams_chats.html` · `_teams_chat_links.html` · the floating 💬 widget in `base.html`
**Tests:** `tests/test_teams_chats.py`

## Purpose

[USER 2026-07-16] One place for the Teams chats and channels that matter, so a
ticket can point at the conversation it is discussed in — and the important
ones are one click away from every page.

## Architecture

ONE table `teams_chats` for chats AND channels: `name`, `kind`, `link` (a
copied Teams deep link) OR `emails` (the deep link is built on click via
`teams_link.build_chat_link`), `description`, `pinned`. One management UI at
`/teams-chats` (dashboard card): inline-edit table, add via prompts, delete
detaches everywhere. `migrate_channel_links` moved the old "Teams Channel"
rows out of `links` (idempotent, runs at startup from `init_schema`).

- **Per-ticket chats** — `teams_chat_refs (entity_type, entity_id, chat_id)`:
  tickets REFERENCE registry rows (connected, never copied; several per ticket
  allowed). Drop-in `_teams_chat_links.html` (dialog + delegated
  `.js-open-chats` buttons, `data-tcl-name` = subtitle): attached list (open ↗
  · copy · detach) + registry search-attach + inline "new chat: register &
  attach". On the DETAIL pages of Retail, Spillover, ECOM and the Gatekeeper
  ticket (ECOM + gatekeeper share via `('jira', key)`, like orders and notes).
- **List rows** use `ui.chat_row_button(...)` from `_macros.html`: ONE chat =
  direct open link (the fast path), several = dialog button, NONE = dimmed
  button that opens the attach dialog [USER 2026-07-17 — the first chat must be
  attachable straight from every list]. Context needs `chats_by_entity` (db
  helper, tolerant of a missing schema in test fixtures).
- **Floating 💬 widget** (`base.html`, stacked above 🔍): PINNED chats only —
  open ↗ + copy per chat + a "Manage…" link. `/teams-chats/pinned.json`.

## Rules & gotchas

- The channel picker component (`[[teams-ping]]`) stores its channels HERE
  since 2026-07-16, but its own routes and shapes were left unchanged.

## Related

`[[teams-ping]]` · `[[issue-message]]` · `[[links]]`
