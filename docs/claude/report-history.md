# Report history

**Type:** mini app
**URL:** `/report-history/` (+ `/import-tabs`)
**Storage:** `app/db/report_history.py` → `report_history`
**Routes:** `app/web_report_history.py`
**Importer:** `app/report_history_importer.py` (snapshot + Excel-tab parsing)
**Templates:** `report_history.html`
**Tests:** `tests/test_report_history.py`

## Purpose

[USER 2026-08-05: "why should I copy something to excel that can be
automatically saved"] The bucket numbers of every status report, per date —
replacing the hand-pasting of Copy-TSV rows into the workbook's ReportRetail /
ReportECOM tabs.

## Architecture

One row per bucket report (`retail` / `ecom` / `manual_retail` /
`manual_ecom`) + reported date, in the APP's 9 bucket columns. Filled two ways:

1. **Email send** — `web_email.send()` calls `snapshot_reports()` after a
   SUCCESSFUL send, for the ticked bucket reports, dated with the email page's
   date. A snapshot failure never blocks the mail (the result banner reports
   it). The same date sent again REPLACES the row.
2. **"⤓ Import from Excel tabs"** on `/report-history` — `import_report_tabs()`
   parses the workbook tabs (label row found by the "date" cell; `21.05.2026`
   and datetime cells; description rows skipped; non-bucket columns like
   "Total number of test cases", "Sense check", "Waiting for SF creation" and
   the combined "In Progress / In Clarification" ignored) and upserts per
   date with source `'excel'` — re-runnable.

Page with a report switcher, newest first, a source pill and Copy-TSV; History
buttons sit on all four report toolbars. Config `report_history_tabs`
(defaults ReportRetail / ReportECOM).

## Related

`[[retail]]` · `[[ecom]]` · `[[manual-tests]]` · `[[email-reports]]`
