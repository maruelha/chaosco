# CS Follow-Up Tracker

**Type:** mini app
**URL:** `/cs_followups` · `/cs_followups/new` · `/cs_followups/<id>` (+ `/status`, `/delete`)
**Storage:** `app/db/planning.py` over `db/core.py` → `cs_followups`
**Routes:** `app/web_planning.py`
**Templates:** `cs_followup_list.html` · `cs_followup_detail.html`

## Purpose

Core South TOPICS that need attention before go-live — the sign-off-facing
tracker. One of three deliberately distinct lists [USER 2026-07-05]:

| List | What it holds |
|---|---|
| `cs_followups` (here) | topics needing attention before go-live |
| `[[follow-ups]]` | what OTHERS promised Marina (the chase list) |
| promises (planned) | what Marina promised others |

**Do not consolidate them.**

## Architecture

**Columns**: `area`, `jira_id`, `topic` (NOT NULL), `description`, `next_step`,
`with_whom`, `status`, timestamps. `CS_FOLLOWUP_STATUSES` = `open` ·
`in_progress` · `done`.

- **List**: multi-select filters for area, with_whom and status, plus
  `?done=1` to include done items (hidden by default). Filter options come from
  the values in use (`get_cs_followup_options`).
- **Status** flips inline via AJAX (`POST /cs_followups/<id>/status`), and the
  route validates against `CS_FOLLOWUP_STATUSES` — an unknown status is refused
  rather than stored.
- **Detail** page: the full form plus the shared notes section (registry key
  `cs_followup`) and a Teams ping button (`[[teams-ping]]`, registered entity).
  `/cs_followups/new` renders the same template with `is_new=True`.

## Rules & gotchas

- Richer than `[[follow-ups]]` on purpose: it carries a description, a next step
  AND a Jira id, because these items end up in sign-off discussions.

## Related

`[[follow-ups]]` · `[[teams-ping]]` · `[[notes]]` · `[[spillover]]`
