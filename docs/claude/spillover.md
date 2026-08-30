# Core South Spillover

**Type:** mini app (import vertical)
**URL:** `/spillover` · `/spillover/<id>` · `/spillover/report` (+ `/view`, `/table`, `/ppt`)
**Storage:** `app/db/spillover.py` → `spillover`, `spillover_annotations`, `spillover_report_selection`
**Routes:** `app/web_spillover.py` (also home of the generic `/order-details/...` routes)
**Importer:** `app/spillover_importer.py` (tab "Core South Spillover")
**Templates:** `spillover.html` · `spillover_detail.html` · `spillover_report_select.html` · `spillover_report_view.html` · `spillover_report_table.html`
**Tests:** `tests/test_spillover_default_filter.py`, `tests/test_spillover_report_table.py`, `tests/test_spillover_whom_report.py`

## Purpose

The Core South spillover items — what is NOT finished and travels into the
next phase — with the annotations sign-off needs: importance, criticality, the
comment that goes into the report, and who it sits with.

## Architecture

- **`spillover`** — `spillover_id` (PK AI), type, name, country, area, status,
  assigned_to, external_id, order_numbers, content, comment, `excel_row`,
  `match_key` (UNIQUE), first_seen, last_seen.
- **`spillover_annotations`** — `importance_for_signoff`, `next_step`,
  `comment_history`, `critical_for_signoff`, `comment_for_signoff`,
  `signoff_group`, and (2026-07-09) `with_whom` (Sales | MB).
- **List** `/spillover`: frozen-pane table, per-row Details / Order details /
  Comments / Notes. "With whom" column (inline AJAX select + multi filter) and
  a "Status report" filter/column (in / not in `spillover_report_selection`,
  green ✓).
- **Report** — selection at `/spillover/report` (persisted in
  `spillover_report_selection`), then TWO coexisting views [USER 2026-07-10:
  the table is ADDITIONAL, not a replacement]:
  - `/spillover/report/view` — the original detailed card view, printable,
    critical-first, wins + Additional sections.
  - `/spillover/report/table` — compact table grouped by `with_whom`
    (Sales → MB → Unassigned), critical-first inside each section,
    inline-editable `comment_for_signoff` column, 📣 call-outs box
    (`report_comments`) edited directly on the report.
  Cross-links in both toolbars and on the selection screen. PPT at
  `/spillover/report/ppt` (card slides, unchanged). Email and export attach
  the DETAILED view.
- **Sign-off reports** `/report/retail` and `/report/ecom`
  (`app/web_reports.py`, template `report.html`) — the spillover rows split by
  AREA: `/report/retail` excludes ecom+omni, `/report/ecom` keeps only them and
  additionally renders the `[[known-production-issues]]` section. Both hide the
  statuses listed in `spillover_hidden_statuses`.

## Rules & gotchas

- The Status-report filter DEFAULTS to "In report" on a fresh page open
  [USER 2026-07-18] — only a MISSING `in_report` param gets the default; the
  form's explicit "All" (present but empty) shows everything, so Clear returns
  to the default view.
- The `/report-comments` add route also accepts `'ecom'`.

## Outputs

Detailed report view (print + HTML download + email) · compact table view ·
PowerPoint (`app/ppt_spillover.py`) · dated snapshots via Export Reports.

## Related

`[[import-pattern]]` · `[[known-production-issues]]` · `[[order-details]]` ·
`[[report-blocks]]` · `[[email-reports]]` · `[[export-backup]]`
