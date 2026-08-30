# ECOM Gatekeeper

**Type:** mini app
**URL:** `/ecom-gatekeeper` · `/ecom-gatekeeper/ticket/<jira_key>` · `/ecom-gatekeeper/sales-report`
**Storage:** `app/db/gatekeeper.py` → `gatekeeper_annotations` (jira_key PK); tickets from `[[jira-store]]`; the legacy `ecom_gatekeeper` table in `db/core.py`
**Routes:** `app/web_ecom.py` + `app/web_reference.py` (legacy table)
**Templates:** `ecom_gatekeeper.html` · `gatekeeper_ticket.html` · `gatekeeper_sales_report.html` · `ecom_gatekeeper_detail.html`
**Tests:** `tests/test_gatekeeper_jira.py`, `tests/test_reporter_filters.py`

## Purpose

The Sales-facing pre-handoff check: which tickets are still being gatekept by
Marina, and which have gone back to Sales. It is the work context BEFORE a
ticket becomes MB work on the ECOM board.

## Architecture

- The **JIRA TICKETS table is THE current gatekeeper** [USER 2026-07-11]; the
  manual `ecom_gatekeeper` table is DEPRECATED (kept, collapsed at the bottom,
  still fully functional). "↻ Update from Jira" =
  `POST /ecom-gatekeeper/import-jira`, newest `.xml` from
  `jira_gatekeeper_folder`.
- **Board sections** — SALES-FACING work contexts [USER 2026-07-12]:
  "Active gatekeeping" (assigned to me AND status not in
  `jira_validation_statuses`, default 'In Validation' — covers first AND
  second checks) and "↩ Back with Sales" (assigned away; an "ECOM" badge when
  the ticket is also on the ECOM board; cancelled tickets stay visible here by
  decision). In-validation tickets LEAVE the board (they are MB work → the
  ECOM board); only an info count links over. **TRIPWIRE:** a red alarm box
  NAMES tickets that are in validation but NOT on the ECOM board — otherwise
  they would be invisible on both.
- **Per ticket row**: read-only Jira fields + an AUTHORED inline next step
  (blur-save, `POST /ecom-gatekeeper/ticket/<key>/next-step`) with the ↻/🕘
  archive buttons (`[[next-steps]]`), a Details link with note count, and an
  inline comments expander.
- **Ticket detail** `/ecom-gatekeeper/ticket/<jira_key>`: Jira card
  (status / assignee / epic / markets, open-in-Jira, extracted order numbers +
  source, acceptance criteria, description HTML, comment thread) + "My next
  step" + the full notes module. Notes/next-step entity type = `jira`
  (registry entries in `web_notes` and `web_next_steps`); inbox filing option
  "Gatekeeper ticket" (search by key / solman id / summary; the old
  `ecom_gatekeeper` type stays supported for legacy notes).
- **Order numbers report** on the gatekeeper page: Jira ID · Solman ID ·
  orders · source pill, copy-as-TSV (extraction rules in `[[jira-store]]`).

## The ECOM Sales report (v2, 2026-07-16)

`/ecom-gatekeeper/sales-report` — standalone print-ready page, v1 layout
deliberately KEPT ["I like it better"]. THREE sections:

- **With Sales** (green): `track_sales` ticked AND no longer assigned to Marina
- **With Marina** (rust): assigned + status in `jira_marina_statuses`
  (default In Progress / Ready for Verification / In Verification)
- **With MB** (blue): assigned + any other status

Columns: # · Jira ID (·E = on the ECOM board) · **Epic link** (browse URL built
from the ticket's own link with the key swapped; plain text when the epic field
is not a key — it replaced the Solman ID) · Summary (**🎉** in front when the
status is in `jira_passed_statuses`, default Done/Closed, or starts with
"Passed") · **Scenario** (from the matching ECOM board row by jira key, "—"
off-board) · Status · **Reporter** · Market · Order numbers · Next step.

**Filter bar** (screen-only — the filtered state is what prints): Reporter /
Status / Scenario dropdowns, AND-combined, per-section "x of y" counts +
Clear; plus column-header sorting per table. All client-side; rows carry
`data-reporter` / `-status` / `-scenario`.

**📣 track-sales checkbox** on EVERY jira row of the Gatekeeper AND ECOM boards
(AJAX `POST /ecom-gatekeeper/ticket/<key>/track-sales`, stored in
`gatekeeper_annotations.track_sales`, survives the handover) — tickable
proactively while a ticket is still with Marina/MB so nothing is lost when it
is reassigned; it only takes effect on the report once the ticket is
un-assigned. Editable 📣 call-out bullets on top (`report_comments` key
'sales'; blank ones hidden in print). Print (A4 landscape) + Download HTML.

**Per-reporter reports** [USER 2026-07-18]: `?reporter=<short name>` serves the
SAME report with only that reporter's tickets, SERVER-side (print, download and
filename follow; the title gets "— Phalk"). Expected reporters = config
`ecom_reporters` (default Phalk + Calvin), matched case-insensitively as
substrings of the Jira "Lastname, Firstname" value — helper `app/reporters.py`.
Toolbar All/Phalk/Calvin switcher + 📄 links in the page header; the gatekeeper
page and the ECOM board each have a reporter dropdown filter (GET `reporter`).

## Related

`[[jira-store]]` · `[[ecom]]` · `[[order-details]]` · `[[next-steps]]` ·
`[[notes]]` · `[[row-validations]]` · `[[delegated]]`
