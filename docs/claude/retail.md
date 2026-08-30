# Retail

**Type:** mini app (import vertical)
**URL:** `/retail` · `/retail/<id>` · `/retail/report` (+ `/download`, `/ppt`, `/diagnostics`, `/save-excel`)
**Storage:** `app/db/retail.py` → `retail`, `retail_annotations`
**Routes:** `app/web_retail.py`
**Importer:** `app/retail_importer.py` (tab "Retail")
**Templates:** `retail.html` · `retail_detail.html` · `retail_report.html` · `retail_report_download.html` · `retail_report_diagnostics.html`
**Tests:** `tests/test_retail_report_impacted.py`, `tests/test_reporter_filters.py`

## Purpose

Every Retail test-case row (test case × country) with its status, plus the
annotations Marina keeps on top: the next step, the comment history and the
action-needed flag. It is the source for the Retail Status Report and for
`[[retail-tracker]]`.

## Architecture

- **`retail`** — `retail_id` (PK AI), `test_case_id`, `country`,
  `testcase_name`, `testcase_scenario`, `status`, `assigned_to`, plus the
  execution / order / S4 fields, `match_key` (UNIQUE), first_seen, last_seen.
- **`retail_annotations`** — `next_step`, `comment_history`, `action_needed`.
- **List** `/retail`: filters, inline next steps, the shared Comments dialog
  (`_comment_history_dialog.html`), the ⚠ data check
  (`[[row-validations]]`), Teams chats and the ✉️ builder.
- **Status report** `/retail/report`: buckets from
  `config/status_mappings.yaml` via `app/reporter.py`. Since 2026-08-05 the
  page body is assembled from the shared `_report_blocks.html` macros
  (`[[report-blocks]]`); `retail_report_download.html` stays a deliberately
  separate standalone rendering. Save to Excel goes through the shared
  `app/report_log.py`.
- **Diagnostics** `/retail/report/diagnostics` — how each status was bucketed,
  plus the MB/Sales decision gaps.
- The report header carries the **Missing test cases** list, rendered from
  `[[missing-tests]]` (not authored here), and the retrofit section from
  `[[retrofits]]` at the bottom.

## Rules & gotchas

- **Impacted counting** [USER 2026-07-06]: the defect section counts test
  cases that reference the defect AND have not passed yet (the passed family =
  the `passed_with_dtc` bucket, ONE definition via `reporter.passed_family`).
  Passed references stay visible as a muted "(+N passed)"
  (`get_retail_defects_impacted` + `compute_impacted_totals`).
- **MB vs Sales** [USER 2026-07-10]: the Excel's "Sales or DTC" column drives
  the split; the manual DTC O2C flag only fills in when that cell is blank;
  neither → Sales plus an amber "no MB/Sales decision" note on diagnostics.
- The report shows a test-case universe block (total test cases from
  `retail_total_test_cases`, in-tracker count, % passed).

## Outputs

Report page · Copy-TSV · standalone HTML download · PowerPoint
(`app/ppt_retail.py`) · Save to Excel (`output/retail_report_log.xlsx`) ·
email attachment · dated snapshots via Export Reports · history snapshot in
`[[report-history]]`.

## Related

`[[import-pattern]]` · `[[retail-tracker]]` · `[[missing-tests]]` ·
`[[retrofits]]` · `[[defects]]` · `[[report-blocks]]` · `[[manual-tests]]`
