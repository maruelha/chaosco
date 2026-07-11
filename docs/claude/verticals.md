# Import verticals — Defects, Core South Spillover, Retail

Read when working on the Excel importers, their tables, screens, or reports.

## Common pattern

Each Excel tab has its own importer + its own SQLite table. Import is
idempotent (upsert, never delete): `first_seen` set once, `last_seen` updated
every run. Importers write ONLY to `defects` / `spillover` / `retail` — never
to the `*_annotations` tables (user-authored). All parsing is header-map
driven (`_HEADER_MAP` at the top of each importer, case/whitespace-insensitive).
`app/importer.py` orchestrates all three: parse → archive (SHA-256 dedup via
`app/archiver.py`) → upsert → skip-log CSV.

| Vertical | Excel tab | Importer | DB module | Table | Annotations | Match key |
|---|---|---|---|---|---|---|
| Defects | "Defects" | `app/read_defects.py` | `app/db/defects.py` | `defects` | `defect_annotations` | `defect_id` (TEXT PK) |
| Spillover | "Core South Spillover" | `app/spillover_importer.py` | `app/db/spillover.py` | `spillover` | `spillover_annotations` | `excel_row` (stable) |
| Retail | "Retail" | `app/retail_importer.py` | `app/db/retail.py` | `retail` | `retail_annotations` | lower(test_case_id) \|\| "\|\|" \|\| lower(country) |

`app/solman_sync.py` — targeted UPDATE of `defects.solman_status` +
`assigned_to` from the "Data aggregated by Defect" SolMan export; skips
Withdrawn/Confirmed defects. Route: `POST /solman-sync` (dashboard has no
card — triggered where configured). Config keys: `solman_export_folder`,
`solman_export_stem`, `solman_export_sheet`.

## Key columns

- `defects` — 21 cols incl. defect_id (PK), channel, solman_status, priority,
  assigned_to, excel_row, first_seen, last_seen
- `defect_annotations` — description, business_impact, reach, retest_needs,
  next_step, action_needed, comments, dtco2c (0/1 = "MB follows up"),
  dtco2c_resp, daily (0/1 = discuss on DTC O2C Daily), updated_at
- `spillover` — spillover_id (PK AI), type, name, country, area, status,
  assigned_to, external_id, order_numbers, content, comment, excel_row,
  match_key (UNIQUE), first_seen, last_seen
- `spillover_annotations` — importance_for_signoff, next_step,
  comment_history, critical_for_signoff, comment_for_signoff, signoff_group
- `retail` — retail_id (PK AI), test_case_id, country, testcase_name,
  testcase_scenario, status, assigned_to, + execution/order/S4 fields,
  match_key (UNIQUE), first_seen, last_seen
- `retail_annotations` — next_step, comment_history, action_needed

## ECOM vertical (importer + pages built 2026-07-09, day plan steps 7+8)

- Blueprint `app/web_ecom.py` (`/ecom`): list (filters status/country/
  scenario + search, Jira-✓ chip, Δ-Desc pill, Orders via the shared
  order-details component) + detail (Excel fields read-only · Jira card
  read-only from the shared store or "no data yet" hint · annotations ·
  Orders incl. "Take over orders from Gatekeeper" =
  `relink_gatekeeper_orders` by same jira id · notes via registry entry
  `ecom`). "↻ Update from Jira" = `run_jira_import(cfg, 'ecom')`.
  Dashboard card. Tests: `tests/test_ecom_pages.py`.
- Status report `/ecom/report` [USER 2026-07-09]: SAME bucket definitions
  as Retail (one config — status_mappings.yaml; "Not Ready" = known
  exclusion, visible in the inline diagnostics section, no separate
  diagnostics page). Impacted ECOM-channel defects
  (`get_ecom_defects_impacted`, same rules as Retail). Outputs: page +
  Copy-TSV + standalone HTML download (via `emailer.standalone_html` — no
  separate download template) + Save-to-Excel (ECOM sheet in the shared
  report log workbook) + 4th email checkbox. NO PPT (not requested).
  Tests: `tests/test_ecom_report.py`.

- `app/ecom_importer.py` (`parse_ecom`) + `app/db/ecom.py`: tables `ecom` +
  `ecom_annotations`. **Match key = JIRA ID** [USER 2026-07-05] — rows
  without one go to the skiplog, never inserted; annotations keyed by
  jira_id survive re-imports.
- Excel fields vs Jira fields strictly separate: `ecom.status`/`assigned_to`
  come from the tab; jira_status/jira_assignee live in the shared jira
  store (join by jira id, step 8).
- Runs in the normal import pipeline (`imports.ecom` in settings.yaml,
  sheet "ECOM"). NOTE: the config merge is per top-level key — the local
  file's `imports:` block replaces the base one, so new tabs go in BOTH.
- Extra columns vs Retail: `jira_id`, `description_change` (display; feeds
  the external coverage tool). Tests: `tests/test_ecom_importer.py`.

## Shared Jira store (trial-verified 2026-07-11 against the real export)

- Real-file trial (gatekeeper search, 8 tickets, 27 comments): parser OK
  first try; the instance's custom-field names ARE "Epic Link"/"Markets".
  Jira has NO order-number field — order numbers live in comment texts.
- `/ecom-gatekeeper` [USER 2026-07-11]: the JIRA TICKETS table is THE
  current gatekeeper; the manual `ecom_gatekeeper` table is DEPRECATED
  (kept, collapsed at the bottom, still fully functional). "↻ Update from
  Jira" (`POST /ecom-gatekeeper/import-jira`, newest .xml from
  `jira_gatekeeper_folder`). Per ticket row: read-only Jira fields +
  AUTHORED inline next step (blur-save,
  `POST /ecom-gatekeeper/ticket/<key>/next-step`) with ↻/🕘 archive
  buttons, Details link (with note count), inline comments expander.
- Ticket detail page `/ecom-gatekeeper/ticket/<jira_key>`
  (`gatekeeper_ticket.html`): Jira card (status/assignee/epic/markets,
  open-in-Jira, extracted order numbers + source, acceptance criteria,
  description HTML, comment thread) + "My next step" (archive component) +
  full notes module. Authored data in `app/db/gatekeeper.py`
  (`gatekeeper_annotations`, jira_key PK — start of Gatekeeper v2 storage,
  survives the ECOM handover). Notes/next-step entity type = `jira`
  (registry entries in web_notes + web_next_steps); inbox filing option
  "Gatekeeper ticket" (search by key / solman id / summary; the old
  `ecom_gatekeeper` type stays supported for legacy notes). Tests:
  `tests/test_gatekeeper_jira.py`.

- `app/db/jira.py`: `jira_issues` (jira_key PK; solman_id = summary before
  first "_"; epic/markets from custom fields by NAME; description HTML) +
  `jira_comments` (HTML bodies, NO authors — export only has JIRAUSER keys).
- `app/jira_importer.py`: Jira RSS parser (DC 10.3; pre-pass escapes bare
  `&`), `run_jira_import(cfg, 'gatekeeper'|'ecom')` — takes the NEWEST .xml
  in `jira_gatekeeper_folder` / `jira_ecom_folder` (settings.yaml),
  filenames irrelevant.
- Re-import rule [USER 2026-07-05]: match by jira key; ONLY jira_status,
  jira_assignee, comments (REPLACED wholesale) and — since 2026-07-11 —
  `acceptance_criteria` refresh (living test data: testers fill order
  numbers into the AC checklist over time); all other fields keep their
  first-import value.
- Acceptance Criteria = okapya checklist custom field; parsed as
  whitespace-normalized text lines. Order-number extraction
  (`jira_importer.extract_order_numbers` [USER 2026-07-11]): 1. ALL
  labeled orders from the AC ("… Order[ Number] : value", XXXX
  placeholders skipped) → 2. else the LATEST comment carrying a labeled
  order or an order token (`AA_BB_XXXXXX` pattern). Feeds the
  "Order numbers report" on the gatekeeper page (Jira ID · Solman ID ·
  orders · source pill, copy-as-TSV).
- Never merged into Excel-sourced tables. Tests: `tests/test_jira_importer.py`.

## Screens & reports

- Defects list `/defects` (filters, inline DTC O2C + Daily toggles, sortable),
  detail `/defects/<id>` (annotation form → notes → meeting-prep add →
  imported fields read-only)
- Spillover list `/spillover` (frozen-pane table, per-row Details / Order
  details / Comments / Notes), detail `/spillover/<id>`. 2026-07-09:
  "With whom" column (Sales | MB, `spillover_annotations.with_whom`,
  inline AJAX select + multi filter) and "Status report" filter/column
  (in/not-in `spillover_report_selection`, green ✓)
- Spillover Status Report: select `/spillover/report` (persists selection
  in `spillover_report_selection`), TWO coexisting views [USER 2026-07-10:
  the table is ADDITIONAL, not a replacement]: detailed card view
  `/spillover/report/view` (printable, critical-first, wins + Additional
  sections — the original) and compact table `/spillover/report/table`
  (grouped by with_whom Sales → MB → Unassigned, critical-first inside
  sections, inline-editable comment_for_signoff column, 📣 Call-outs box =
  report_comments edited directly on the report; the /report-comments add
  route also accepts 'ecom'); cross-links in both toolbars + both on the
  selection screen. PPT `/spillover/report/ppt` (unchanged card slides).
  Email/export attach the detailed view.
- Retail list `/retail`, detail `/retail/<id>`
- Retail Status Report `/retail/report` (buckets from
  `config/status_mappings.yaml` via `app/reporter.py`; Save to Excel appends
  `output/retail_report_log.xlsx`; Download HTML/PPT), diagnostics
  `/retail/report/diagnostics`. Defect section counts IMPACTED test cases
  [USER 2026-07-06]: TC references the defect AND has not passed yet (passed
  family = the passed_with_dtc bucket, one definition via
  `reporter.passed_family`); passed refs stay visible muted "(+N passed)"
  (`get_retail_defects_impacted` + `compute_impacted_totals`). MB vs Sales
  [USER 2026-07-10]: the Excel's "Sales or DTC" column (imported as
  `defects.sales_or_dtc`) DRIVES the split — DTC → MB, Sales → Sales; the
  manual DTC O2C flag only fills in when the cell is blank; neither →
  Sales + amber "no MB/Sales decision" note on diagnostics.
- Sign-off reports `/report/retail`, `/report/ecom`; production defects
  `/prod_defects`
- PPT builders: `app/ppt_utils.py` (shared primitives), `app/ppt_retail.py`,
  `app/ppt_spillover.py`. Export Reports button (`POST /export-reports`,
  `app/report_exporter.py`) writes dated HTML + PPTX for both reports to
  `report_export/`.
