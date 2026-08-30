# Follow-ups

**Type:** mini app
**URL:** `/followups` (+ detail page, `/options/...` for the pick lists)
**Storage:** `app/db/core.py` → `followups`, `followup_options`
**Routes:** `app/web_planning.py`
**Templates:** `followup_list.html` · `followup_detail.html` · `_incoming_section.html`
**Tests:** `tests/test_followup_options.py`

## Purpose

What OTHERS promised MARINA — the chase list. Deliberately distinct from
`[[cs-follow-ups]]` (topics needing attention before go-live) and from the
planned "promises" tracker (what Marina promised others) [USER 2026-07-05:
do not consolidate].

## Architecture

Lightweight per-person list plus a detail page with the shared notes section
and a Teams ping button (`[[teams-ping]]`). Incoming inbox items routed to
`followup` land in the amber "Incoming" section at the top of the list.

**Pick lists, not free text** [USER 2026-08-11] — "right now I have 5 spellings
for one group and that is cumbersome": "With whom" and "Group" are chosen from
`followup_options` (one row per entry, `kind` = `person` | `group`). An entry
may stand for several people — it is ONE entity to her, so a follow-up holds
exactly one value, **strictly no free text**. Maintained in the grey "Lists"
section at the top of `/followups`:

- add
- rename (`…/options/<id>/rename` updates every follow-up using the old
  value; renaming ONTO an existing entry MERGES the two — that is the
  de-duplication tool)
- delete (removes the list entry only; existing rows keep their text)

Values already in use were seeded into the lists once (migration in
`db/core.py`); a row whose value later leaves the list keeps it, and the edit
dialog re-offers it as "(not on the list)".

## Rules & gotchas

- The status `<select>` carries `name="fu-status-<id>"` + `autocomplete="off"`
  — the same position-restore bug as the payment tracker: after a row went to
  done and dropped out of the list, the browser painted "Done" onto the next
  row on reload.

## Related

`[[cs-follow-ups]]` · `[[contacts]]` · `[[teams-ping]]` · `[[inbox]]` ·
`[[meeting-prep]]`
