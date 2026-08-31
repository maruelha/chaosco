# Delegated Testing (2026-08-26)

**Type:** mini app
**URL:** `/delegated/` · `/delegated/report` · `/delegated/numbers` · `/delegated/overview` · `/delegated/ticket/<jira_key>` · `/blockers/`
**Storage:** `app/db/delegated.py` → `delegated_annotations`, `delegated_goal` · `app/db/blockers.py` → `blockers`, `blocker_links`; tickets from the shared Jira store
**Routes:** `app/web_delegated.py` · `app/web_blockers.py`; bucket rules in `app/delegated_buckets.py`
**Templates:** `delegated.html` · `delegated_report.html` · `delegated_numbers.html` · `delegated_overview.html` · `delegated_ticket.html` · `blockers.html` · `blocker_detail.html` · `_blocker_picker.html`
**Tests:** `tests/test_delegated_buckets.py`, `tests/test_delegated_web.py`, `tests/test_blockers.py`

## Purpose

The card for testing work DELEGATED to the team. Its own Jira XML export,
uploaded as a file on the card; tickets bucketed by status/assignee from
🔴 Blocker down to "Test case completed" (wording rewritten 2026-08-31,
see below).

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
| 🔴 Blocker (top, wins) | status Blocked |
| Not started yet | status Open **or Reopened** (2026-09-01 [USER]) |
| Testing team creating order | status Accepted |
| Marina gatekeeper check | status In Progress |
| Settlement file to be created | In Verification |
| With GBS key users | In Validation |
| ECOM BPO test | In Review |
| Test case completed | Resolved / Closed / Done |
| Unexpected status | anything else (never silently dropped — and since
2026-09-01 the reports NAME the status, see below) |

Case-insensitive, whitespace-tolerant. Board hides Resolved+Unexpected
sections while empty; the report shows only non-empty sections.

**Status workflow + wording rewritten 2026-08-31 [USER]** — the workflow
the team agreed that day: `Accepted` = the testing team is creating the
order, `In Progress` = with Marina for the first check. The **assignee no
longer decides a bucket**: `bucket_key`/`bucket_issues`/`bucket_counts`/
`staged_counts` lost their `me` argument and `web_delegated._me()` is
gone. Both sections stay [USER: "the sections still stay"] — they are just
fed by different statuses. The wording above is Marina's own (she corrected
a first draft: "Issue" → **Blocker**, "With Marina for first check" →
**Marina gatekeeper check**, "With Flora" → **ECOM BPO test**). `Accepted`
joins the **Until Gatekeeper Check** stage of the Management Summary, so it
does NOT count toward the weekly goal — to be re-confirmed [USER: "need to
confirm that - but for now.."].

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

## Delegated Testing Overview (2026-08-31 [USER]) — the management report

Third report, `/delegated/overview` + `/delegated/overview/download`,
template `delegated_overview.html`, context `overview_context` (shared with
`report_exporter`). ADDED next to the status report and the Management
Summary — the three are expected to stay separate. Built to Marina's own
mockup (designed in a Claude chat, brought in as a screenshot).

**Pipeline by stage** — four cards, each with a big stage total, an owner
line, and TWO lines underneath:

| Card | Owner | In progress (Jira status) | Blocked (blocker's team) |
|---|---|---|---|
| TECH TEST EXECUTION | Sales Tech | Open · Accepted | `Sales*` · PDM · Omni |
| MB EXECUTION & VERIFICATION | MB | In Progress · In Verification · In Validation | DTC O2C · MB BIZ |
| ECOM BPO VERIFICATION | ECOM BPO | In Review | Kibana · ECOM BPO |
| COMPLETE | — | Resolved · Closed | — |

A BLOCKED ticket's status says nothing about who has to move, so it is
staged by the **responsible team of its blocker** instead [USER]. Several
blocker teams on one ticket → the EARLIEST stage wins, so a ticket is
counted exactly once and the pipeline keeps adding up. `Kibana` and
`ECOM BPO` joined `db_blockers.FIXED_TEAMS` for this.

**Execution status** — the mockup's four-group stacked bar [USER: "I want
to keep the mockups stages as that is what the manager wants"]: Passed
(done) · In Progress (accepted/marina/settlement/gbs/sales) · Blocked ·
Not Started (open). Marina listed `Open` under both In Progress and Not
Started; resolved as Not Started, since "Open → not started yet" is fixed.

**Blockers by team** — the open blockers (`_open_blockers`, shared with the
Management Summary so the two can never disagree), grouped by team instead
of by type: fixed teams in combobox order, then custom ones, "No team
assigned" last. Empty teams are left out entirely.

**Invariant, held by the tests:** stages + `blocked_unassigned` +
`unexpected` == `total` == the sum of the bar. Tickets that belong to no
stage ("team not assigned", "unexpected status") get their own amber line —
rendered ONLY when non-zero [USER: "if it is empty dont show as
placeholder"], so a clean report shows nothing there at all.

Backlog tickets are excluded, like on the Management Summary. **No goal
box** for now [USER: "I dont know what management wants there"] — revisit.
Editable 📣 call-outs on their own key `delegated_overview` (allowlisted in
`web_reports.report_comment_add`). Download + Export Reports (7th file) +
Email Reports choice `delegated_overview`, same as the other two.

Pure logic in `app/delegated_buckets.py`: `OVERVIEW_STAGES`,
`overview_team_stage`, `blocked_stage`, `BAR_GROUPS`, `overview_counts`.

## Odd statuses are NAMED, not just counted (2026-09-01 [USER])

[USER: "when there is an unexpected Jira status mention what the status is
so one does not need to research"]. `delegated_buckets.unexpected_statuses`
(pure, tested) returns `[(status, count), …]` for everything in the
Unexpected bucket, most frequent first; a missing/blank status is reported
as `(no status)` rather than as an empty label. Both aggregate reports use
it — the Management Summary appends "— Ready for Verification ×2" to its
Unexpected row, the Overview names them in its amber note line. The board
and the status report already showed each ticket's Status in a column, so
they were not the gap.

Adding a status to the workflow is therefore a two-line change in
`delegated_buckets` (the `bucket_key` branch + the docs) — and until it is
made, the reports say out loud what they could not place.

## Jira labels (2026-08-28 [USER: "would help while filtering"])

The XML export's `<labels><label>…</label></labels>` import into
`jira_labels` (shared jira store, one row per (jira_key, label),
**replaced per import like the comments** — but only when the parsed
dict carries a `labels` key, so older callers can't wipe stored ones).
`db_jira.labels_for_issues(conn, keys)` batches them;
`web_delegated._load_issues` attaches `i["labels"]` (alphabetical).
UI: small gray chips next to the Summary on the board and the status
report; a "Label: all" dropdown filterbar on the board
(`dlgFilterLabel()`, rows carry `data-labels` space-joined — Jira labels
never contain spaces) and an rf-label select in the report's filter bar
(AND-combines with status/assignee/blocker); the ticket detail lists
them in the Details tab.

## MB tracking join (2026-08-28 [USER], resolves parked item 5)

The ECOM tab of `DTC_UAT_testtracking_ROE` already imports into the
shared `ecom` table (unique match key = normalized Jira ID → the join to
a delegated ticket is 1:1). New pieces:

- **⤒ MB tracking upload** on the board: picks the workbook (filename
  must contain `testtracking` or the configured `filename_stem`), runs
  ONLY the ECOM-tab import (`parse_ecom(xlsx_path=…)` + the same
  `upsert_ecom_rows` the dashboard Import uses, dated copy
  `delegated_tracking_*.xlsx`). CONSEQUENCE BY DESIGN: also refreshes
  what the ECOM board/reports show — one store. Schema init reads
  `_cfg["database_path"]` at call time (NOT the module `_db_path`) so it
  hits the same DB as `_get_conn` under test monkeypatching.
- **MB Status column** on the board, only in the four buckets with
  expectations (`delegated_buckets.MB_EXPECTED`, [USER wordings]):
  blocked → "Blocked - returned to Sales"/"Blocked DTC"; settlement →
  empty/"Not Ready"; gbs → "In Progress"/"clarification needed"; sales →
  "Passed"/"Conditionally Passed". `mb_status_state()` → ''/'none'/'ok'/
  'mismatch' (normalized: casefold, whitespace, en/em dashes). Only a
  MISMATCH gets color (red chip, [USER: "a color to show if the status
  does not match"]); ok renders plain, no ECOM row renders a neutral —
  ("not tracked is not wrong"). Wordings adjustable in MB_EXPECTED.
- **"MB tracking (ECOM tab)" card** on the ticket detail (read-only,
  shown only when a row matches): Test Case ID, Testcase name, MB
  Status, Defect ID, S4 Sales order/Billing documents/Journal invoice
  entry, Reason for pass with reservation, MB Comments + a link to the
  row's ECOM detail page. Report/Management Summary deliberately
  untouched [USER].

## Report tweaks + call-out archive (2026-08-28, second batch [USER])

- Status report blocker chips are **id-only** (jira key → BC id → name
  fallback, full name in the tooltip) — same rule as the board chips.
- **Impact column on the Blockers list page** too (inline blur-save via
  the same `POST /blockers/<id>/impact`), right after ID — "see at a
  glance what functionality is blocked".
- **Call-out archive** (status report): `report_comments.archived_at`
  migration (in db/core.py); `list_report_comments` now returns LIVE
  ones only (all reports), `archive_report_comment` +
  `list_archived_report_comments` in db/reference.py;
  `POST /report-comments/<id>/archive` in web_reports.py. Each call-out
  gets a 🗄 button (screen only); archived ones show in a collapsed
  "🗄 Archived call-outs" expander with their dates ("<created> →
  archived <date>") — [USER: "saved for the date"]. The download shows
  live call-outs only, no archive section. Numbers-page call-outs can
  get the same treatment on request — not asked yet.

## Responsible team per blocker + Mgmt Summary call-out archive (2026-08-28, third batch [USER])

- `blockers.team` (migration). Combobox = `FIXED_TEAMS` (Sales BIZ ·
  Omni · DTC O2C · PDM · MB BIZ) + every custom "Other" value already in
  use (`team_options`, case-insensitively deduped) — [USER: "once added
  it appears in the combobox"]. Detail form: select + Other… text field
  (`team='__other__'` + `team_other`); Blockers list: inline select per
  row (Other… uses a prompt, saves via `POST /blockers/<id>/team`,
  reloads so the new value joins every combobox). Visible: Blockers
  list column, Mgmt Summary blocker overview column, and "· team" suffix
  on the board/report blocker chips (id stays first).
- Call-out archive extended to the **Management Summary** ("especially
  there"): same 🗄 button / archived expander / live-only download as
  the status report, key `delegated_numbers`.

## Board slimming + MB follow-ups (2026-08-28, fourth batch [USER:
"content is cut off - maybe too many columns"])

- OFF the board, detail page only: label chips (the Label FILTER stays —
  rows keep `data-labels`), the Orders column (latest-comment orders),
  the Why-blocked input, the 💬 chat + ✉️ message buttons (their
  includes/JS removed from the board template; `dlgBrSave` gone).
  The Orders POPUP button (shared order-details) stays.
- `MB_EXPECTED["gbs"]` also accepts **"Ready for Validation"** [USER].
- MB join hardened: `ecom_rows_for_jira_keys` falls back to a TOKEN scan
  (regex `[A-Za-z][A-Za-z0-9]*-\d+` over the stored Jira-ID cells) for
  keys the exact match misses — the workbook cell sometimes carries more
  than the bare key, which was the likely cause of [USER: "mb status did
  not update for all the tickets"]. The ⤒ MB tracking upload result now
  says "MB rows match X of Y board tickets" so a mismatch is visible at
  upload time.
- Blockers LIST: Notes column removed [USER]; Mgmt Summary blocker
  overview gained a **Next step** column (the blocker's own next step).

## Board pass two + report/summary layout (2026-08-28, fifth batch [USER])

- BLOCKED section: **no Next step column** ("I need the next step for
  the blockers - not for the blocked test cases") — blocked tickets'
  next step stays editable on the detail page; other sections keep the
  inline field + ↻/🕘.
- Orders COLUMN restored ("I like those"); the Orders POPUP button left
  the board instead (detail page keeps it, `_order_details.html`
  include removed from the board template).
- Status report: labels removed entirely (chips + rf-label filter +
  `filter_options.labels`) ["not interesting"]; `.rpt-section` got
  `width: fit-content; min-width: 100%` so the colored section head
  spans the full BLOCKED table width instead of stopping at the
  viewport.
- Management Summary: body max-width 820px → 1150px ("why is it so
  thin?"); blocker overview reordered to Name · **Impact (2nd)** · ID
  (jira_key **or the BC display id**) · Team · Next step · Blocks.
- Labels in the ticket detail need a FRESH XML upload to show — they
  only enter `jira_labels` at import time (the row renders "—" until
  then).

## Blocker impact on the Management Summary (2026-08-28)

The blocker `impact` field ("what is blocked", already on the blocker
detail form) is now a column in `/delegated/numbers`' Blocker overview —
**inline-editable** on screen (dashed-underline input, blur-saves via
`POST /blockers/<id>/impact`, only-field `set_blocker_impact`), static
text in the download snapshot. [USER: "so one can see at a glance what
is blocked".]

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

## ReqTool checkbox (2026-08-29 [USER])

Dashboard-only authored flag, own column `delegated_annotations.req_tool`
(same only-this-field upsert pattern as `backlog`/`counts_toward_goal`,
`app/db/delegated.py`). Checkbox on every board row + the ticket detail
form (`POST /delegated/ticket/<key>/req-tool`); a "ReqTool: all / checked /
unchecked" dropdown in the board filter bar (`data-reqtool` per row,
combined client-side with the Label filter in one `dlgFilterBoard()`).
**Deliberately excluded from `report_context`/`numbers_context`** — [USER:
"no report - it is ONLY on the dashboard"], so neither the status report
nor the Management Summary reads it.

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

## Related

`[[jira-store]]` · `[[gatekeeper]]` · `[[ecom]]` · `[[email-reports]]` ·
`[[report-blocks]]` · `[[notes]]` · `[[next-steps]]` · `[[teams-chats]]`
