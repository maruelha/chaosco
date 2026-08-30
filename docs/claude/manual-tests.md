# Manual Test Cases (Retail + ECOM)

**Type:** mini app (import vertical, two streams)
**URL:** `/manual/retail`, `/manual/ecom` (+ `/report`, `/report/download`)
**Storage:** `app/db/manual_tests.py` → `manual_retail`, `manual_ecom`
**Routes:** `app/web_manual_tests.py` (ONE Blueprint for both streams)
**Importer:** `app/manual_importer.py` (`parse_manual(cfg, vertical)`)
**Templates:** `manual_list.html` · `manual_report.html`
**Tests:** `tests/test_manual_importer.py` (incl. a FIELDS↔importer drift guard), `tests/test_manual_pages.py`

## Purpose

The two "Manual Test Cases" tabs — the cases that are executed by hand and
were previously invisible to every report. Read-only lists plus the simple
status report, so manual coverage can be reported like the rest.

## Architecture

- ONE importer module and ONE storage module for BOTH tabs, but **separate
  header maps** (the tabs are siblings, not identical) and **separate tables**
  (architecture rule 1).
- **Tab shapes**: `| Retail` ≈ the Retail tab + `store_no` / `sales_status`
  (plus a bare duplicate "Order number" column, deliberately unmapped);
  `| ECOM` ≈ the ECOM tab (`jira_id`, `description_change`) but `jira_id` is
  BLANK in the data.
- **Match key per vertical** (`db.manual_tests.KEY_FIELDS`): Retail = test case
  + country like the Retail tab; **ECOM = the Testcase Scenario ALONE**
  [USER 2026-08-06]. The tab repeats the same tc+country once per partner shop
  (the 2026-08-05 CDI0000MU34 "duplicates" were per-partner rows); the team
  then filled the scenario column as the differentiator, e.g.
  "ALLL.AT_ Zalando", unique per row in ROE(49): 179/179. One deliberately
  narrow key = only ONE editable column can break row identity.
- ONE line per key stays enforced: in-file repeats go to the skiplog
  ("duplicate scenario in file" / "duplicate test case+country in file") and
  show as a red count on the import screen.
- **Pages**: `/manual/<stream>` list (dropdown filters + free search; ECOM
  shows the Jira ID column, Retail the Key User) and `/manual/<stream>/report`
  — the simple Retail pattern assembled from the shared `[[report-blocks]]`
  macros.
- **Defects section** (`get_manual_defects_impacted`): the defect is
  referenced in the tab's `defect_id_ref` AND the Defects-tab channel matches
  (retail/ecom, case-insensitive); same counting and MB/Sales rules as Retail.
  Referenced defects of another or blank channel render as a red ⚠ box
  (`get_manual_offchannel_defect_refs`) — never silently dropped.

## Rules & gotchas

- **The pipe in the sheet names is deliberate**: the workbook still contains
  two older EMPTY stub tabs WITHOUT the pipe, which must stay ignored.
- Migration 2026-08-06 in `init_schema`: old-format `manual_ecom` keys
  (containing `||`) are deleted once — the scenario texts were rewritten in the
  workbook, so those rows could never match again; the next import re-fills.
- `imports.manual_retail` / `imports.manual_ecom` in settings.yaml — a local
  `imports:` override replaces the whole block, so add the entries there too.
- No annotations tables yet: the lists are read-only, with no notes, detail
  pages or row validations in v1.

## Outputs

Two report pages · Copy-TSV · Download HTML (standalone via
`emailer.standalone_html`) · Save to Excel (sheets "Manual Retail" / "Manual
ECOM" via `app/report_log.py`) · two email checkboxes · two dashboard cards ·
`[[report-history]]` snapshots.

## Related

`[[import-pattern]]` · `[[retail]]` · `[[ecom]]` · `[[report-blocks]]` ·
`[[report-history]]` · `[[row-validations]]`
