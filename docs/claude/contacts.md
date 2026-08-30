# Contacts

**Type:** mini app
**URL:** `/contacts` · `/contacts/new` · `/contacts/<id>` (+ `/delete`)
**Storage:** `app/db/reference.py` over `db/core.py` → `contacts`
**Routes:** `app/web_reference.py`
**Templates:** `contacts.html` · `contact_detail.html` · `_incoming_section.html`

## Purpose

The contact directory — who is who, in which area, for which topic. It is also
the address book that the Teams ping page reads, so a chat can be opened from a
row without looking an address up anywhere else.

## Architecture

**Columns**: `name` (NOT NULL), `email`, `area`, `topic`, `comments`, `tags`,
timestamps.

- **List**: multi-select filters for area, topic and tags plus a free-text
  search (`get_contact_options`).
- **Detail**: the form plus the shared notes section (registry key `contact`).
- **Incoming**: inbox items routed to `contact` land in the amber
  `_incoming_section.html` block at the top of the list (`[[inbox]]`).
- **Teams ping integration** (`[[teams-ping]]`): `find_contact_email` matches a
  row's person by NAME to pre-fill the recipient; "Save to contacts" writes an
  address back through `upsert_contact_email`, which updates a name-matched
  contact or creates a minimal one — so the next ping pre-fills by itself.

## Rules & gotchas

- The name is the join key for the Teams lookup: a person spelled two ways is
  two contacts, and the ping page will only pre-fill one of them.

## Related

`[[teams-ping]]` · `[[follow-ups]]` · `[[cs-follow-ups]]` · `[[inbox]]` ·
`[[encouragements]]`
