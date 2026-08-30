# Retail Requirements Tracker

**Type:** mini app
**URL:** `/retail-tracker/board` · `/retail-tracker/payment-methods` · `/retail-tracker/` (import & admin)
**Storage:** `app/db_retail_tracker.py` → `retail_requirements`, `tracker_countries`, `country_payment_methods`, `cpm_checks`, `tracker_tab4_tests`, `tracker_clarify`, `tracker_parked_tests`, `requirement_country_targets`, `tested_overrides`
**Routes:** `app/web_retail_tracker.py`; counting in `app/retail_tracker_counting.py` (pure functions); importer `app/retail_tracker_importer.py`
**Templates:** `retail_tracker.html` · `retail_tracker_board.html` · `retail_tracker_payment.html`
**Tests:** `tests/test_retail_tracker_*.py` (counting, importer, assign, expected, kickout, manage)

## Purpose

Read when working on `/retail-tracker/*`. Full spec + decision log:
`retail-tracker-handoff.md` (repo root) — that file is authoritative for the
counting semantics and every user decision.

## The one rule

**Nothing is stored as "tested".** Completion derives live from `retail`
statuses on every request (only status `Passed` counts, case-insensitive);
a reopened test un-counts automatically. The only stored tested-states are
human decisions: `tested_overrides` (requirements, mandatory reason — UI
pending, build plan item 1) and `cpm_checks` (tab-4 per-method check-off).

## Modules (the template for NEW verticals)

- `app/db_retail_tracker.py` — schema + all SQL
- `app/retail_tracker_importer.py` — one-time import of the 4-tab tracking
  Excel; test resolution by NAME after the first underscore (the Excel's
  GKP…MU01 ids are unrelated to the dashboard's GKPMU000… ids); named-target
  rules ("UK, IE" comments, "special case PL" names, propagation across areas
  by requirement name); "1 or 5" imports as 5
- `app/retail_tracker_counting.py` — pure counting functions +
  `compute_from_db(conn)`
- `app/web_retail_tracker.py` — Blueprint `/retail-tracker`
- Tests: `tests/test_retail_tracker_importer.py`,
  `tests/test_retail_tracker_counting.py`

## Tables

- `tracker_countries` — active-country list ("18 = ALL" derives from it)
- `retail_requirements` — per requirement: area (sales/return — NO payment
  area, that tab was duplicative), scenario_label, name, excel_test_ref,
  test_name, test_case_id (resolved; manual picks survive re-import),
  required_dtc / all_countries, user_comment (importer never touches),
  source ('excel' | 'manual' — manual rows are user-added, excel_row ≥ 5000,
  never pruned/upserted by the importer), UNIQUE(area, excel_row);
  payment-tab folded rows use excel_row + 1000. Editable via board ✎:
  name/scenario/required ONLY — test_name + test_case_id are dropdown-only
  [USER 2026-07-06]
- `tracker_clarify` — "ask Sales: does this test exist?" per unresolved
  requirement; auto-removed when the requirement resolves (both pick paths)
- `tracker_parked_tests` — passed tests judged out of requirement scope
  ("tested anyway"); excluded from the coverage check's unmatched list,
  shown on the board with live per-country passes + inline comment
- `requirement_country_targets` — named specific-country targets
- `country_payment_methods` — tab-4 matrix + user_comment;
  `tender_type_code` (voucher/unknown only — card is ZPSP, derived at
  display time, never stored), `source` (free-text provenance, backfilled
  to "Iuliia analysis" once when the column was created), `origin`
  ('excel' | 'manual' [USER 2026-08-06] — the Excel tab-4 turned out
  incomplete; manual rows are user-authored voucher/card lines the
  importer never prunes; if the Excel later grows the same country +
  method, the import takes it over — origin flips to 'excel', source and
  tender_type_code survive); `tracker_tab4_tests` — the four fixed tests;
  `cpm_checks` — manual per-method confirmations. The board's red alarm list
  is NOT a tracker table any more [USER 2026-08-30]: it comes from the
  Missing Test Cases module (`missing_test_cases`, see
  `docs/claude/missing-tests.md`); the old `tracker_missing_tests` table was
  copied over once and dropped

## Screens

- Board `/retail-tracker/board` — red Tests-missing gap list AT THE TOP
  [USER 2026-07-06] (shared with the Retail status report since 2026-08-30 —
  maintained in `/missing-tests/`), followed by the read-only Retail retrofit
  mirror [USER 2026-08-30], then Excel-order sections with per-section scenario
  GROUP filters [USER 2026-07-09: Till transactions · Different articles
  (first batch) · Discounts · General payment methods · B2B · PROMAT/FOC ·
  Other — substring mapping in settings.yaml `tracker_scenario_groups`,
  first hit wins] + ALL-countries toggle, per-row country chips expand, inline
  comments, ✎ edit dialog (name/scenario/required; redirect returns to the
  row anchor `#req-<id>`, not the top), overachieved "✓ X/N ★", Download
  HTML (dated standalone snapshot; Print REMOVED [USER 2026-07-09]); at
  the bottom, both COLLAPSED by default [USER 2026-07-09]: Clarify list
  ("ask Sales — does this test exist?") then parked list ("Not part of our
  requirements — tested anyway", count + "countries ▸" expand like normal
  rows, inline comment, un-park). Hash helper opens collapsed sections on
  anchor navigation. Both bottom lists (and "Kicked out" on payment methods)
  use `ui-section--gray` [USER 2026-07-18] — without a color class the shared
  section summary is white-on-white (headings looked empty).
- Payment methods `/retail-tracker/payment-methods` — per (country × method ×
  kind) AJAX check-off, "● test passed" hints, category editable only while
  unknown, filters (country dialog · Methods ▾ show/hide checklist
  [USER 2026-07-23: all ticked by default, untick to hide] · category ·
  method text; filter state survives reloads via sessionStorage
  [USER 2026-07-24]). Mass actions [USER 2026-07-24]: row checkboxes +
  select-all-visible, "Kick out selected" (one reason for all, filtered-away
  rows auto-deselected) and "Take back in selected" in the kicked-out
  section — both `POST /payment-methods/bulk-active` (ids comma-separated). 🚫 kick-out per row [USER 2026-07-09]: reason MANDATORY
  (`POST /payment-methods/<id>/active`, `set_cpm_active`; `inactive_reason`
  column) — inactive rows leave ALL counting (compute_cpm skips them,
  cpm_counts counts active only) and live in a collapsed "Kicked out"
  section with the reason + "↩ Take back in" (clears the reason). The
  section is split into TWO lists [USER 2026-07-23]: "Not able to test in
  testenvironment" (reason matched via `_kickout_env_blocked`, letters-only
  so spacing/case variants hit; kick-out prompt is prefilled with the
  phrase) and "Other reasons". **Tender type code + Source columns +
  manual add [USER 2026-08-06]:** card rows show fixed non-editable
  "ZPSP"; voucher/unknown rows get an inline-editable tender type code
  (`POST .../tender-code`). Source is inline-editable on every row
  (`POST .../source`). "➕ Add payment method" dialog
  (`POST /payment-methods/add`, `add_cpm_manual`) creates a manual line
  for a country + method the Excel was missing — country/method/source
  required, source required so provenance is never ambiguous; rejects a
  duplicate (country, method) with a red banner. Manually added rows show
  a gray "manual" pill next to the method name and behave like any other
  row everywhere else (counting, checks, kick-out, comment).
- Import & admin `/retail-tracker/` — re-runnable import, add-requirement
  form (manual rows, born unresolved), unresolved-test manual picks + "→
  Clarify" per row + free-text "⏳ Expect" input [USER 2026-07-11]: link a
  FUTURE dashboard test id that the retail table doesn't carry yet (counts
  as resolved, amber "⏳ expected" pill on the board, `counts.expected`
  line; NO stored state — derived live, self-heals when the import brings
  the test; used for the 4 cross-store exchange tests GKPMU000057-60,
  where GKPMU000058 deliberately feeds TWO requirements. The pill asks
  `test_case_id in db.get_retail_test_ids(conn)` — ids only. It used to test
  membership of the NAME lookup (`get_retail_test_options`, which filters
  `testcase_name IS NOT NULL`), so a Retail tab importing ids but no names
  pilled EVERY board row while `counts.expected` stayed small — board and
  counts box disagreeing is the tell [USER 2026-07-28]. Names stay
  name-based, but only for `display_test_name`), coverage check (passed tests not linked to any
  requirement) with reverse assignment (`POST /coverage/assign`,
  `assign_test_to_unresolved` — refuses already-resolved rows; one test per
  requirement, rethink is backlog item 6 in build_plan) and Park button
  (`POST /coverage/park`)

## Status 2026-07-05

The tracking Excel is RETIRED — the board is the single source of truth
(import button = re-import tool only). Yes-marks comparison dropped.
Override button is backlog-only (table + counting support already exist).

## Related

`[[retail]]` · `[[missing-tests]]` · `[[retrofits]]` · `[[import-pattern]]` ·
`[[defects]]`
