# MB ROE Defects

**Type:** mini app (import vertical)
**URL:** `/defects` · `/defects/<defect_id>`
**Storage:** `app/db/defects.py` → `defects`, `defect_annotations`
**Routes:** `app/web_defects.py`
**Importer:** `app/read_defects.py` (tab "Defects"); SolMan sync `app/solman_sync.py`
**Templates:** `defects.html` · `defect_detail.html`
**Tests:** `tests/test_importers.py`, `tests/test_defects_channel_filter.py`

## Purpose

Every defect from the workbook's Defects tab, with the annotations that the
Excel has no room for: business impact, reach, retest needs, the next step,
and the flags that decide where a defect shows up (DTC O2C, daily).

## Architecture

- **`defects`** — 21 columns incl. `defect_id` (PK), `channel`,
  `solman_status`, `priority`, `assigned_to`, `sales_or_dtc`, `excel_row`,
  `first_seen`, `last_seen`.
- **`defect_annotations`** (user-authored, importer never touches):
  `description`, `business_impact`, `reach`, `retest_needs`, `next_step`,
  `action_needed`, `comments`, `dtco2c` (0/1 = "MB follows up"),
  `dtco2c_resp`, `daily` (0/1 = discuss on the DTC O2C Daily), `updated_at`.
- **List** `/defects`: filters, inline DTC O2C + Daily toggles, sortable,
  blocked-test-case counts, search.
- **Detail** `/defects/<id>`: annotation form → notes → "add to meeting prep"
  → the imported fields read-only.
- **SolMan sync** `app/solman_sync.py`: targeted UPDATE of
  `defects.solman_status` + `assigned_to` from the "Data aggregated by Defect"
  SolMan export; skips Withdrawn/Confirmed defects. Route `POST /solman-sync`
  (no dashboard card — triggered where configured). Config keys:
  `solman_export_folder`, `solman_export_stem`, `solman_export_sheet`.

## Rules & gotchas

- **`channel` arrives in MIXED casings** from the Excel ("ecom" / "Ecom" /
  "Retail") and is stored AS-IS. The `/defects` channel filter collapses the
  casings into one uppercase dropdown entry, matches case-insensitively, and
  the list column displays uppercase [USER 2026-07-18]
  (`get_filter_options` + `list_defects`). The impacted-defect report queries
  were always `LOWER(TRIM(channel))`.
- **MB vs Sales** [USER 2026-07-10]: the Excel's "Sales or DTC" column drives
  the split on the reports — DTC → MB, Sales → Sales. The manual DTC O2C flag
  only fills in when that cell is blank; neither → Sales, with an amber
  "no MB/Sales decision" note on the Retail diagnostics.

## Related

`[[import-pattern]]` · `[[retail]]` · `[[ecom]]` · `[[spillover]]` ·
`[[meeting-prep]]` · `[[notes]]`
