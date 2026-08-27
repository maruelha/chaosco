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

**Only user stories (2026-08-27)** [USER: "the main page should only have
jira user stories"]: the export deliberately also carries the blocker
DEFECT issues (see Blockers: one upload refreshes everything), so
`_load_issues` additionally drops every issue whose Jira `type` isn't a
story — registered as a blocker or not. Story matches by **SUBSTRING**
(`db_delegated.is_story_type`: "Story", "User Story", … —
case-insensitive; the first version compared exactly to 'story' and
EMPTIED Marina's real board because her Jira wording differed, fixed
same day). NULL type (export without `<type>`) is tolerated as a story
rather than silently dropped, and the board shows a "🛈 Not shown (not a
user story): <type> ×n" hint line (`_hidden_non_story`) so the filter
can never empty the page silently again — registered blockers don't
count as "hidden" (they live on the Blockers page by design). The
dashboard badge (`db_delegated.delegated_counts`) mirrors the same rule
(stories only, blockers excluded) so badge and board always agree. The
upsert refresh also writes `type` since 2026-08-27, so one normal upload
backfills rows imported without one ("can this be fixed for already
uploaded issues?" — yes).

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
  BLOCKER; `blocker_links` (m:n to delegated jira_key) is the attach-to-
  tickets step — live since build step 8 (2026-08-27).
- **Attach picker (step 8).** `_blocker_picker.html` — same drop-in AJAX
  dialog pattern as `_order_details.html`: one opening button
  (`data-jira-key` + `data-blk-name`), no per-page context wiring. On the
  board's blocked rows + the ticket detail page: attach an existing
  blocker, detach one, or quick-create-and-attach in one step (type, name,
  jira key — "add name+key+type while attaching" [USER 2026-08-27]).
  Chips (name + jira key) render inline via `blockers_for_tickets` (one
  batch query for the whole board) / `list_blockers_for_ticket` (detail).
- **`counts_toward_goal`** (step 8) — per-ticket authored flag on
  `delegated_annotations`, checkbox on blocked board rows + the detail
  form, shown/editable only when blocked or already set (same convention
  as "Why blocked"). Depends on WHERE the defect was found, so it is NOT
  derived from status [USER 2026-08-27]. Toggle route
  `POST /delegated/ticket/<key>/counts-toward-goal`; feeds the weekly goal
  actual in the Management Summary (build step 10).
- **Three types, fixed order everywhere**: Defects → Tasks → Business
  Clarifications (`db_blockers.TYPE_SECTIONS`). Clarifications never carry
  a jira key — just a name (`_clean_jira_key` strips it even if posted).
- **No separate upload/import.** A defect/task blocker's live status,
  description and comments come from the SAME shared jira store the
  delegated card already refreshes — Marina extends her delegated Jira
  filter to include the blocker issues, and the existing
  `POST /delegated/upload` keeps them current by key, same as any other
  ticket [USER 2026-08-27].
- **AUTO-REGISTER on upload (2026-08-27, second round)** [USER: "why cant
  i see all the defects I uploaded in the list of blockers?"]: every
  Defect/Bug/Task-type issue in the export becomes a blocker row
  automatically during `run_delegated_import` (`_blocker_type_for`:
  defect/bug→defect, task→task; name = summary, solman_id from the
  summary prefix) unless its key is already registered — re-upload never
  duplicates, and one normal upload backfills defects uploaded before
  this existed. Stories and other types (Epic, …) are never
  auto-registered; unhandled non-story types show in the board's 🛈
  hint. The upload flash message appends "· n blockers registered".
- **Excluded from the delegated board.** A jira key registered as a
  blocker is filtered out in `web_delegated._load_issues` (the board,
  status report and numbers all route through it) — a blocking defect must
  not also appear as a testing ticket to work through. It only lives on
  the Blockers page.
- **"Why blocked" stays as-is for now** [USER 2026-08-27] — decide later
  whether structured blockers replace that free-text field.
- **Fields batch (2026-08-27, second round)** [USER]: `comment` + `impact`
  free-text fields on every blocker; optional `solman_id` (UI shows it for
  Defects only; stored for tasks too so a type flip loses nothing;
  clarifications never keep it — same rule as the jira key). Business
  clarifications get a generated **`display_id` BC-001…** (assigned at
  creation, backfilled for existing rows oldest-first on startup, partial
  unique index; a row edited INTO a clarification gets its id then, an
  existing id is never regenerated).
- **Open/closed split** [USER: "focus on the open issues"]: closed =
  manually closed (`closed_at`, ✔ Close/↺ Reopen on list + detail) OR the
  jira ticket reached the done family (`db_blockers.DONE_FAMILY` =
  resolved/closed/done — auto, reopens itself if Jira reopens; a manual
  reopen cannot override the auto rule). The list page's type sections
  show only open blockers; closed ones collapse into a "✔ Closed" section
  at the bottom (with Type column; auto-closed rows show "(closed in
  Jira)" instead of a Reopen button). The **Management Summary's blocker
  overview lists only open blockers** [USER: "blockers should only show
  up if they are not closed"].
- **Id-only chips** [USER: "I only want to see the id (else everything
  explodes)"]: the chips on the board's blocked rows, the ticket detail
  and the picker's attached list show ONLY `chip_label` (jira key → BC id
  → name fallback) and are LINKS to the blocker's detail page; the full
  name lives in the tooltip (and next to the chip inside the picker
  dialog, where you need it to pick). The status report's chips keep
  name+key (static text; downloads can't link into the app).
- **Next steps on blockers** [USER]: `next_step` column on the blockers
  table, inline blur-save on list rows + detail page, ↻ archive / 🕘
  history via the generic component (registry entity `blocker`).
- **Management Summary call-outs** [USER: "add comments that appear on
  the report - noteworthy things"]: same 📣 component as the status
  report, own `report_comments` key `delegated_numbers` — editable on
  screen, static text in download/email. Found+fixed while wiring it:
  `web_reports.report_comment_add`'s allowlist never included
  `delegated`, so "+ Add call-out" on the delegated STATUS report had
  silently 400ed since 2026-08-26.
- Notes: registry entity `blocker` (own thread, `_notes_section.html`).
- Links: dashboard "Delegated Testing" card + the board toolbar both carry
  a 🚧 Blockers button.
- Tests: `tests/test_blockers.py` (storage, list/detail pages, notes,
  board-exclusion, attach/detach/quick-create, blocked_ticket_counts),
  `tests/test_delegated_web.py` (goal toggle, chips on board + detail).
- **Bug fixed 2026-08-27**: `blockers_for_tickets`' join selected both
  `l.jira_key` (the delegated ticket) and `b.jira_key` (the blocker's own,
  often NULL) under the same column name — the blocker's key silently
  overwrote the ticket key, crashing the board whenever an attached
  blocker had no jira_key of its own. Fixed with `AS ticket_key`; caught
  by `test_board_and_detail_show_attached_blocker_chip`.
- **Status report (step 9, 2026-08-27)**: blocked rows show the SAME
  chips (name + jira key), and a Blocker filter joins Status/Assignee in
  the screen-only filter bar — pick one, see only the tickets it blocks.
  Options list only blockers actually attached to a ticket in this
  report. The report's CSS is self-contained (not the app's
  `style.css`, so it stays a clean standalone download) — chips get
  their own `.rpt-blockers` style rather than reusing `.chip`. Chips
  render in every mode; the filter select sits inside the existing
  `{% if not download %}` filterbar block, so downloads/exports drop it
  automatically with zero extra code.
- **Management Summary (step 10, 2026-08-27)** — the Numbers page renamed
  ("Management Summary Status Report"; routes/keys/filenames stay
  `numbers`/`delegated_numbers` so exports/email keep working — only
  visible titles changed, incl. `emailer.REPORT_CHOICES` and the board/
  report "🔢 Numbers" links, now "📊 Management Summary"). Three pieces:
  - **Weekly goal**: ONE number, no history [USER 2026-08-27] —
    `delegated_goal` one-row table (`id=1`, portable
    `ON CONFLICT DO UPDATE`). Inline blur-save
    (`POST /delegated/numbers/goal`); the page updates Actual/Delta live
    via JS, no reload. Actual = Past-Gatekeeper-Check stage total +
    BLOCKED tickets flagged `counts_toward_goal` — "goal for the week is
    X CREATED TEST ORDERS" [USER 2026-08-27], not successful ones, so a
    ticket that reached settlement/GBS/sales/done counts regardless of
    its eventual outcome, same as a defect found early enough to flag.
  - **3-stage bucket view**: `delegated_buckets.staged_counts` (pure,
    tested) groups the 9 buckets into Blocked | Until Gatekeeper Check
    (open/team/marina) | Past Gatekeeper Check
    (settlement/gbs/sales/done); Unexpected status is reported outside
    any stage so it still can't silently disappear. Rendered as one
    table with bold stage-header rows + a stage-total row, rather than
    a 3-column layout — stays compact and print-friendly like the
    original table.
  - **Blocker overview**: Defects → Tasks → Business Clarifications
    (same `TYPE_SECTIONS` order as the Blockers page), each blocker's
    name, jira key and blocked-ticket count — `blocked_ticket_counts`
    reused from the Blockers list page, one source of truth.
  - Tests: `tests/test_delegated_buckets.py` (+2: `staged_counts`),
    `tests/test_delegated_web.py` (+2: goal save + actual calculation,
    stage/blocker-overview rendering). Also fixed along the way: 3
    label assertions gone stale from the rename, and a missing
    `db_blockers.init_schema` in the Export Reports test fixture — gave
    `list_blockers` the same missing-table tolerance as the rest of the
    module for consistency.

All four build-plan steps for Blockers + Management Summary (7–10) are
now done.

## PARKED — explicitly pushed to later [USER 2026-08-26]

1. **Excel/ECOM info join**: the `ecom` table rows (filled by the ROE
   tracking import) matched by Jira key, so the board/detail also shows the
   Excel-side info next to the Jira data. Marina was "not quite sure" about
   this — re-discuss scope before building.
2. ~~Backlog items~~ RESOLVED 2026-08-27 — the requirement came back
   INVERTED [USER: "define some open tickets as 'backlog' - and then they
   are in their own section 'backlog' - and do not appear on the
   management summary report"]: not extra counted-only items, but a
   per-ticket authored flag (`delegated_annotations.backlog`, checkbox on
   every board row + the ticket detail form). Flagged tickets land in a
   📦 Backlog section at the bottom of the board AND the status report
   (`bucket_key` returns `backlog` FIRST — wins even over Blocked), and
   are excluded from the Management Summary entirely (total, staged
   counts, goal actual — `numbers_context` filters them before
   `staged_counts`). Toggle `POST /delegated/ticket/<key>/backlog`
   (board checkbox reloads the page so the row visibly moves).
