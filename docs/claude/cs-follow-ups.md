# CS Follow-Up Tracker

**Type:** mini app
**URL:** `/cs_followups`
**Storage:** `app/db/core.py` → `cs_followups`
**Routes:** `app/web_planning.py`
**Templates:** `cs_followup_list.html` · `cs_followup_detail.html`

## Purpose

Core South TOPICS that need attention before go-live — by area and Jira id,
with next steps, an owner and notes. The richer sign-off-facing counterpart to
`[[follow-ups]]` (which is the personal chase list) [USER 2026-07-05: three
deliberately distinct trackers, do not consolidate].

## Architecture

List + detail page with the shared notes section; registry key `cs_followup`
for notes and for the Teams ping button.

## Related

`[[follow-ups]]` · `[[teams-ping]]` · `[[notes]]`
