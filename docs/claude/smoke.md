# CORE SOUTH Smoke Testing (`/smoke/`) — planned 2026-08-27

Mini app for the EU Core South smoke test execution: import the shared
tracking workbook (`EU CS Smoke Test execution.xlsx`), show the eCOM and
Retail scenarios with their steps, plus a status overview.

## Design decisions (planning chat 2026-08-27)

- **File picker upload, not a watched folder** — same pattern as the
  Delegated upload: `<input type="file">` on the page, dated copy kept in
  `data/uploads/` (mirrored by backup). No per-machine folder config.
- **Import filter**: keep only scenarios where `WS` ∈ {eCOM, Retail} AND
  `MB Invoice Validation` = WAHR (boolean TRUE), plus their Step rows.
  Non-WAHR scenarios are DROPPED at import for both WS [USER 2026-08-27].
  In the 2026-08-27 file that is 70 eCOM + 9 Retail scenarios — the low
  Retail count is confirmed correct [USER 2026-08-27].
- **OMNI split (eCOM page only)**: a scenario is OMNI when `Package` is one
  of Click & Collect / Ship From Store / Return in Store (match
  case-insensitively — the file has "Return in Store"); every other eCOM
  scenario is ECOM. Retail has no split.
- **Replace-all per import** — imported tables only, like every other
  vertical; no user-authored data lives in these tables yet.
- Route `/smoke/`, page title "CORE SOUTH Smoke Testing" [USER 2026-08-27].

## Workbook structure (findings 2026-08-27)

Sheet `EU CS Smoke Test execution` (~7,700 rows, 50 cols; also `Comments`
and an empty `Summary` sheet — both ignored).

- `RowType` = Package (62) / Scenario (538) / Step (7,129).
- Steps link to their scenario via `ParentRow` == scenario `RowID`
  (`Parent UUID`/`UUID` agree; exactly 1 orphan step in the file — log,
  skip). `RowID` is unique across scenarios → business key; we still use
  our own technical PKs.
- `MB Invoice Validation` arrives as boolean (pandas: `1.0`/NaN).
- Scenario `Status` values seen: Not Started, In Progress, empty (4 of the
  79 WAHR-filtered scenarios, all eCOM). "Completed" expected once testing
  starts. **Judgment call [Claude 2026-08-27, flag for Marina]:** blank
  Status folds into "Not Started" in the overview counts — matches the
  user-facing meaning (untouched = not started) and the 3-bucket ask; no
  4th "unknown" bucket was requested. Revisit if that reads wrong once
  real data comes in.
- Step-level `Execution Status` and `Progress` are entirely empty in the
  current file — columns imported anyway, they'll fill up later.
- Column-name mapping: `Expected result` → expected_result,
  `Sales Org.` → sales_org, `Plant (DC)` → plant.

## Tables (app/db/smoke.py)

- `smoke_scenarios`: id PK, row_id, package, ws, scenario, comment,
  status, company_code, sales_org, plant, store_code
- `smoke_steps`: id PK, scenario_id FK→smoke_scenarios, row_id, step,
  expected_result, comment, owner_email, owner, ws_executing,
  aspen_ticket, execution_status, progress

## Pages

- **Overview**: stat cards per report — ECOM / OMNI / Retail — total,
  not started, in progress, completed (scenario `Status`).
- **eCOM page**: OMNI section + ECOM section; scenario rows expandable to
  show their steps; text filter on the `Scenario` column.
- **Retail page**: same list, single section.

## Pieces

- `app/db/smoke.py` — schema + all SQL
- `app/smoke_importer.py` — workbook → tables (filter, scenario↔step link)
- `app/web_smoke.py` — Blueprint `/smoke/`: overview (`/`), eCOM (`/ecom`),
  Retail (`/retail`), upload (`/upload`)
- Templates: `smoke.html` (overview + upload, all 3 group headers link
  out), `smoke_ecom.html` (OMNI + ECOM sections), `smoke_retail.html`
  (one section) — shared partial `_smoke_scenarios.html` (macro
  `scenario_group(scenarios, group_key)` — expandable scenario list +
  Scenario filter, reused by all three groups so the identical structure
  isn't tripled). New CSS
  component `details.smoke-scenario` in style.css (per-scenario
  accordion — native `<details>`, no custom JS needed to expand/collapse;
  the only page JS is the live filter, `smokeFilterScenarios()`, mirrors
  the tracker payment-method filter's `oninput` + `data-*` pattern).
- Tests: `tests/test_smoke_storage.py`, `tests/test_smoke_importer.py`,
  `tests/test_smoke_web.py`; route smoke test (`test_routes_smoke.py`)
  auto-covers new GET routes.

Build steps: `docs/build_plan.md` → "CORE SOUTH Smoke Testing".
