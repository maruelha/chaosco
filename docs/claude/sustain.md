# Core South Sustainphase Monitoring (`/sustain/`)

**Type:** mini app
**URL:** `/sustain/` · `/sustain/day/<day>/<stream>` · `/sustain/summary` (+ `/summary/<day>`)
**Storage:** `app/db/sustain.py` → `sustain_tasks`, `sustain_task_details`;
`app/db/sustain_callouts.py` → `sustain_callouts` (authored, own log — see
Call-outs section below)
**Routes:** `app/web_sustain.py`; importer `app/sustain_importer.py`;
call-outs routes `/sustain/callouts/add|<id>|<id>/status|<id>/delete|<id>/next-step`
(`<id>` = the detail page, GET + POST save)
**Templates:** `sustain.html` · `sustain_callout_detail.html` · `sustain_day.html` ·
`sustain_summary.html`
**Tests:** `tests/test_sustain_importer.py`, `tests/test_sustain_storage.py`,
`tests/test_sustain_web.py`, `tests/test_sustain_callouts_storage.py`,
`tests/test_sustain_callouts_web.py`, `tests/test_inbox_to_callout.py`

## Purpose

Daily GBS Operations checklist for the sustain phase (O2C DTC), one
workbook per date window. Built step-by-step per the build-plan section
"Core South Sustainphase Monitoring" (planning chat 2026-08-27, executed
autonomously the same day — Marina was away; open judgment calls are
flagged in `docs/marina_notes/MarinaCheckSoon.html`).

## Source workbook

Filename: `<prefix>DTC_GBS Operations_checklist.xlsx` — the prefix
changes per file (encodes the date window, e.g. `1_0109_0409-O2C`), so
the upload matches on the **suffix** `DTC_GBS Operations_checklist.xlsx`.

- One tab per stream per day: `Retail_<ISO date>` / `eCom_<ISO date>`
  (verified file: 8 tabs = Retail+eCom × 2026-09-01..04).
- **The header row moved [2026-08-31].** The September file dropped the
  "Duplicate this sheet…" instruction line, so headers are on row **5**
  and data starts at row **6** (was 6/7). The importer therefore
  **locates** the header row (column A == "Task ID", scanning rows 1–12)
  instead of hardcoding it — both layouts import, and a genuine structure
  drift is still loud (`ParseError`).
- Columns: A Task ID · B L4 Taxonomy · C Process/Task · D Cadence ·
  E Due Today · F Country · G Provider/Partner/Financial Account ·
  H–K France/Italy/Portugal/Spain Result · L Task Overall (formula,
  "DO NOT EDIT") · **M Comments/Observations [new 2026-08-31]**.
- **Column M** is free text ("Enter optional free-text comments in column
  M", row 4). It is imported into `comments` on both tables and shown, but
  it is **informational only — never part of a status**: the workbook's own
  Task Overall ignores M, so we do too. It is located by header name
  (substring "comment"), so older files without it simply import `NULL`.
- **Parent tasks** carry a Task ID at outline level 0. **Detail rows**
  ("↳ Detail check", one per country × provider/account/store) sit at
  outline level 1, collapsed in Excel; openpyxl exposes
  `row_dimensions[r].outline_level`, so the structure imports faithfully.
- Result-cell vocabulary: `OK` / `Pending` / `Not due` / `N/A` /
  `Review`, or **free text** — the team writes short issue notes directly
  into the cell (how-to in row 5). Free text is the discussion-point
  signal.
- The summary row (row 4 before, **row 3** now) holds the
  DUE/COMPLETED/PENDING/REVIEW `COUNTIFS` summaries; its last cell is a
  save-check ("Save file to check"). Cached formula values are only right
  after a save → **never trust the summary row or the rollup cells;
  recompute in Python** (see below).

### The workbook's own rollup logic (decoded from the formulas)

- Parent country cell H–K (parents WITH details, e.g. `H10`): over that
  country's **due** detail rows — none due → `N/A`, any blank →
  `Pending`, any value that is neither OK nor N/A (i.e. free text!) →
  `Review`, else `OK`.
- Task Overall `L`: Due `No` → `Not due`. `On occurrence` → all four
  cells blank → `No occurrence`, any `Review` → `Review`, any blank →
  `Pending`, else `OK`. Otherwise (due): any `Review` → `Review`, any
  `Pending` → `Pending`, any `OK` → `OK`, all four `N/A` → `N/A`, else
  `Pending` (this fallback is what makes blank-but-due = Pending).
- Summary row — **the definitions changed with the 2026-08-31 file**, and
  `summary_counts` follows them [USER 2026-08-31]:

  | | old file (row 4) | new file (row 3) |
  |---|---|---|
  | DUE | parents with E=Yes | `SUM(COMPLETED:REVIEW)` — i.e. due parents with L in {OK, Pending, Review}; **a due parent whose L is N/A drops out of the due population** |
  | COMPLETED | due parents with L in {OK, **N/A**} | due parents with L=**OK only** |
  | PENDING | due parents with L=Pending | unchanged |
  | REVIEW | **all** parents with L=Review | **due** parents with L=Review |

  Verified: the new `summary_counts` reproduces the new file's cached
  DUE/COMPLETED/PENDING on all 8 tabs exactly. Consequence to expect: a
  day imported from an *older* file now shows slightly lower due/completed
  than that old workbook's own row 4 — the new definitions are applied to
  all history, which is the point (one consistent trend line).
- `COUNTIF` matches case-insensitively → every comparison in our Python
  mirror does too (`casefold`).

## Storage — `app/db/sustain.py`

`sustain_tasks` / `sustain_task_details` (1:n via `task_pk`, technical
PKs, portable SQL; both gained `comments` on 2026-08-31 via the additive
`_MIGRATIONS` ALTERs in `init_schema`). Each upload calls `replace_day_stream` per tab, so
consecutive files with different date windows **accumulate history**;
re-uploading a tab replaces it. Import tables only — never user-authored
data. Registered in the `database.py` facade; `init_schema` called from
`app/web.py` and the importer.

Classification (pure functions, tested in
`tests/test_sustain_storage.py`):

- `derive_country_cell(details, country)` — mirror of the H–K rollup.
- `derive_cells(task)` — the four FR/IT/PT/ES cells: rolled up from
  details if the task has any, its own literal cells otherwise.
- `derive_overall(due_today, cells)` — mirror of the L formula.
- `is_free_text(value)` — non-blank and outside the vocabulary.
- `task_status(task)` → `done | pending | attention | not_due`.
  Excel-faithful **except one deliberate deviation**: any free-text
  result cell forces `attention`. (Excel's L lets free text on a simple
  parent fall through to OK if another country is OK — an issue note must
  never hide behind an OK elsewhere in the row.)
- `summary_counts(conn, day, stream)` → recomputed
  due/completed/pending/attention, per the **new** definitions above:
  DUE = due parents whose recomputed Overall is OK/Pending/Review,
  COMPLETED = Overall OK, PENDING = Overall Pending. The deviation stands:
  a task classified `attention` counts in neither completed nor pending,
  and attention still counts over ALL parents — an on-occurrence issue
  must surface too, even though the workbook now restricts its REVIEW
  count to due tasks [USER 2026-08-31].
- `comment_items(conn, day, stream)` → every non-blank column-M entry of
  a tab (parents and details), for the summary's comments table. Comments
  never influence a status or a count.
- `list_tabs` (day picker), `list_tasks` (workbook order, details
  attached), `task_count` (dashboard badge).

## Importer — `app/sustain_importer.py`

`parse_sustain_workbook` loads with `data_only=True` (cached cell values;
aggregations are recomputed in storage, never imported). Tab pattern
`(Retail|eCom)_<ISO date>` (case-insensitive) → (stream, day); other tabs
ignored. `_find_header_row` scans rows 1–12 for column A == "Task ID"
(row 6 in the old files, row 5 since 2026-08-31) and raises `ParseError`
if it finds none — structure drift must still be loud.
`_find_comments_column` locates column M by header name past column L, so
the Comments/Observations text is imported when present and `None` when
not. Parent = row with Task ID;
detail = outline level ≥ 1 under the last parent; level-0 rows without a
Task ID are dropped. Task IDs arrive as text OR numbers → normalised to
text. `run_sustain_import` replaces each contained tab
(`replace_day_stream`) and returns ok/error + tabs/tasks/details counts.

Verified 2026-08-28 against the real `1_0109_0409` file: 8 tabs,
236 tasks, 2,720 details; recomputed due/completed/pending matched the
Excel's cached row 4 on all 8 tabs exactly.

Re-verified 2026-08-31 against the **new version of the same file**
(header row 5, column M): same 8 tabs / 236 tasks / 2,720 details, and
the recomputed due/completed/pending match its cached **row 3** on all 8
tabs exactly. The previous file still imports unchanged.

## Web — `app/web_sustain.py` (Blueprint `/sustain/`)

Upload on the card (Smoke pattern): file picker, dated `sustain_*.xlsx`
copy in `data/uploads/`, then `run_sustain_import`. Filename guard:
`.xlsx` AND the name must **contain** `DTC_GBS Operations_checklist`
(not end with it — browser " (1)" double-download copies must still
import; the prefix before `DTC_GBS` varies per file anyway). Import
result via `sustain_ok`/`sustain_msg` query params in a result-box.
Template `sustain.html`; the imported-days table (`list_tabs`) links each
(day, stream) to the day report.

### Call-outs (`app/db/sustain_callouts.py`, planning chat 2026-09-01)

Marina's own monitoring log, shown on the card page **above** the
imported-days table (`sustain.html`, `ui.section('Call-outs', 'amber', ...)`).
Own table `sustain_callouts` (channel, type, **name**, topic, ticket_no,
impact, responsible, status, date_captured, next_step) — deliberately
separate from `db/sustain.py`, never touched by the importer, same
separation as `sustain_issue_annotations` from `sustain_issues`.

**Short line vs. detail** [USER 2026-09-02, planning chat]: the list shows
only the short `name` (+ ticket no); `topic` (the longer text), `impact`
and `responsible` are edited on the **detail page** `/sustain/callouts/<id>`
(`sustain_callout_detail.html`, blocker-detail shape: full-row form,
status chip, next step with ↻/🕘, the shared notes component). Rows from
before 2026-09-02 were back-filled `name := topic` on `init_schema`; a
call-out created without a topic keeps `topic == name` until edited on
the detail page (storage rule in `create_callout`/`update_callout`).
`ticket_no` is free text (SUS-/ASPEN/Jira ids all fit) and deliberately
NOT in the global 🔍 widget — tickets live only here, the list's text
filter finds them [USER: "not really needed"].

- **channel** — `retail` / `ecom` / `both`, chip at the start of the row.
- **type** — fixed list `CALLOUT_TYPES`: Issue, Spotcheck, Observation,
  MigrIssue, OrgIssue, Question.
- **status** — a cycling chip (SalesXLS pattern, `_salesxls_chip.html`
  reused as a template, not shared code): click cycles
  open → in_progress → closed → open, saved immediately via
  `POST /sustain/callouts/<id>/status` (`db_sc.cycle_status` — server
  decides the next state, no value posted). Closed items are hidden by
  default; `?show_closed=1` reveals them.
- **date_captured** — set once at creation (today), never edited.
- Quick add on the list (channel · type · name · ticket no · responsible)
  + delete (fetch, reload); everything else is edited on the detail page
  (the inline edit row of the first build is gone since 2026-09-02).
- **Filter bar** (2026-09-02, client-side, `sc-filterbar`): channel and
  status selects, one **checkbox per type** (combinable — Marina's ask),
  free text over name + ticket no, Clear, shown/hidden counter. Rows carry
  `data-channel/type/status/search`; the status chip keeps `data-status`
  in step. Closed rows are only on the page with `?show_closed=1`, so the
  status filter can only pick among what is loaded.
- **Inbox → call-out** (2026-09-02): the inbox filing picker's target
  "Sustain call-out" files a note under an existing call-out (search by
  name / ticket no, open first) or creates a NEW one from the note
  (`POST /inbox/<id>/file-to-callout`, name defaults to the heading) —
  see `[[inbox]]`.
- `list_open_for_channel(conn, channel)` — a channel's own open/in-progress
  items **plus every `both` item** — feeds the management summary below.

- **next_step** — inline text input (`sustain_issues.html` pattern: onblur
  save via `POST /sustain/callouts/<id>/next-step`, JSON body), plus ↻
  archive / 🕘 history through the generic `/next-steps` component
  (`web_next_steps.REGISTRY['sustain_callout']`, entity id = the row's
  `id`; `_next_step_history.html` included once on the page). Stored
  directly on `sustain_callouts.next_step` (blocker pattern), added by an
  additive `ALTER TABLE` in `init_schema`.
- **Notes** — the SAME shared `_notes_section.html` component every other
  entity uses (heading + text, per-note 📷 screenshot / 📎 file
  attachment upload with Ctrl+V paste, edit/delete), one instance
  included per call-out row, toggled open/closed by a plain "Notes (n)"
  button (`js-sc-notes-toggle`, board-only JS, no fetch). **Fixed
  2026-09-01** [USER]: the first build had copied the OTHER, lighter
  pattern used by `todo_list.html`/Meeting Prep (plain-textarea quick-add,
  no heading, no attachments) — the wrong precedent to follow; the
  Delegated Ways of Working page already proved the full component works
  fine on a list-only entity (`detail_endpoint=None` in
  `web_notes.REGISTRY`) without a dedicated detail page. No data was lost
  by the swap — same `notes` table/entity_type, existing notes just had
  no heading (shown as "(no heading)") and no attachments (there was no
  button for it before). Two small shared-infrastructure changes made
  this possible:
  - `_notes_section.html`'s wrapper id changed from the hardcoded
    `id="notes"` to `id="notes-{entity_type}-{entity_id}"`, so multiple
    instances on one page (one per call-out) don't collide (the one other
    place linking to the bare anchor, Retail's note-count link, updated
    to match).
  - `web_notes._redirect_target` now appends `&note_entity=<id>` to every
    add/edit/delete redirect. `_notes_section.html`'s "saved" banners only
    show when `note_entity` matches their own `entity_id` (or is absent —
    single-instance pages are unaffected) — otherwise EVERY call-out row's
    banner would flash after saving just one note. `sustain.html` also
    auto-reopens the touched call-out's notes row on that redirect (server
    side, via the same query params) so the confirmation banner is
    actually visible, since rows start collapsed.
  - Add/Edit/Delete are real page navigations, not instant like the old
    widget — other expanded rows re-collapse on that round trip; accepted
    as-is for now [USER: "try plain first"]. Since the detail page exists
    (2026-09-02) the registry entry has a `detail_endpoint`; the list
    page's include passes `notes_return_to='list'` so **Add** from a row
    still lands back on the board, while Edit/Delete of a note from the
    list land on the call-out's detail page (the note form carries no
    return_to in edit mode).
- **Management summary block** (build plan step 4) — inside each stream's
  section on `/sustain/summary[/<day>]`, right below the stat cards and
  above the Attention list: a table of that channel's open/in-progress
  call-outs (`db_sc.list_open_for_channel`, so `channel='both'` items show
  up in BOTH the Retail and eCom sections) — type, name, responsible,
  status pill, date captured, current next step. Shown on every day's
  summary until closed (call-outs are ongoing, not tied to one day's
  import) — hidden entirely when a channel has none open.

### Day report — `/sustain/day/<day>/<stream>` (`sustain_day.html`)

Mirrors the Excel tab: a real `ui.table` (# · Process/Task+taxonomy ·
Cadence · Due · Provider · FR/IT/PT/ES · Overall), parent `<tr>`s with
detail rows toggle them via `sustainToggle()` (hidden `<tr>`s, `.sustain-*`
CSS component in style.css) — deliberately NOT the smoke `<details>`
accordion, Marina asked for "the structure of the excel". Every shown
status is recomputed in the web layer via the storage classification
(`derive_cells`/`derive_overall`/`task_status`); result cells render as
pills — OK green, Pending amber, Review + **free-text issue notes red
(verbatim text)**, N/A / Not due gray, blank —. A last column
**Comments / Observations** shows column M as plain grey text (parents and
detail rows), visibly separate from the status pills. Stat cards =
`summary_counts` (due/completed/pending/attention). Header: back link,
⇄ toggle to the other stream of the same day, day-link row per stream.

### Management summary — `/sustain/summary[/<day>]` (`sustain_summary.html`)

v1 layout (built 2026-08-28 while Marina was away; layout review flagged
in MarinaCheckSoon). Defaults to the **latest** imported day; day-link
row to switch. Per stream a `ui.section` (Retail blue, eCom teal, badge
"N attention"/"all clear"): stat cards (due/completed/pending/attention)
+ the **Attention list** — task · country · provider · verbatim note as
a red pill (`attention_items`: free-text cells + literal `Review` marks;
for tasks with details only DUE detail rows are scanned — a note on a
not-due row isn't today's business; simple parents use their literal
cells). Underneath, a **Comments / observations** table per stream lists
every column-M entry of the day (`comment_items`) — deliberately its own
table below the attention list, because a comment is an observation, not
an issue, and must not inflate the attention count. Then **Day-over-day trend** (`overview`: every tab, completion %
= completed/due, rows link to the day reports) and **Repeat offenders**
(`repeat_offenders`: same stream+task+country+provider in attention on
2+ days → sorted days + deduped verbatim notes; sorted by day-count
desc). 📊 button on the card page.

Jinja gotcha (cost one debugging round): a template-visible dict must
not use the key `items` — `dict.items()` shadows it in attribute lookup;
the per-stream dicts use `attention`.

## Dashboard card

"Core South Sustainphase Monitoring" (after the Smoke card), task-count
badge (`db_sustain.task_count`), Open + 📊 Summary buttons.

## Ways of Working (2026-09-02 [USER])

**🤝 Ways of working** button in the card header opens
`/notes-page/sustain_wow` — the sustain team's decision log. Not its own
build either: one more entry in the shared working-notes pages registry
(`[[note-pages]]`), free-text headings exactly like the Delegated one.
Asked for as "similar to the one we did in delegated testing" — the
component question (CLAUDE.md) was asked and answered: the component
already exists, this is its fourth user.

## Meeting Summaries (2026-09-01 [USER])

**📝 Meeting summaries** button in the card header opens
`/notes-page/sustain_meeting_summaries` — daily AI meeting summaries kept
for future reference. Not its own build: one entry in the shared
**working-notes pages** component (`[[note-pages]]`, registry
`app/note_pages.PAGES`), with `heading_mode='date'` — the note's heading
is ONLY a native date picker (prefilled with today), no free text
[USER: "in the title I can pick a date"]; several meetings on the same
date are fine, notes sort by that date (newest first), not by when they
were pasted. A keyword filter box above the list finds a topic by plain
substring match — no AI, ever [USER: "the app itself NEVER EVER uses
ai"]. TXT export was asked for and deliberately parked (HTML download
only, for now).

All 6 build-plan steps done 2026-08-28 (steps 2–6 executed autonomously —
Marina's click-through checklist: `docs/marina_notes/SessionTest_2026-08-28.html`;
open review points in `MarinaCheckSoon.html`: the free-text-attention
deviation and the summary v1 layout).

## Related

`[[sustain-issues]]` · `[[smoke]]` · `[[report-blocks]]` ·
`[[next-steps]]` · `[[notes]]`

## Change log

- **2026-09-02 — Call-outs: name + detail page, ticket no, impact, filter
  bar, inbox push** (planning chat, 6 steps). `name` is the short list
  line; topic/impact/ticket no/responsible live on the new detail page
  `/sustain/callouts/<id>` (the inline edit row is gone); type filter as
  combinable checkboxes + channel/status/text; inbox notes can be pushed
  under an existing or a new call-out. Global-search registration was
  dropped on Marina's call (tickets live only here). Shared change:
  `_notes_section.html` takes an optional `notes_return_to`. 14 new
  tests.
- **2026-09-01 — Call-out notes fixed to the full shared component**
  [USER: "what you gave me was a simple text filed"] — see the Notes
  bullet in the Call-outs subsection above for the full story (root
  cause, the fix, and the two small shared-infrastructure changes it
  needed). No notes lost.
- **2026-09-01 — Call-outs** (planning chat, built in 4 steps: storage,
  card-page section + status chip, next-step/notes wiring, management
  summary block). Marina's own monitoring log for the daily review — see
  the Call-outs subsection above for the full shape. 24 new tests across
  `test_sustain_callouts_storage.py` / `test_sustain_callouts_web.py`.
- **2026-08-31 — new workbook version** (`1_0109_0409-O2C DTC_GBS
  Operations_checklist (1).xlsx`). Three changes, all handled:
  1. Header row 6 → 5 (the instruction line was dropped). Would have
     broken the import outright; the header row is now located, and both
     layouts import.
  2. New free-text column M "Comments/Observations" → imported into
     `comments` on both tables, shown in the day report (own column) and
     the management summary (own table); informational only.
  3. The workbook's own summary definitions changed (DUE excludes N/A,
     COMPLETED = OK only, REVIEW restricted to due) → `summary_counts`
     follows [USER], so the app's stat cards match the Excel again.
