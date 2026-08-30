# ECOM

**Type:** mini app (import vertical)
**URL:** `/ecom/` · `/ecom/<id>` · `/ecom/report`
**Storage:** `app/db/ecom.py` → `ecom`, `ecom_annotations`
**Routes:** `app/web_ecom.py` (Blueprint `ecom`)
**Importer:** `app/ecom_importer.py` (`parse_ecom`, tab "ECOM")
**Templates:** `ecom.html` · `ecom_detail.html` · `ecom_report.html`
**Tests:** `tests/test_ecom_importer.py`, `tests/test_ecom_pages.py`, `tests/test_ecom_report.py`

## Purpose

The ECOM test cases from the workbook, joined LIVE with the shared Jira store
so the board shows both worlds at once: what the Excel says, and what the
ticket currently says.

## Architecture

- **Match key = JIRA ID** [USER 2026-07-05]. Rows without one go to the
  skiplog and are never inserted; `ecom_annotations` keyed by `jira_id`
  therefore survive re-imports.
- **Excel fields and Jira fields stay strictly separate**: `ecom.status` /
  `assigned_to` come from the tab, while `jira_status` / `jira_assignee` live
  in `[[jira-store]]` and are joined by jira id.
- Extra columns vs Retail: `jira_id`, `description_change` (display only;
  feeds the external coverage tool).
- **List** `/ecom`: filters (status / country / scenario + search), Jira-✓
  chip, Δ-Desc pill, Orders via `[[order-details]]`, reporter dropdown filter.
  Rows with Jira data carry a **"Jira N ▸" expander** [USER 2026-07-12]: Jira
  comments + the GATEKEEPER notes (entity `jira`, same key — the shared
  history travels with the ticket), plus live "Jira status" / "Jira assignee"
  columns ("—" until the ticket is imported).
- **Comments button** [USER 2026-07-18] = the SHARED
  `_comment_history_dialog.html` (imported Excel comment read-only + own
  comment_history; `POST /ecom/<id>/comment` → `set_ecom_comment_history`,
  only-this-field upsert keyed by `jira_id`) — the same dialog Retail and
  Spillover use; their copied dialog + JS were replaced by the include
  (`{% set cmt_post_base = '/<vertical>' %}`).
- **Detail**: Excel fields read-only · Jira card read-only from the store (or
  a "no data yet" hint) · annotations · Orders addressed `('jira', jira_key)`
  since 2026-07-16 — the SAME rows as the Gatekeeper Check · Teams chats +
  ✉️ builder at `('jira', key)` · notes via registry entry `ecom`.
- **"↻ Update from Jira"** = `run_jira_import(cfg, 'ecom')`.
- **Status report** `/ecom/report` [USER 2026-07-09]: the SAME bucket
  definitions as Retail (one config, `status_mappings.yaml`); "Not Ready" is a
  known exclusion, visible in the inline diagnostics section — no separate
  diagnostics page. Impacted ECOM-channel defects
  (`get_ecom_defects_impacted`, same rules as Retail).

## Rules & gotchas

- The former "Take over orders from Gatekeeper" button is RETIRED;
  `relink_gatekeeper_orders` and `/ecom/<id>/pull-orders` are kept as inert
  legacy.
- The ECOM report has **no PPT** — not requested.
- A row whose ticket has a reporter outside `ecom_reporters` gets a ⚠
  data-check finding (`[[row-validations]]`, rule `unexpected_reporter`).

## Outputs

Report page + Copy-TSV + standalone HTML download (via
`emailer.standalone_html`, no separate download template) + Save-to-Excel
(ECOM sheet in the shared report log) + an email checkbox + a
`[[report-history]]` snapshot. The `[[retrofits]]` section renders at the
bottom.

## Related

`[[import-pattern]]` · `[[jira-store]]` · `[[gatekeeper]]` ·
`[[order-details]]` · `[[report-blocks]]` · `[[retrofits]]` · `[[delegated]]`
