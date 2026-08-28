# Core South Sustainphase Monitoring (`/sustain/`)

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
- Headers row 6, data from row 7. Columns: A Task ID · B L4 Taxonomy ·
  C Process/Task · D Cadence · E Due Today · F Country · G Provider/
  Partner/Financial Account · H–K France/Italy/Portugal/Spain Result ·
  L Task Overall (formula, "DO NOT EDIT").
- **Parent tasks** carry a Task ID at outline level 0. **Detail rows**
  ("↳ Detail check", one per country × provider/account/store) sit at
  outline level 1, collapsed in Excel; openpyxl exposes
  `row_dimensions[r].outline_level`, so the structure imports faithfully.
- Result-cell vocabulary: `OK` / `Pending` / `Not due` / `N/A` /
  `Review`, or **free text** — the team writes short issue notes directly
  into the cell (how-to in row 5). Free text is the discussion-point
  signal.
- Row 4 holds DUE/COMPLETED/PENDING/REVIEW `COUNTIFS` summaries; L4 is a
  save-check ("Save file to check"). Cached formula values are only right
  after a save → **never trust row 4 or the rollup cells; recompute in
  Python** (see below).

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
- Row 4: DUE = parents with E=Yes; COMPLETED = due parents with L in
  {OK, **N/A**}; PENDING = due parents with L=Pending; REVIEW = **all**
  parents with L=Review (not only due ones).
- `COUNTIF` matches case-insensitively → every comparison in our Python
  mirror does too (`casefold`).

## Storage — `app/db/sustain.py`

`sustain_tasks` / `sustain_task_details` (1:n via `task_pk`, technical
PKs, portable SQL). Each upload calls `replace_day_stream` per tab, so
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
  due/completed/pending/attention. completed+pending partition the due
  tasks that need no attention; attention counts over ALL parents (like
  Excel's REVIEW — an on-occurrence issue must surface too).
- `list_tabs` (day picker), `list_tasks` (workbook order, details
  attached), `task_count` (dashboard badge).

## Importer — `app/sustain_importer.py`

`parse_sustain_workbook` loads with `data_only=True` (cached cell values;
aggregations are recomputed in storage, never imported). Tab pattern
`(Retail|eCom)_<ISO date>` (case-insensitive) → (stream, day); other tabs
ignored; a matching tab whose row-6 column A isn't "Task ID" raises
`ParseError` (structure drift must be loud). Parent = row with Task ID;
detail = outline level ≥ 1 under the last parent; level-0 rows without a
Task ID are dropped. Task IDs arrive as text OR numbers → normalised to
text. `run_sustain_import` replaces each contained tab
(`replace_day_stream`) and returns ok/error + tabs/tasks/details counts.

Verified 2026-08-28 against the real `1_0109_0409` file: 8 tabs,
236 tasks, 2,720 details; recomputed due/completed/pending matched the
Excel's cached row 4 on all 8 tabs exactly.

## Web — `app/web_sustain.py` (Blueprint `/sustain/`)

Upload on the card (Smoke pattern): file picker, dated `sustain_*.xlsx`
copy in `data/uploads/`, then `run_sustain_import`. Filename guard:
`.xlsx` AND the name must **contain** `DTC_GBS Operations_checklist`
(not end with it — browser " (1)" double-download copies must still
import; the prefix before `DTC_GBS` varies per file anyway). Import
result via `sustain_ok`/`sustain_msg` query params in a result-box.
Template `sustain.html`; the imported-days table (`list_tabs`) links each
(day, stream) to the day report.

### Day report — `/sustain/day/<day>/<stream>` (`sustain_day.html`)

Mirrors the Excel tab: a real `ui.table` (# · Process/Task+taxonomy ·
Cadence · Due · Provider · FR/IT/PT/ES · Overall), parent `<tr>`s with
detail rows toggle them via `sustainToggle()` (hidden `<tr>`s, `.sustain-*`
CSS component in style.css) — deliberately NOT the smoke `<details>`
accordion, Marina asked for "the structure of the excel". Every shown
status is recomputed in the web layer via the storage classification
(`derive_cells`/`derive_overall`/`task_status`); result cells render as
pills — OK green, Pending amber, Review + **free-text issue notes red
(verbatim text)**, N/A / Not due gray, blank —. Stat cards =
`summary_counts` (due/completed/pending/attention). Header: back link,
⇄ toggle to the other stream of the same day, day-link row per stream.

## Still to build (build-plan steps 5–6)
4. Detail report (day picker + stream toggle, expandable parents, stat
   cards from `summary_counts`).
5. Management summary (headline + Attention list + trend + repeat
   offenders) — layout to re-discuss with Marina after step 4.
6. Dashboard card + docs sweep.
