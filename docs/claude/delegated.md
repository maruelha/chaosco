# Delegated Testing (2026-08-26)

The card for testing work DELEGATED to the team. Its own Jira XML export,
uploaded as a file on the card; tickets bucketed by status/assignee from
🔴 BLOCKED down to "Ready for Sales validations".

## Design decisions (planning chat 2026-08-26)

- **Own Jira export, SHARED store.** The upload tags every ticket in the
  file `seen_in_delegated` in `jira_issues` (third source tag next to
  gatekeeper/ecom). No filtering — the export itself defines the scope.
  Shared-store refresh rules apply (status, assignee, acceptance criteria
  refresh; comments replaced wholesale). A ticket may carry several tags —
  one import refreshes every view.
- **File upload, not a watched folder** [USER]: like ECOMTestPlan — the
  browser uploads the file's content (`<input type="file">`), so there is
  no per-machine folder config and it would survive future hosting. A dated
  copy is kept: `data/uploads/delegated_jira_<timestamp>.xml` (mirrored by
  the backup). The watched-folder + tkinter-Browse ideas were discussed and
  rejected.
- **Order numbers: LATEST COMMENT only** [USER] — `extract_latest_comment_orders`
  in `app/jira_importer.py`; acceptance criteria deliberately ignored
  (unlike the gatekeeper's acceptance-criteria-first rule). Comment bodies
  are stored as HTML, so they are flattened (tags → spaces, entities
  decoded) before the regexes run — without that, markup between label and
  value made extraction find nothing [USER 2026-08-26]. The gatekeeper's
  comment fallback got the same flattening. Delegated order shapes [USER]:
  three OR four capitals + digits (ASK0342321 / ASKR0342321) and bare
  numbers starting 6000 (6000084252) — both in the shared `_ORDER_TOKEN_RE`.
- **Order details component**: the shared `_order_details.html` dialog at
  `('jira', jira_key)` — Orders button per board row (S4 ✓ tick) + a card
  on the ticket detail page; SAME rows as the Gatekeeper/ECOM boards.
- **Authored fields separate from the gatekeeper.** `delegated_annotations`
  (jira_key PK, blocked_reason, next_step) in `app/db/delegated.py`. Same
  jira_key can hold a gatekeeper next step AND a delegated next step —
  different working contexts. Next-step archive entity: `delegated`.
  Notes entity: `delegated` (own thread, separate from gatekeeper `jira`).
- **Report duplication accepted** [USER]: `delegated_report.html` is a COPY
  of the sales-report layout — the two reports are expected to grow apart
  (still experimenting). Extract a shared partial only if they stabilise.

## Buckets (app/delegated_buckets.py — pure, tested)

| Bucket | Rule |
|---|---|
| 🔴 BLOCKED (top, wins) | status Blocked |
| Open | status Open |
| In progress with testing team | In Progress, not Marina |
| Gatekeeper check Marina | In Progress + `jira_gatekeeper_assignee` substring |
| Waiting for Settlementfile creation | In Verification |
| In validation with GBS key users | In Validation |
| Ready for Sales validations | In Review |
| Resolved / Closed | Resolved / Closed / Done |
| Unexpected status | anything else (never silently dropped) |

Case-insensitive, whitespace-tolerant. Board hides Resolved+Unexpected
sections while empty; the report shows only non-empty sections.

## Pieces

- `app/db/delegated.py` — schema + all SQL (annotations, `delegated_counts`
  for the dashboard badge)
- `app/delegated_buckets.py` — bucket rules + counts (backlog joins here later)
- `app/web_delegated.py` — Blueprint `/delegated/`: board, upload, ticket
  detail (Details/Messages tabs), inline saves, `/report`, `/numbers` +
  `/report/download`, `/numbers/download` (dated standalone HTML — the
  templates render with `download=True`, which drops toolbar/filter
  bar/scripts and shows call-outs as static text; CSS is inline anyway —
  in-app pages keep all their buttons, only the downloads are stripped
  [USER 2026-08-26]). `report_context`/`numbers_context` are shared with
  `report_exporter.py`: the dashboard Export Reports card also writes
  `delegated_report_<date>.html` + `delegated_numbers_<date>.html`.
  Both reports are also Email Reports attachments (`emailer.REPORT_CHOICES`
  keys `delegated` / `delegated_numbers` — gather_attachments fetches the
  download routes, already-clean HTML) [USER 2026-08-26].
- Templates: `delegated.html`, `delegated_ticket.html`,
  `delegated_report.html` (call-outs key `delegated`), `delegated_numbers.html`
- Registries: `web_notes.REGISTRY['delegated']`,
  `web_next_steps.REGISTRY['delegated']`
- Tests: `tests/test_delegated_buckets.py`, `tests/test_delegated_web.py`

## Blockers (planning chat + build step 2026-08-27)

Own entity, own module (`app/db/blockers.py` + `app/web_blockers.py`,
Blueprint `/blockers/`) — a defect, task or business clarification that
blocks one or more delegated tickets. Design decisions:

- **Own table, not free text.** A blocker (e.g. a pricing defect) commonly
  blocks several tickets — modelling it as per-ticket `blocked_reason` text
  would mean retyping the same defect and never being able to ask "what
  does S4DEF-1 block?". `blockers` (id, type, name, jira_key) is the
  BLOCKER; `blocker_links` (m:n to delegated jira_key) is the "attach to
  tickets" step — schema exists, UI comes in build step 8.
- **Three types, fixed order everywhere**: Defects → Tasks → Business
  Clarifications (`db_blockers.TYPE_SECTIONS`). Clarifications never carry
  a jira key — just a name (`_clean_jira_key` strips it even if posted).
- **No separate upload/import.** A defect/task blocker's live status,
  description and comments come from the SAME shared jira store the
  delegated card already refreshes — Marina extends her delegated Jira
  filter to include the blocker issues, and the existing
  `POST /delegated/upload` keeps them current by key, same as any other
  ticket [USER 2026-08-27].
- **Excluded from the delegated board.** A jira key registered as a
  blocker is filtered out in `web_delegated._load_issues` (the board,
  status report and numbers all route through it) — a blocking defect must
  not also appear as a testing ticket to work through. It only lives on
  the Blockers page.
- **"Why blocked" stays as-is for now** [USER 2026-08-27] — decide later
  whether structured blockers replace that free-text field.
- Notes: registry entity `blocker` (own thread, `_notes_section.html`).
- Links: dashboard "Delegated Testing" card + the board toolbar both carry
  a 🚧 Blockers button.
- Tests: `tests/test_blockers.py` (storage, list/detail pages, notes,
  board-exclusion).

Next build steps (see `docs/build_plan.md`): 8 attach blockers to tickets
(picker + chips + `counts_toward_goal` flag), 9 blocker filter/chips on the
status report, 10 Management Summary blocker overview + weekly goal.

## PARKED — explicitly pushed to later [USER 2026-08-26]

1. **Excel/ECOM info join**: the `ecom` table rows (filled by the ROE
   tracking import) matched by Jira key, so the board/detail also shows the
   Excel-side info next to the Jira data. Marina was "not quite sure" about
   this — re-discuss scope before building.
2. **Backlog items**: manually managed items that are COUNTED in the
   numbers report but NOT listed in any detail view. Likely a small
   `delegated_backlog` table; the counting seam is
   `delegated_buckets.bucket_counts` (add backlog counts onto the bucket
   counts there). Will "get more complex" per Marina — expect follow-up
   requirements when she brings it back.
