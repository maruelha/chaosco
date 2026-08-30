# Shared report blocks (macros, Excel log, call-outs)

**Type:** component
**URL:** no page — `_report_blocks.html` macros used by the bucket reports
**Storage:** `app/db/core.py` → `report_comments`; the Excel log via `app/report_log.py`
**Code:** `app/reporter.py` (bucket counting) · `app/report_log.py` · `emailer.standalone_html`
**Tests:** `tests/test_reporter_filters.py`, `tests/test_report_exporter.py`

## Purpose

Every bucket status report (Retail, ECOM, Manual Retail, Manual ECOM) must
look and count the same. The blocks, the counting and the Excel writer are
therefore shared — a change to a bucket definition changes every report at
once.

## Architecture

- **Bucket counting** — `app/reporter.py` over ONE config,
  `config/status_mappings.yaml`. `reporter.passed_family` is the single
  definition of "passed" used by the impacted-defect counting everywhere.
- **`_report_blocks.html` macros** (since 2026-08-05): bucket tiles,
  in-progress breakdown, impacted-defects table, inline diagnostics, additional
  comments, and the copy/save script. Retail, ECOM and both Manual reports are
  assembled from them; `retail_report_download.html` stays a deliberately
  separate standalone rendering.
- **Save to Excel** — `app/report_log.py`, one sheet per report in the shared
  report-log workbook.
- **📣 Call-outs / additional comments** — `report_comments`, free-text bullets
  edited directly on the report, keyed per report — the allowlist is
  `spillover`, `retail`, `ecom`, `sales`, `delegated`, `delegated_numbers`
  (a key missing from it makes "+ Add call-out" silently 400, which is exactly
  what happened to `delegated` between 2026-08-26 and 08-27). Since 2026-08-28
  a call-out can be ARCHIVED [USER]: out of the live report, kept with its
  dates in the report page's 🗄 history
  (`POST /report-comments/<id>/archive`).
- **Standalone rendering** — `emailer.standalone_html` inlines the CSS, strips
  the scripts and opens collapsed sections, so a page rendered through the app
  can be attached to an email or saved to disk.

## Rules & gotchas

- A report that needs its own look gets its own template — but the COUNTING
  must still come from `reporter.py`, never re-implemented.
- Reports that already return clean standalone HTML (delegated, missing test
  cases, the prod-defect management report) are attached AS-IS, never run
  through `standalone_html` a second time.

## Related

`[[retail]]` · `[[ecom]]` · `[[manual-tests]]` · `[[spillover]]` ·
`[[report-history]]` · `[[email-reports]]` · `[[export-backup]]`
