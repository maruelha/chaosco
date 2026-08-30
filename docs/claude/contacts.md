# Contacts

**Type:** mini app
**URL:** `/contacts` (+ `/contacts/new`, detail page)
**Storage:** `app/db/core.py` → `contacts`
**Routes:** `app/web_reference.py`
**Templates:** `contacts.html` · `contact_detail.html` · `_incoming_section.html`

## Purpose

The contact directory — name, email, area, topic, tags — with notes per
contact. It is also the address book the Teams ping page reads.

## Architecture

List + detail page with the shared notes section (registry key `contact`).
Incoming inbox items routed to `contact` land in the amber "Incoming" section.
`[[teams-ping]]` looks an address up with `find_contact_email` (name match)
and writes one back with `upsert_contact_email` — updating a name-matched
contact or creating a minimal one — so the next ping pre-fills.

## Related

`[[teams-ping]]` · `[[follow-ups]]` · `[[inbox]]` · `[[notes]]`
