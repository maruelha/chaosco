# Encouragements

**Type:** mini app
**URL:** `/encouragements` (+ `/add`, `/<id>/delivered`, `/<id>/delete`)
**Storage:** `app/db/reference.py` over `db/core.py` → `encouragements`, `encouragement_people`
**Routes:** `app/web_reference.py`
**Templates:** `encouragements.html`

## Purpose

Positive observations about people, with a delivered flag — so appreciation is
actually SAID and not just thought. The dashboard badge counts the undelivered
ones, which is the entire point of the module.

## Architecture

Two tables: `encouragement_people` (name, UNIQUE) and `encouragements`
(`person_id` FK, `text`, `date`, `delivered` 0/1, `created_at`).

- **Adding** takes a person NAME, not an id:
  `get_or_create_encouragement_person` looks the name up and creates it if it is
  new, so the list of people grows by itself and nobody has to maintain it. The
  date defaults to today.
- The list can be filtered to one person (`?person_id=`), and the page shows
  that person's name when filtered.
- **Delivered** is an AJAX toggle (`POST /encouragements/<id>/delivered`,
  accepts JSON `{value: bool}` or a form field) — a delivered item leaves the
  dashboard count but stays in the list.
- Each item has a copy button so the text can be pasted into a chat, a review
  or a message.

## Rules & gotchas

- The people table exists only to de-duplicate names; there is no link to
  `[[contacts]]`. A person here is a name, nothing else.

## Related

`[[contacts]]` · `[[teams-ping]]`
