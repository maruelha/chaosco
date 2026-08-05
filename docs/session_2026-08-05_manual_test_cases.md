# Session 2026-08-05 — Manual Test Cases verticals (Retail + ECOM)

Running documentation of this session; updated after every completed step.

## Goal

Two new Excel tabs — **`Manual Test Cases | Retail`** and **`Manual Test
Cases | ECOM`** (pipe in the sheet names!) — get their own import verticals,
two new dashboard cards, and two new status reports in the **simple Retail
report style**, without duplicating the report code. The Retail report is
pulled out as a reusable component first; both manual reports are then built
from it. The reports also become sendable from the Email Reports page.

## Findings from the workbook (`DTC_UAT_testtracking_ROE(46).xlsx`)

- The workbook ALSO still contains two older, empty stub tabs without the
  pipe (`Manual Test Cases Retail` / `Manual Test Cases ECOM`) — ignored;
  the importers target the pipe names exactly.
- **`| Retail`** (34 rows): shaped like the Retail tab (Key user
  responsible, execution started/completed, Comment, reason for pass with
  reservation) + new columns `Store No.`, `Sales Status`, a second
  `Order number` (all still empty). 7 test cases (CDI0000MU01–07) ×
  18 countries.
- **`| ECOM`** (179 rows): shaped like the ECOM tab (`Jira ID`,
  `Description Change` — both entirely blank so far). 38 test cases
  (CDI0000MU01–38) × 19 countries; content is mostly per-partner
  Settlement File Validation (Zalando, Best Secret, …).
- The same test-case IDs (MU01–07) appear on BOTH tabs → the two verticals
  need separate tables.
- Jira ID is blank everywhere → the manual ECOM vertical can NOT match by
  Jira ID like the ECOM board. **Both manual verticals match by
  lower(test_case) + lower(country), like Retail.**

## Decisions (Marina)

- Report landscape from this Excel: a) Spillover = its own beast, untouched ·
  b) ECOM report = a bit different (Jira comes in), untouched ·
  c) Retail report = THE simple pattern (Excel statuses + defects) ·
  d) Manual Retail + e) Manual ECOM = two more instances of exactly that
  simple pattern · f) Defects report = exists, untouched.
- No special per-partner report design for Manual ECOM — both manual
  reports are the simple pattern.
- **Defects rule for the manual reports:** a defect appears only if it is
  (1) referenced in the manual tab's "Defect ID (if applicable)" column AND
  (2) its channel on the Defects tab matches (Retail channel for Manual
  Retail, ecom for Manual ECOM; case-insensitive). Referenced defects whose
  channel does NOT match go to the report diagnostics instead of vanishing.
  Impacted counting = same rules as the Retail report (not-passed TCs count,
  passed shown muted, MB/Sales split).
- Same bucket definitions as Retail/ECOM (`config/status_mappings.yaml`).
- **ONE line per test case + country** (decision after seeing the data):
  the ECOM tab's repeated identical CDI0000MU34 rows (up to 7× within one
  country, 63 extra rows) are a DATA DEFECT in the workbook — Marina
  clarifies with the team. The importer keeps the first occurrence and
  skiplogs the rest (red counter on the import screen). The earlier
  occurrence-suffix approach was implemented first, then reverted.

## Plan / progress

| Step | Content | Status |
|---|---|---|
| ① | Extract shared report component; Retail report unchanged | ✅ done 2026-08-05 |
| ② | Importers + tables `manual_retail` / `manual_ecom` | ✅ done 2026-08-05 |
| ③ | Report + list pages, two dashboard cards | ✅ done 2026-08-05 |
| ④ | Email Reports checkboxes for both manual reports | ✅ done 2026-08-05 |
| ⑤ | Docs + session click-through test plan | ✅ done 2026-08-05 |

## Step ① — Shared report component (done)

- **New `app/templates/_report_blocks.html`** — Jinja macros:
  `bucket_overview`, `breakdown`, `impacted_defects` (with optional summary
  cards), `diagnostics_inline`, `additional_comments`, `report_scripts`
  (copy-TSV + save-Excel wiring).
- **`retail_report.html`** is now a thin page: header + Retail-only
  universe strip + five macro calls. Verified by before/after HTML diff of
  `/retail/report` — identical output (only a JS comment and quote style
  inside the script differ).
- **New `app/report_log.py`** — `append_report_row(cfg, report, day,
  sheet_name)`: the ONE writer for `output/retail_report_log.xlsx`.
  `web_retail.py` (sheet "Retail") and `web_ecom.py` (sheet "ECOM") now use
  it; their duplicated copies are deleted.
- NOT touched by design: `ecom_report.html` (page unchanged, may adopt the
  blocks later) and `retail_report_download.html` (separate standalone
  rendering for the email attachment).
- Tests: full suite green (285 passed).
- Docs updated: `docs/architecture.html` (report_log row, status-report
  blocks component, layout table), `docs/claude/verticals.md` (Retail
  report entry).

## Step ② — Importers + tables (done)

- **New `app/manual_importer.py`** — one module, `parse_manual(cfg,
  vertical)` with separate header maps per tab (they are siblings, not
  identical). Blank Excel header columns ("Unnamed: N") are ignored; the
  Retail tab's bare duplicate "Order number" column is deliberately left
  unmapped (first-wins alias rule keeps "Order number /Transaction number").
  CLI: `python -m app.manual_importer` parses both tabs, prints a summary.
- **New `app/db/manual_tests.py`** — tables `manual_retail` + `manual_ecom`
  (schema, upsert, list/filter/status-count queries). Match key = test case
  + country, like Retail.
- **Data finding:** the ECOM tab repeats `CDI0000MU34` ("Settlement File
  Validation") up to 7× within one country as fully identical rows
  (63 extra rows; only Country varies across the 81 MU34 rows; counts
  differ per country — Austria 6, Poland 7, Croatia 1). Marina judged this
  a WORKBOOK DEFECT → one line per tc+country; duplicates skiplogged and
  counted red on the import screen. Also spotted: country typo "FInland"
  (6 rows) next to "Finland" — splits into two filter values until fixed.
- Wired into `app/importer.py` (parse + upsert + skiplog + result blocks),
  `config/settings.yaml` (`imports.manual_retail` / `manual_ecom`, pipe
  sheet names), `app/web.py` (schema init), and the import-result screen
  (two new sections).
- Verified against the real workbook (46): manual_retail 34 rows,
  manual_ecom 116 rows (+63 duplicates skiplogged), re-import idempotent.
  Tests: `tests/test_manual_importer.py` (9 tests incl. FIELDS↔importer
  drift guard + duplicate-skip behaviour); full suite 294 green.
- Docs updated: `database_schema.html` (two new table cards + index),
  `docs/claude/verticals.md` (table rows + new section).

## Step ③ — Pages + cards (done)

- **New `app/web_manual_tests.py`** — ONE Blueprint for both streams:
  `/manual/<stream>` list (read-only, Status/Country/Scenario dropdowns +
  free search) and `/manual/<stream>/report` + `/report/download`
  (standalone via `emailer.standalone_html`) + `/report/save-excel`
  (sheets "Manual Retail" / "Manual ECOM" via the shared
  `report_log.append_report_row`). Unknown streams 404.
- **New templates** `manual_list.html` + `manual_report.html` — the report
  is five calls into the shared `_report_blocks.html` macros plus one
  stream-specific section.
- **Defects rule implemented** (`get_manual_defects_impacted`): defect
  appears ONLY if referenced in the tab's defect_id_ref AND its Defects-tab
  channel matches (retail/ecom, case-insensitive); counting/MB-Sales split
  identical to Retail. Referenced-but-off-channel defects render as a red
  ⚠ box on the report (`get_manual_offchannel_defect_refs`) — never
  silently dropped. Both sections start empty (no defect refs in the data
  yet).
- **Two dashboard cards** (View List + Report each).
- Tests: `tests/test_manual_pages.py` (7 tests: rendering, 404s, filters,
  the defects rule incl. off-channel, save-excel sheets, standalone
  download); full suite 300 green. Verified against the real DB — all
  pages 200, report previews sent to Marina.
- Docs updated: `screens.html` (two new screen cards),
  `dashboard_cards.html` (two new cards), this file.
- NOT included (deliberate, v1): notes/annotations on manual rows, detail
  pages, ⚠ row validations, PPT export.

## Step ④ — Email checkboxes (done)

- `emailer.REPORT_CHOICES` grew entries 5+6 ("Manual Test Cases Retail /
  ECOM Report") — the /email-report page lists them automatically.
- `gather_attachments`: both manual reports rendered through the live app
  (`/manual/<stream>/report`) and made standalone via `standalone_html`,
  attached as `manual_<stream>_report_<date>.html`.
- Docs: screens.html email-report card updated. Tests: attachment naming +
  standalone check in `tests/test_manual_pages.py`; full suite 301 green.

## Step ⑤ — Docs + test plan (done)

All docs current: `verticals.md` · `screens.html` · `dashboard_cards.html`
· `database_schema.html` · `architecture.html` · `build_plan.md` (new
module section) · `MarinaCheckSoon.html` (4 new checkboxes). Click-through
checklist: `docs/marina_notes/SessionTest_2026-08-05.html`. Final suite:
301 tests green.

## Bonus — Report history (same session, after the ①–⑤ plan)

Marina's goal: stop hand-pasting the report numbers into the workbook's
ReportRetail / ReportECOM tabs — save them automatically instead.

- **`report_history` table** (app/db/report_history.py): one row per
  bucket report + reported date, the app's 9 bucket columns, source
  ('email' | 'excel'), REPLACE on same (report, date).
- **Email send** now auto-saves the ticked bucket reports under the email
  page's date (snapshot failure never blocks the mail).
- **`/report-history` page**: switcher over the four reports, dates newest
  first, source pill, Copy-TSV, and the **"⤓ Import from Excel tabs"**
  button that pulls the workbook tab lines in (upsert per date,
  re-runnable — 36 real Retail dates 21.05.–23.07. imported on this
  machine; ECOM tab has headers but no data; 1 Retail line skipped for an
  unreadable date). History buttons on all four report toolbars.
- Tab parser handles the real layout: junk header row, label row found via
  the "date" cell, description row skipped, 21.05.2026 + datetime cells,
  non-bucket columns ignored (Total from Sales, Sense check, Waiting for
  SF creation, combined In Progress/In Clarification).
- Tests: `tests/test_report_history.py` (6) — suite 307 green. Docs:
  database_schema.html, screens.html (new card + email card), verticals.md
  (new section), build_plan.md.
- **Marina can now stop maintaining the ReportRetail/ReportECOM tabs** —
  the import button remains for catching up any lines colleagues still add.

## Bonus 2 — 🔍 search covers Jira tickets + notes (same session)

Marina's question: "in my search for order numbers I don't check the
Gatekeeper page, do I?" — correct: the manually pinned order-details lines
were searched, but NOT the Jira acceptance criteria / comments where
Gatekeeper order numbers actually live.

- New search sources in `db/search.py`: **Jira tickets** (AC + comment
  bodies, HTML stripped, snippet with AC:/Comment: prefix, one hit per
  ticket → gatekeeper ticket page) and **Notes incl. Inbox** (heading +
  body; URL via the notes REGISTRY, inbox items → /inbox, unknown entity
  types dropped in the web layer).
- Decided NOT searched: manual test cases (no order numbers there
  [Marina]), topics (unsure she'd use it — skipped for now), meeting prep
  (covered indirectly via defects + notes).
- Verified on real data: an order number living only in a Jira AC
  (S4ECOM-1241) is now found. Tests extended in `tests/test_search.py`;
  suite 307 green. Docs: screens.html search-widget card.

## Bonus 3 — three small UI/import changes (same session)

- **"Defects" renamed to "MB ROE Defects"** everywhere in the UI: page
  title + h1, dashboard card, notes breadcrumb (web_notes REGISTRY). The
  Excel sheet name and all URLs/endpoints are unchanged.
- **Message-types card**: TIBCO API + IIB API columns widened 16 → 21.5rem
  (~⅓) so the API names are readable.
- **Retail "Store No." imported**: header map + `retail.store_no` column
  (additive migration in db/core.py) + optional row on the Retail detail
  page. Real data: 4 Bulgarian rows carry "BGBR". The Retail tab's OTHER
  new columns (Sales Status, old defect ids, bare "Order number") remain
  deliberately unimported — only Store No. was requested.
- Tests: `test_retail_imports_store_no`; suite 308 green.

## Bonus 4 — two form-state bug fixes (same session)

- **Meeting prep — note appeared on the next row after "✓ Discussed"**:
  server data was always correct (verified — notes are id-keyed); the
  cause was `location.reload()` after the status change. Browsers restore
  typed form values BY POSITION on reload, so with the discussed row gone
  from the (default planned) view, the typed note text reappeared in the
  NEXT row's textarea — and saving there would have written it to the
  wrong item. Fix: `window.location.replace(window.location.href)` (a
  navigation, no form restoration) + `autocomplete="off"` on the note
  textareas. Rule for the future: prefer location.replace over
  location.reload after row-removing actions.
- **Encouragements — name stuck in the Person field after save**: the add
  form pre-filled the field from the person FILTER (which the post-save
  redirect sets to the added person). Prefill removed — the filter still
  shows the person's list below, the form starts clean.
- Tests: `tests/test_form_state_fixes.py` (3 — incl. a markup-contract pin
  on replace-not-reload); suite 311 green.

## Notes / watch-outs

- `settings.local.yaml` overrides merge PER TOP-LEVEL KEY: a local
  `imports:` block replaces the base one — when step ② adds the two new
  import entries, machines with a local `imports:` override need them added
  there too (both computers!).
- Retail report's `retail_missing_categories` still lists "Manual test
  cases" as untracked on the Retail report's universe strip — Marina to
  decide later whether that wording/number changes once the manual tabs are
  tracked.
- The newest workbook was found in `C:\Users\AI_Agents\Downloads`; the app
  imports from the configured `downloads_folder` (project `Download` folder
  on this machine) — file must be copied there, as usual.
