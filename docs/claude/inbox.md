# Inbox

**Type:** mini app
**URL:** `/inbox`
**Storage:** `app/db/notes.py` → `notes` rows with `entity_type='input'`, `entity_id='inbox'`; auto-file logic in `app/db/inbox_autofile.py`
**Routes:** `app/web_reference.py` (capture pad, filing, routing) + the shared `/notes/...` attachment routes
**Templates:** `inbox.html` · `_incoming_section.html`
**Tests:** `tests/test_inbox_delete.py`, `tests/test_inbox_quick_route.py`, `tests/test_inbox_search.py`, `tests/test_inbox_autofile.py`

## Purpose

The daily capture pad: paste a note or a screenshot the moment it happens, tag
it with an Order / SolMan / Jira id or a route-to, and file it to its real
destination later. Nothing is lost because you did not yet know where it
belongs.

## Architecture

Unfiled items ARE notes (`entity_type='input'`, `entity_id='inbox'`) — filing
is one UPDATE re-parenting the row, and the attachments follow automatically.
The inbox keeps its own routes and UI (capture pad + filing) on top of the
shared notes storage.

- **Filing targets** (`_INBOX_TARGET_TYPES` in `db/notes.py` + picker options
  in `inbox.html` + a search/exists branch each): defect, retail, spillover,
  ecom (2026-07-10, search by jira id / test case / name), ecom_gatekeeper
  (2026-07-11, legacy — no picker option any more), jira = "Gatekeeper ticket"
  (2026-07-11, the current gatekeeper; search by jira key / solman id /
  summary), test_learning, followup, shelf, topic, contact, link,
  prod_defect = "Known Prod Issue" (2026-08-06, search by scenario / short
  description / technical key), delegated_wow = "Delegated — Ways of
  Working" (2026-09-01, SINGLETON — only id `'main'`, no search branch:
  picking the type arms Move › immediately).
- **Reference fields + ⚡ Auto-file** [USER 2026-07-16]: `notes` gained
  optional `order_number`, `solman_id`, `jira_id`, `route_to` (core.py
  migration; set in the add/edit forms, shown as chips — the intended landing
  zone for a future Power Automate Teams import). "⚡ Auto-file" is a
  preview-then-confirm dialog (`GET /inbox/autofile/preview`,
  `POST /inbox/autofile/apply` — matches RECOMPUTED server-side on apply).
  Matching is FIELDS ONLY (no text scanning — deliberate v1), precedence
  `route_to > jira_id > solman_id > order_number`, the first PRESENT field
  decides with no fall-through; only UNAMBIGUOUS matches move (a solman id
  hitting both a jira ticket and a defect stays put, with the reason shown).
  Targets: the jira store (→ notes at `('jira', key)`) and defects; order
  numbers resolve via `order_details('jira')`, ecom rows,
  `defects.order_number`.
- **Quick route-to** [USER 2026-07-18]: a route-to combobox in every pending
  item's actions row (`POST /inbox/<id>/route` → `set_inbox_route`, route_to
  ONLY — other ref fields untouched), so items can be flagged
  Contact/Link/Follow-up for the ⚡ batch without opening the edit form.
  Selecting auto-submits.
- **Text search** [USER 2026-07-16]: live CLIENT-side filter (no route, no
  SQL) over heading + note text + attachment names + reference chips —
  deliberately not whole-card `textContent`, so button labels ("Edit") do not
  match everything. The count badge shows "shown / total" while filtering; ✕ /
  Escape clears; the box only renders when items exist.
- **Delete**: per-item Delete (confirm) → `POST /inbox/<id>/delete` removes the
  note, its attachment rows AND the files in `data/uploads`; the ✕ on a single
  thumbnail removes just that attachment.
- **Incoming buckets** [USER 2026-07-16]: `route_to = contact|link|followup`
  pushes an item to `(module, 'incoming')` — NEVER auto-connected to a row
  (explicit user decision). The Contacts / Links / Follow-ups list pages render
  `_incoming_section.html` ("Incoming (N)", amber, only when non-empty): per
  note a target search (reuses `/inbox/targets`) + "Attach ›"
  (`POST /incoming-notes/<id>/file` — type fixed to the note's own module,
  target validated) + delete. Helpers in `db/notes.py`.

## Rules & gotchas

- The page keeps its scroll position across edit/file/delete/route round-trips
  (sessionStorage save on submit + restore on load). The quick-route select
  saves explicitly, because a programmatic `form.submit()` fires no submit
  event.
- The markup contract of the search box is pinned by a test — changing the
  card structure silently breaks the filter otherwise.

## Related

`[[notes]]` · `[[contacts]]` · `[[links]]` · `[[follow-ups]]` · `[[shelf]]` ·
`[[topics]]` · `[[known-production-issues]]`
