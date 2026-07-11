# Retail Requirements Tracker

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
  `tracker_tab4_tests` — the four fixed tests; `cpm_checks` — manual
  per-method confirmations; `tracker_missing_tests` — red alarm list

## Screens

- Board `/retail-tracker/board` — red Tests-missing gap list AT THE TOP
  [USER 2026-07-06], then Excel-order sections with per-section scenario
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
  anchor navigation.
- Payment methods `/retail-tracker/payment-methods` — per (country × method ×
  kind) AJAX check-off, "● test passed" hints, category editable only while
  unknown, filters. 🚫 kick-out per row [USER 2026-07-09]: reason MANDATORY
  (`POST /payment-methods/<id>/active`, `set_cpm_active`; `inactive_reason`
  column) — inactive rows leave ALL counting (compute_cpm skips them,
  cpm_counts counts active only) and live in a collapsed "Kicked out"
  section with the reason + "↩ Take back in" (clears the reason)
- Import & admin `/retail-tracker/` — re-runnable import, add-requirement
  form (manual rows, born unresolved), unresolved-test manual picks + "→
  Clarify" per row + free-text "⏳ Expect" input [USER 2026-07-11]: link a
  FUTURE dashboard test id that the retail table doesn't carry yet (counts
  as resolved, amber "⏳ expected" pill on the board, `counts.expected`
  line; NO stored state — derived live, self-heals when the import brings
  the test; used for the 4 cross-store exchange tests GKPMU000057-60,
  where GKPMU000058 deliberately feeds TWO requirements), coverage check (passed tests not linked to any
  requirement) with reverse assignment (`POST /coverage/assign`,
  `assign_test_to_unresolved` — refuses already-resolved rows; one test per
  requirement, rethink is backlog item 6 in build_plan) and Park button
  (`POST /coverage/park`)

## Status 2026-07-05

The tracking Excel is RETIRED — the board is the single source of truth
(import button = re-import tool only). Yes-marks comparison dropped.
Override button is backlog-only (table + counting support already exist).
