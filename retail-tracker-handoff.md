# Retail Requirements Tracker — Handoff Spec

**For: a build session in the TEST COORDINATION DASHBOARD project** (not this repo).
Written 2026-07-04 after a design discussion in the Test Coverage Tool project; that
session's context is summarized here so the building session needs nothing else.
The user is the same person — confirm open questions with them before building.

---

## 1. Purpose

A much-simplified sibling of the Test Coverage Tool: track that Retail (ROE UAT)
**test requirements are tested** across countries. No configuration matching, no rule
engine — the link between a requirement and its test case is EXPLICIT (a test ID),
and "tested" is derived from test case **statuses**, which is exactly why this module
belongs in the coordination dashboard (where statuses live) and not in the coverage
tool (whose competence is config-derived matching, not needed here).

Replaces a 4-tab Excel: `TRACKING_Retail ROE UAT Testcases DTC.xlsx`.

## 2. The Excel being replaced (source structure)

**Tabs 1–3 are the same shape** (Tracking Sales / Tracking Return / Payment methods):
- Rows = requirements, grouped under scenario headings ("1. Retail Sale" → "a. normal").
- Columns: scenario text | test ID (Solman-style, e.g. `GKP0029MU01_…`) | **"DTC
  required"** (18 = all countries, 1 = once anywhere) | comment | computed count |
  one **yes-column per country** (~18 countries: UK, Germany, Switzerland, Poland, …).
- A requirement is DONE when the count of distinct passed countries ≥ required.
- The Return tab shows TWO test IDs (sale + return) — **the sale ID is informational
  only** (which sale the return belongs to); ONLY the return test counts
  [USER 2026-07-04]. Keep the sale reference as a display field.

**Tab 4 (Country-specific payment methods)** is different:
- One row per (country × payment method), e.g. DE + AMEX, DE + VISA…, with a category
  flag (Card / Voucher).
- Up to four "Tested" checkboxes per row — Sale/Return × Card/Voucher — whose test IDs
  are fixed (four known test cases); the category decides which two apply to a row.
- Done when every applicable checkbox is ticked for every active (country, method).

## 3. Decisions ALREADY MADE with the user (do not re-litigate)

1. **LIVE counting, not sticky** [USER 2026-07-04 — the central decision]: the module
   NEVER stores a "yes". Every view derives passed-marks from the dashboard's CURRENT
   test case statuses: status = passed for (test ID, country) → counts; anything else
   → doesn't. A test reopened or failing a retest automatically UN-counts and its
   requirement drops back to incomplete. The report always tells the truth about now.
2. **Manual override escape hatch**: "counted as done by decision" per
   requirement × country (and per tab-4 checkbox), with a MANDATORY reason, stored
   separately from anything derived. This is the only stored "tested" state.
3. **Distinct-country semantics**: a (test, country) pair counts ONCE no matter how
   many passed runs exist. (Lesson learned the hard way in the coverage tool: raw
   counts overstate; count distinct target units.)
4. **"18" is not a number — it means ALL**: store an all-countries sentinel and derive
   the required count from the active country list at view time. Only genuine partial
   requirements (the 1s etc.) store a literal number. (Markets change; hardcoded 18s
   all go stale together.)
5. **Tab 4's row set is living data**: (country × method × category) comes from a
   maintained table, not baked-in rows — methods appear/disappear per country.
6. **Roll-up display**: per area/scenario show "requirements complete: X of Y", never
   sums of yes-marks.
7. **Scenario headings flatten** to one grouping label per requirement (the Excel
   hierarchy is formatting, not information) — recommendation; confirm while importing.
8. **Matching = test NAME, resolved once at import** [VERIFIED against live data
   2026-07-04]: the tracking Excel's IDs (`GKP0005MU01_…`) and the dashboard's
   `retail.test_case_id` (`GKPMU000005`) are two UNRELATED numbering schemes — the
   numeric parts do not correspond (Excel `GKP0013…` = "Verify Cancel transaction" is
   `GKPMU000011` in the DB) and the MU01-style IDs appear in NO column of the retail
   table. What matches is the descriptive name AFTER the first underscore: 79 of 86
   Excel tests match `retail.testcase_name` exactly (case-insensitive, trimmed).
   **Design consequence:** the importer resolves each Excel test to the dashboard's
   `test_case_id` at IMPORT time (by name) and stores that resolved ID on the
   requirement row; unresolved rows are shown for manual pick-and-confirm. The Excel's
   own `GKP…MU01` ID is kept as a display/reference field only. Live counting then
   joins on `test_case_id + country` — exact, immune to name typos.
   The tracking Excel is a ONE-TIME import (requirements only, never re-synced);
   live statuses always come from the `retail` table.
9. **"1 or 5" means 5** [USER 2026-07-04]: the ~30 discount rows whose "DTC
   required" reads `1 or 5` count as required = 5. Encoded in the importer's
   `_parse_required` (so re-imports keep it); `required_raw` preserves the
   original text for provenance.
10. **The 7 tests that won't auto-resolve** (expected at import, verified 2026-07-04):
   - `Verify Suspend transaction functionality`, `Verify Retrieve transaction
     functionality` — not in the retail table at all (yet)
   - `X Store Ex with Neg / with Pos / Even` — renamed in the dashboard to
     `Exchange with Neg / with Pos / Exchange Even`
   - `X Store Ex Even Plus 1` — no counterpart (DB has only 3 exchange tests)
   - `Sale MLMQ Clearance Disc - Cash` — DB name has a typo: `…Clearance Disc - Cas`
11. **Excel retired — the board is the single source of truth** [USER
    2026-07-05]: the import button remains as a re-import tool only;
    yes-marks comparison dropped; override button backlog-only.
12. **Reverse manual pick from the coverage check** [USER 2026-07-06]: each
    passed-but-unmatched test gets a dropdown of still-unresolved
    requirements (`POST /coverage/assign`); assigning sets that
    requirement's `test_case_id` — same stored link as the pick, survives
    re-imports, never overwrites a resolved row.
13. **Requirements are manageable in the app** [USER 2026-07-06] — the Excel
    was only the first seeding:
    - Add form (Import & admin): manual rows carry `source='manual'` +
      `excel_row ≥ 5000`; the importer never prunes or upserts them.
    - Board ✎ edit: name / scenario / required (number or ALL) ONLY —
      `test_name` and `test_case_id` stay dropdown-matched, never editable.
    - One requirement links exactly ONE test; rethink = build_plan Retail
      Tracker backlog item 6.
14. **Clarify list** [USER 2026-07-06]: "→ Clarify" on an unresolved row =
    "ask Sales: does this test exist?"; board section; the entry
    auto-removes when the requirement resolves (both pick paths).
15. **Parked passed tests** [USER 2026-07-06]: Park on the coverage check =
    "tested anyway, not part of our requirements" (`tracker_parked_tests`);
    leaves the coverage unmatched list, shown on the board with live
    per-country passes + inline comment; un-park restores.
16. **Board layout** [USER 2026-07-06]: red Tests-missing gap list at the
    TOP; Clarify and Parked sections at the bottom.
17. **Board polish** [USER 2026-07-09]: Print button removed (Download HTML
    is the only snapshot); Clarify + Parked collapsed by default; Parked
    shows a passed COUNT + "countries ▸" expand like normal rows; actions
    return to a row anchor (`#req-<id>`) — never to the top of the board.
18. **Scenario GROUP filter** [USER 2026-07-09]: the verbose Excel scenario
    headings roll up into Till transactions · Different articles (first
    batch) · Discounts · General payment methods · B2B · PROMAT/FOC · Other
    (substring map `tracker_scenario_groups` in settings.yaml, first hit
    wins — till transactions before the "1. Retail Sale" batch).
19. **Payment-method kick-out** [USER 2026-07-09]: 🚫 per row with MANDATORY
    reason (`inactive_reason`); inactive rows leave ALL counting and live in
    a collapsed "Kicked out" section with "↩ Take back in" (clears the
    reason).
20. **"Expected" pre-resolution** [USER 2026-07-11]: announced-but-not-yet-
    imported tests are NOT unresolved and NOT missing — link the known
    future id via the free-text "⏳ Expect" input; the board shows an amber
    "⏳ expected" pill derived LIVE (id absent from the retail table), which
    self-heals on import. Applied to the cross-store exchange rows:
    GKPMU000057 (uneven higher), GKPMU000058 (cross-store return AND uneven
    lower — one test, two requirements), GKPMU000059 (even), GKPMU000060
    (even plus 1). Remaining truly unresolved: suspend, retrieve,
    Clearance discount CS.

## 4. OPEN questions — resolve WITH THE USER before coding

1. ~~**THE feasibility question**: does the dashboard hold a status **per
   (test case, country)**?~~ — **RESOLVED YES, verified 2026-07-04**: the `retail`
   table keys on exactly (test_case_id, country) — e.g. `GKPMU000066` exists as 9
   rows, one per country, each with its own status; `Passed` is among the status
   values. Step zero is done. Note: the DB currently holds **9 distinct countries**,
   while the Excel's "18 = all" implies a larger market universe — the tracker needs
   its OWN maintained active-country list (decision #4 already requires this).
2. **Migration of existing yes-marks**: the live model stores no "yes" — historical
   Excel marks must either already be visible as passed statuses in the dashboard, or
   be imported as manual overrides with reason "migrated from Excel 2026-07".
   Decide which, per tab, with the user.
3. ~~**Partial counts**: any N vs N specific?~~ — **RESOLVED 2026-07-04**:
   comments that are pure country lists (e.g. "UK, IE") mean THOSE specific
   countries; the user confirmed this is currently the only such case. Stored in
   `requirement_country_targets` (parsed conservatively: only when every
   comma-separated comment token is a known country code; replaced on re-import).
   Counting rule for step 3: named targets present → done when EVERY target
   country passed/overridden; else required_dtc means ANY N distinct.
   Per the user's "only case" steer, the other comments are interpreted as:
   "CORE (6)" = any 6 (plain count), "for all countries where allowed in one
   receipt" = all countries (exchange rows) — correct here if wrong.
4. Override workflow details: who may override, where the reason is displayed.

## 5. Data model sketch (~5 small tables — adapt to the dashboard's conventions)

```
country                (reuse the dashboard's, if one exists; needs an 'active' flag)

retail_requirement     (id, area [sales|return|payment_general], scenario_label,
                        name, test_case_id — the RESOLVED dashboard id (GKPMU…),
                        set at import by name-match (decision #8),
                        excel_test_ref — the Excel's GKP…MU01 id, display only,
                        sale_test_ref NULLABLE — informational only,
                        required_dtc INT NULLABLE, all_countries BOOL — exactly one
                        of the two set, comment)

country_payment_method (id, country, method_name, category [card|voucher], active)
                        -- tab 4 rows; the four fixed test IDs (sale/return ×
                        -- card/voucher) live in config, category picks the two
                        -- that apply

tested_override        (id, requirement_id NULLABLE, cpm_id NULLABLE,
                        test_kind NULLABLE — for tab-4 checkboxes,
                        country, reason NOT NULL, created_at)
                        -- the ONLY stored "tested" state; human decisions only

-- NO stored passes. Completion is computed per request:
--   tabs 1–3: distinct countries where status(test_id, country) = passed,
--             UNION overridden countries; done when ≥ required
--             (required = count(active countries) when all_countries)
--   tab 4:    per (country, method): every applicable test kind passed or overridden
```

## 6. Lessons imported from the coverage tool (why these choices)

- **Compute per request, store only human decisions** — regressions surface by
  themselves; no stale marks; editing/retesting needs no "recount" step. This
  principle carried the coverage tool through every feature; keep it here.
- **Derive "ALL"-type totals from live data** (the coverage tool's auto-derived
  targets); never hardcode counts that change with market scope.
- **Every override carries a why** (the decision-log pattern) — otherwise people
  stop trusting green.

## 7. Build plan — 5 steps, each verified before the next [USER-CONFIRMED 2026-07-04]

Work one step at a time (per `docs/ways_of_working.md`): finish, user verifies,
then move on. "Go for it" applies WITHIN a step; the steps are the checkpoints.

**Structural guardrails (apply to every step):**
- New code goes in NEW files: routes as a Flask Blueprint (e.g.
  `app/web_retail_tracker.py`, registered in `web.py` with two lines), SQL in its
  own module (e.g. `app/db_retail_tracker.py`) — do NOT grow `web.py`/`database.py`.
- NO notes module on this vertical for now (avoids an 11th copy of the note routes;
  overrides carry their own mandatory reason).
- This step plan creates the project's first `tests/` + pytest setup — deliberate:
  it doubles as step 2 of the cleanup plan (`docs/project_review_2026-07-04.md`).

**Testing scope (decided with user 2026-07-04):** test the counting service and the
importer's name resolution — the pure logic where bugs would be silent. Do NOT write
UI/template tests (verified by eye in step 4) or CRUD tests (exercised indirectly).
At most one smoke test that the new pages return 200.

---

**Step 1 — Schema + one-time import of tabs 1–3.**
New tables (§5) in a new DB module. Importer reads the tracking Excel, flattens
scenario headings to a grouping label (decision #7), converts "18" to the
all-countries sentinel (decision #4), and resolves each test name to the dashboard
`test_case_id` (decision #8). Import-result screen shows: auto-resolved (expect 79),
unresolved needing manual pick-and-confirm (expect the 7 of decision #10).
*Tests:* importer resolution with a mini Excel fixture — known names resolve to the
right `test_case_id`; unresolved come back flagged, never silently dropped; "18"
becomes the sentinel, not a literal.
*User verifies:* requirement list matches the Excel; the 7 stragglers confirmed.

**Step 2 — Tab 4 import (country × payment method matrix).** ✅ BUILT 2026-07-04
Populates `country_payment_methods` (147 data rows, 19 countries — tab 4 uses
2-letter codes: AU=Austria, BU=Bulgaria; **Cyprus appears ONLY in tab 4** and is
deliberately NOT added to tracker_countries so "all" stays 18). The four fixed
test IDs are parsed from tab-4 ROW 2 (not config — more faithful than the spec's
config idea) into `tracker_tab4_tests` and all four auto-resolved
(GKPMU000079–82). Category = the X in the Card/Voucher column; ~17 rows without
a clean X (nine "Offline Transactions" rows, the shifted RO rows, Croatia's
comment block, SE "confirm with thorsten", IE Maestro) get category NULL +
Excel text kept as comment + an inline Card/Voucher picker on the page; manual
picks survive re-imports. **Tab 4's "Tested" columns are empty in the Excel** —
so step 5's migration question only concerns tabs 1–3 yes-marks.
*User verifies:* the (country × method × category) matrix matches the Excel;
decide the 17 open categories (or leave "Offline Transactions" rows open if
they aren't payment methods to track).

**Step 3 — Counting service, TEST-FIRST.** ✅ BUILT 2026-07-04
`app/retail_tracker_counting.py` — pure functions (`build_passed_pairs`,
`compute_requirements`, `compute_cpm`) + `compute_from_db(conn)` assembly.
Only status 'Passed' counts (case/whitespace-insensitive). Named targets
require EVERY listed country. 14 counting tests in
`tests/test_retail_tracker_counting.py` (28 total in the suite), all green.
*Live sanity check on real data (2026-07-04):* 22 of 90 requirements done
(sales 10/42, return 10/46, payment 2/2); tab 4 truthfully 0/147 — all four
payment tests are Blocked/Not Ready everywhere. Real-world validation of the
named-targets rule: return Kids articles has 2 passes (DE+UK) against
required 2 but stays OPEN because targets are UK+IE and Ireland hasn't passed
— a plain any-N count would have shown a wrong green.
*User verifies:* pytest green (done) + spot-check the numbers in step 4's UI.

**Step 4 — Read-only UI.** ✅ BUILT 2026-07-04
`/retail-tracker/board` — the Requirements Board, laid out LIKE THE EXCEL
[USER 2026-07-04]: one section per tab (Sales / Return / Payment methods),
rows sorted by test case, one column per country in the Excel's column order
(UK → Finland, headers = the Excel headers), live marks instead of manual
"yes" cells: ✓ passed · ○ executed-not-passed (hover = status) · faint dot =
no execution. Named-target countries get amber-highlighted cells; done rows
get a green tint + "✓ X/N" pill. Summary strip on top (overall + per area +
payment matrix). Tab-4 table below, sorted by country, Sale/Return derived
from the four fixed tests. Dashboard card's primary button now opens the
board; the import/resolution page is "Import & admin".
*User verifies:* numbers checked BY EYE against the current Excel — this is
where real-world discrepancies surface.

**Step 4 revisions after user review (2026-07-04):**
- **NO payment area** [USER]: the Payment methods tab almost entirely
  duplicates section 8 of Sales/Return; those tabs win the dedup and the
  payment tab's two unique rows (OFFLINE Return, Blind return) fold into
  Return (scenario "Payment methods — Return", excel_row offset +1000 to
  avoid key collisions). Board shows two sections: Tracking Sales, Tracking
  Return (+ the tab-4 matrix).
- **Board redesign** [USER]: higher contrast (colored section headers,
  stat cards); column order Test case → Test name (part after "_") →
  Scenario → Requirement → Required → Progress, all visible without
  scrolling; countries hidden behind a per-row "countries ▸" expand
  (country chips: green=passed, amber=executed, gray=none, red ring=named
  target); sections collapsible (<details>).
- **"Tests missing" alarm list** [USER]: red section at the board bottom —
  free-text items, saved in `tracker_missing_tests`, add/delete, red stat
  card when non-empty. For requirements/scenarios with NO test case at all.
- **Rows sort in EXCEL ROW ORDER** [USER 2026-07-04, supersedes the earlier
  by-test-case sort]: each section reads exactly like the Excel tab.
- **Parser fix (bug found by user)**: requirement rows that carry their own
  sub-heading letter ("d. sales cancellation") now REPLACE the current
  sub-heading instead of inheriting the previous one ("c. Sale of giftcard");
  the letter prefix is stripped from the requirement name. Pinned by test.
- **Named-target rules extended** [USER 2026-07-04]: (a) "special case XX"
  in a requirement NAME makes XX a target — "B2B invoice (special case PL)"
  must pass in Poland (its passes elsewhere no longer count); the plain
  "B2B invoice" line stays any-1 ("Poland and one other country").
  (b) Targets PROPAGATE across areas to same-named requirements — Kids
  articles' "UK, IE" now applies to sales AND return.
- **Overachieved display** [USER 2026-07-04]: progress in teal with ★
  (e.g. "✓ 2/1 ★") when passed in more countries than required.
- **Board filters + print** [USER 2026-07-04]: Scenario column bold, moved to
  2nd position; multi-select scenario filter (dialog, client-side) +
  "ALL-countries only" toggle; 🖨 Print button expands all sections and prints
  (print CSS hides buttons/forms/widgets), "As of <date time>" line under the
  title. Tab-4 "Offline Transactions" rows EXCLUDED from import (covered by
  the Sales/Return OFFLINE requirements) and stale rows cleaned on re-import
  (147 → 138 matrix rows, unknown-category 17 → 8).
- **Coverage check on Import & admin** [USER 2026-07-04]: "X of Y passed test
  cases matched to a requirement" + list of unmatched passed tests (live data
  2026-07-04: 69/74 matched; unmatched: Sale MLMQ Discount Reason Code,
  Return Mixed Basket, RWR to GC, Partial Return, X Store Vanilla Return —
  several correspond to Excel rows that are headings WITHOUT a test id, i.e.
  candidate missing requirement lines).
- **TAB-4 RESTRUCTURED — manual per-method check-off** [USER 2026-07-04,
  supersedes the pure-live tab-4 model]: the four fixed tests pass once per
  country, but a pass cannot say WHICH payment methods the run exercised —
  that is human knowledge. New model: per (cpm row × applicable test kind) a
  manual CHECK (table `cpm_checks`, presence = confirmed covered; UNIQUE
  (cpm_id, test_kind)) + an editable `user_comment` per row (e.g. "what was
  NOT tested"; separate column — the importer only writes the Excel-derived
  `comment`). done = all applicable kinds CHECKED; the live pass is shown as
  a "● test passed" hint meaning checking is now possible; summary gains
  `ready` (= all applicable tests passed, checks pending). tested_overrides'
  cpm columns are superseded by cpm_checks (kept in schema, unused).
  New page `/retail-tracker/payment-methods`: the four fixed tests shown as
  cards, filters (country multi-select, category, method text), AJAX
  checkboxes + comments, inline category select. Admin's tab-4 section is now
  a summary + link; the board's tab-4 table shows checked-state + "ready to
  check" pill and links to the page.
- **Round 7 fixes** [USER 2026-07-04]: (a) **Download HTML** button (what was
  actually asked for — the earlier Print button was a misread): dated
  standalone snapshot of the CURRENT view, CSS inlined, filters respected,
  comment inputs flattened to text; Print kept as secondary. (b) Filter bars
  moved INTO each section — Sales and Return each have their own Scenario
  multi-select + ALL-countries toggle, scoped to that section's scenarios;
  the board's tab-4 section got its own bar (country multi / category /
  method text). (c) **Requirement comments**: editable Comment column on
  every board row (`retail_requirements.user_comment`, blur-save AJAX
  `POST /retail-tracker/requirements/<id>/comment`, importer never touches
  it, flattened to text in the download). (d) Payment methods page: category
  editable ONLY while unknown — once set, only the checks change.
- Known cosmetic leftover: the Excel names the same test differently in two
  places, so Return contains two near-duplicate pairs (Blind Return /
  OFFLINE Return ↔ GKP2002; Blind Return giftcard / Blind return ↔ GKP1015)
  — names differ, so dedup correctly keeps both; clean up in the Excel or
  ignore.

**Step 5 — REVISED 2026-07-05 [USER]:** the tracking Excel is RETIRED as of
now — the board is the single source of truth (the import button stays as a
re-import tool only). The historical yes-marks comparison is DROPPED (not
needed). The override button ("counted as done by decision") moves to the
backlog — build only if the need ever arises.

*(original step for reference)* **Step 5 — Overrides + migration + go-live.**
Override button with MANDATORY reason (decision #2). Then resolve open question #2
with the user: historical Excel yes-marks either already visible as passed statuses,
or imported as overrides with reason "migrated from Excel 2026-07" — decide per tab.
*User verifies:* report matches reality → retire the Excel.
