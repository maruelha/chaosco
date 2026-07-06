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

## Screens & reports

- Defects list `/defects` (filters, inline DTC O2C + Daily toggles, sortable),
  detail `/defects/<id>` (annotation form → notes → meeting-prep add →
  imported fields read-only)
- Spillover list `/spillover` (frozen-pane table, per-row Details / Order
  details / Comments / Notes), detail `/spillover/<id>`
- Spillover Status Report: select `/spillover/report` (persists selection in
  `spillover_report_selection`), view `/spillover/report/view` (printable,
  critical-first, wins section), PPT `/spillover/report/ppt`
- Retail list `/retail`, detail `/retail/<id>`
- Retail Status Report `/retail/report` (buckets from
  `config/status_mappings.yaml` via `app/reporter.py`; Save to Excel appends
  `output/retail_report_log.xlsx`; Download HTML/PPT), diagnostics
  `/retail/report/diagnostics`. Defect section counts IMPACTED test cases
  [USER 2026-07-06]: TC references the defect AND has not passed yet (passed
  family = the passed_with_dtc bucket, one definition via
  `reporter.passed_family`); passed refs stay visible muted "(+N passed)"
  (`get_retail_defects_impacted` + `compute_impacted_totals`). MB vs Sales =
  the defect's manual DTC O2C flag; unset counts as Sales — diagnostics
  shows an amber "no MB/Sales decision" note listing those defects.
- Sign-off reports `/report/retail`, `/report/ecom`; production defects
  `/prod_defects`
- PPT builders: `app/ppt_utils.py` (shared primitives), `app/ppt_retail.py`,
  `app/ppt_spillover.py`. Export Reports button (`POST /export-reports`,
  `app/report_exporter.py`) writes dated HTML + PPTX for both reports to
  `report_export/`.
