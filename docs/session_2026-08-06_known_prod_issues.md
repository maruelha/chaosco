# Session 2026-08-06 — Known Production Issues (rename + rebuild)

Running documentation of this session; updated after every completed step.
Plan agreed in chat before build started.

## Goal

Rebuild the "Known Production Defects" page into **Known Production Issues**
(UI rename only — URLs/endpoints/table/column names stay, same precedent as
"Defects" → "MB ROE Defects"): new fields (Channel, Type, Sub-case, How to
detect), a new column layout + filters on the list, inbox filing support,
and a download/email flow for the page.

## Decisions (Marina, from chat)

- **New fields** on the detail form: `channel` (ECOM | Retail), `type`
  (Defect | Limitation | Risk | Accepted Defect), `sub_case` ("in which
  specific sub-case of the scenario does it happen" — e.g. "several items
  in one order row, GWC applied"), `how_to_detect` ("how can Operations
  find these cases in the system").
- **Scenario becomes a fixed dropdown** (was free text): SFDC, SFS, CNC,
  Return to DC, Return in Store, Exchange to DC, Exchange in Store, GWC,
  **Return/Exchange after GWC**, Giftcard Sale, Split shipment,
  Cancellation, Retail Sale, Retail Return, Retail Exchange, other.
  List lives in `config/settings.yaml` (`prod_defect_scenarios`) so it can
  be extended without a code change. Existing free-text scenario values
  that don't match the list stay visible as an extra "(current)" option in
  that row's dropdown — nothing is silently lost or forced.
- **List page columns, in this order**: Channel · Scenario · Short
  Description · Biz Impact · How to handle · Confluence. References and
  Next Steps move to detail-only (already there, just dropped from the
  list).
- **Filters**: Channel (dropdown) + Scenario (dropdown, same fixed list).
- **Confluence link at the top of the page**: the TRAN space page
  ("Core South and ROE SIT defects related to existing production
  issues") — URL in `config/settings.yaml`
  (`prod_defects_confluence_url`), not hardcoded.
- **Note count** on the list's Edit button ("Edit (2)"), matching the
  other boards. (Notes themselves already exist on the detail page —
  nothing to add there.)
- **Inbox routing**: add `prod_defect` as a filing target (search by
  scenario / short description / technical key); "Known Prod Issue" in
  the picker.
- **Download + email**: "⬇ Download HTML" (dated standalone snapshot, same
  mechanism as the report downloads) and an inline "✉ Send via email"
  action. Implementation choice: reuse the existing `/email-report`
  infrastructure (recipients, mailing lists, SMTP config, same GMX
  sender) rather than building a parallel recipient UI on this page —
  Known Production Issues becomes a 7th entry in `emailer.REPORT_CHOICES`
  / `gather_attachments`; the list page's "✉ Send via email" button links
  to `/email-report` with this report pre-ticked. This satisfies "same
  sender as reports" and "pick from my list or add addresses" (the
  existing recipient-add form) without duplicating that UI.
- **Channel is optional** on existing rows — not backfilled, not forced;
  the filter simply won't match a row until Channel is set on it.
- Page rename is UI text only (title, h1, breadcrumb, dashboard card,
  Spillover page link, notes-registry label, report.html heading) — no
  URL/endpoint/table/column renames.

## Plan / progress

| Step | Content | Status |
|---|---|---|
| ① | Schema: channel, type, sub_case, how_to_detect, how_to_handle + scenario dropdown config | ✅ done |
| ② | Detail form + storage functions for the new fields | ✅ done |
| ③ | List page: columns, filters, note count, Confluence link, page rename | ✅ done |
| ④ | Inbox filing target `prod_defect` | ✅ done |
| ⑤ | Download HTML + email (REPORT_CHOICES entry + send button) | ✅ done |
| ⑥ | Tests + docs (screens.html, database_schema.html, coordination.md) | ✅ done |

Each step implemented, smoke-tested, and confirmed with the full test
suite green before moving to the next. Final suite: **339 tests green**
(10 new in `tests/test_prod_defects.py`).

## Step-by-step notes

- **Field found missing mid-build**: the original ask had a separate
  "How to handle" field distinct from the identify/detect split — it was
  dropped from an early schema pass and caught before step ② finished.
  Added as `how_to_handle` (own column, own form field, own list column).
- **Step ①**: additive `ALTER TABLE` migrations on `known_prod_defects`
  in `app/db/core.py` (same pattern as the existing `comments`/
  `confluence` migration block). `prod_defect_scenarios` (16-value fixed
  list) and `prod_defects_confluence_url` added to `config/settings.yaml`
  — no `settings.local.yaml` change needed (brand-new keys, base fills
  the gap per the merge-by-top-level-key rule).
- **Step ②**: `create_known_prod_defect`/`update_known_prod_defect` gained
  4 new optional kwargs; `web_defects.py` routes pass them through;
  `prod_defect_detail.html` gained Channel/Type/Scenario dropdowns +
  Sub-case/How to detect/How to handle textareas. Scenario dropdown shows
  a legacy value not in the fixed list as an extra "(current)" option —
  verified with a smoke test against a real free-text value.
- **Step ③**: `list_known_prod_defects` gained a note-count subquery +
  channel/scenario filter params; list template columns reordered to
  Channel · Scenario · Short Description · Biz Impact · How to handle ·
  Confluence; filters-bar dropdowns; Confluence link at the top from
  config; page/breadcrumb/dashboard-card/notes-registry/report.html
  heading all renamed to "Known Production Issues" (UI text only, same
  precedent as the MB ROE Defects rename — URLs/table/columns unchanged).
- **Step ④**: `prod_defect` added to `_INBOX_TARGET_TYPES`, a search
  block (scenario / short_description / technical_key), and an existence
  check in `file_inbox_item`. No JS change needed — the inbox picker's
  standard search-and-file path is fully generic (only `shelf` gets
  special-cased in `inbox.html`).
- **Step ⑤**: `known_prod_defects` added to `emailer.REPORT_CHOICES` +
  a `gather_attachments` branch (self-request `/prod_defects` through the
  app, `standalone_html`). New `/prod_defects/download` route (same
  self-request + standalone pattern as the manual-tests report download).
  `/email-report/?reports=<key>` now pre-ticks just that report (new
  `checked_reports` set in `web_email.email_page`; no query param keeps
  the old "everything ticked" default) — lets the list page's own
  "✉ Send via email" button open Email Reports with itself pre-selected,
  reusing the existing recipient/mailing-list/SMTP infrastructure instead
  of building a parallel one.
- **Step ⑥**: `tests/test_prod_defects.py` (10 tests) — new-field
  round-trip, legacy-scenario preservation, list filters + note count,
  Confluence link, inbox filing (incl. nonexistent-target refusal), inbox
  picker option, download snapshot, email pre-tick, `gather_attachments`
  branch. Docs updated: `screens.html` (list/detail cards, dashboard
  card, inbox description, email-report card), `database_schema.html`
  (6 new/changed column rows + notes relation), `docs/claude/
  coordination.md` (inbox target list + reference-entities section).
