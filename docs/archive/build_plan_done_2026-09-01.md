# Build plan — finished sections, moved out 2026-09-01

Moved here from `docs/build_plan.md` in docs-cleanup round 1, step 5
("when something is added, something goes" [USER 2026-09-01]). These are
the FULL build logs of finished modules and the 2026-07-04 refactoring
steps 1-6, verbatim.

**Archive rule applies:** frozen history, never updated, never quoted as
current. Open items that were still live at the time of the move were
carried back to `build_plan.md` -- if something reads as "open" below, the
live copy in `build_plan.md` (or MarinaCheckSoon) is the truth, not this
snapshot.

---

### Email Reports (`/email-report/`) — ✅ BUILT 2026-08-31/09-01

Four changes requested [USER 2026-08-31]:

1. ✅ Opens with NOTHING ticked, plus All / None buttons and a live
   "n of 13 selected" hint.
2. **Groups** = a whole saved send: recipients + reports + own subject/text.
   ✅ done — `email_list_reports` table, `email_lists.subject/body`, the chip
   applies members + reports + wording in one click.
3. **"↻ Regenerate text"** so the report list in the mail matches the ticks;
   auto-follows while the text has not been hand-edited. ✅ done —
   `POST /email-report/text` + the ↻ button; `default_texts` distinguishes
   "not asked" from "nothing ticked".
4. **Adding a recipient must not wipe** the typed text or the ticked reports —
   ✅ done — those endpoints answer `fetch` with JSON and the page updates in
   place; the redirect stays as the no-JavaScript fallback.
   Tests: `tests/test_email_page_features.py` (12).

Done the same day: the Retail report's three copies (page download, email
attachment, export snapshot) now go through ONE renderer — see
`docs/claude/retail.md`; and the Missing Test Cases report shows no counts.


---

### Missing Test Cases (`/missing-tests/`) — ✅ BUILT 2026-08-30

One list instead of two that drifted apart (config `retail_missing_categories`
on the Retail status report vs `tracker_missing_tests` on the Requirements
board). Entry = title + detail note; second section mirrors the Retail
retrofits read-only with a per-retrofit test-coverage note and their status
(Confirmed / Potential = "not confirmed yet"). HTML report + download, email
report choice "Missing Test Cases (Retail)", copy & paste email text.
Seeded ONCE from both old places (`missing_test_meta.seeded`). Deep dive:
`docs/claude/missing-tests.md`.

Corrections the same day [USER 2026-08-30]:
- the **test coverage note moved to the Retrofits page** (column
  `retrofits.test_coverage_note`); Missing Test Cases, the board and the
  reports only display it
- the **Requirements board also shows the retrofit list** (read-only, under
  the ⚠ Tests missing box)

Open/possible next steps:
- report heading wording on the Retail status report ("Missing test cases
  (on top of total test cases)") — to confirm
- ECOM has no equivalent list yet; the module is Retail-only on purpose



---

### Sustainphase Issues (`/sustain-issues/`) — PLANNED 2026-08-28

From the **Defects tab** of `DTC_Sustainphase_Tracking….xlsx` (planning
chat 2026-08-28; tab is still an EMPTY template — 21 headers in row 1,
built against headers + synthetic tests, first real upload is the true
test). Columns: Channel · Sales or DTC · ASPEN STATUS · Defect ID ·
Short description · more Defect description · Comment · raised by ·
order number · Date Reported · Date Closed · Priority · Assigned to ·
Tech Team · Country · Scenario · affected testcases · Retest Dependency ·
Does it block execution · Exists in production (IGNORED entirely [USER])
· Defect reason.

Decisions [USER 2026-08-28]: issues can exist before their ASPEN id →
auto-assigned placeholder key `SUS-001`-style (technical PK anyway);
once the real Defect ID arrives the placeholder disappears from view but
stays SEARCHABLE (kept as former id). Upload = file picker, name
contains `DTC_Sustainphase_Tracking`. Authored per issue: call-outs/
comment + next step (generic archive, entity `sustain_issue`).
Dashboard card next to Sustainphase Monitoring / Smoke — NOT linked to
them for now. Steps one at a time, test+commit after each:

1. ~~Storage `app/db/sustain_issues.py`~~ ✅ DONE 2026-08-28:
   `sustain_issues` (issue_key UNIQUE = defect_id or SUS-nnn
   placeholder; `former_placeholder` kept when the real id "promotes"
   the issue — placeholder numbers never reused; upsert by defect_id,
   fallback match by normalized short description; absent rows KEPT,
   last_seen shows staleness; Exists-in-production ignored) + authored
   `sustain_issue_annotations` (callouts + next_step, follow the key on
   promotion). Registered in the `database.py` facade.
   `tests/test_sustain_issues_storage.py` (6 tests, incl. the
   promotion + annotation-migration path); suite 617.
2. ~~Importer + upload~~ ✅ DONE 2026-08-28:
   `app/sustain_issues_importer.py` — Defects tab found by name, columns
   mapped by NORMALIZED HEADER NAME prefix (headers contain newlines;
   position-mapping would break on inserted columns), dates → ISO,
   Exists-in-production unmapped/dropped; ParseError on missing tab or
   headers; empty tab imports fine (the template starts empty — verified
   against the real file: ok, 0 rows). `app/web_sustain_issues.py`
   Blueprint `/sustain-issues/` registered in web.py: upload
   (name-contains guard, dated `sustain_issues_*.xlsx` copy), plain
   count line until step 3, plus the callouts/next-step save routes
   (`POST /sustain-issues/issue/<key>/callouts|next-step`).
   `tests/test_sustain_issues_importer.py` (4) +
   `tests/test_sustain_issues_web.py` (6); suite 628.
3. ~~List view~~ ✅ DONE 2026-08-28: expandable rows (kpd pattern —
   `details.si-row` added to the shared expandable-row CSS; deliberately
   NOT a wide table, Marina's earlier feedback on horizontal scrolling).
   Summary: key (former placeholder as tooltip) · short description ·
   ASPEN-status chip · priority · red "blocks execution" chip ·
   📣 call-outs marker · → next-step preview · channel/country/dates.
   Body: description, Excel comment, meta line, call-outs textarea +
   next-step input with ↻/🕘 (entity `sustain_issue`, registered in the
   REGISTRY). Filters Channel/ASPEN status/Country/Priority
   (client-side, distinct values); Open vs Closed sections split by
   Date Closed (Closed collapsed). Web tests now 10; suite 632.
4. ~~Search source~~ ✅ DONE 2026-08-28 together with the search
   extensions below: "Sustainphase Issues" block (order number +
   issue_key + former SUS-nnn placeholder — a promoted issue stays
   findable by its old key; hits link to the card), "Smoke scenarios"
   block (scenario name + step ASPEN tickets; ws picks /smoke/ecom vs
   /smoke/retail) and a dedicated "Delegated Testing" group (key +
   summary of delegated-tagged tickets → DELEGATED ticket detail, not
   the gatekeeper view). All new SQL uses portable
   `LOWER(col) LIKE LOWER(?)`; every block tolerates its tables missing.
   `tests/test_search_new_sources.py` (3); suite 635.
5. ~~Dashboard card + docs sweep~~ ✅ DONE 2026-08-28: card after
   Sustainphase Monitoring (issue-count badge). Docs:
   `docs/claude/sustain-issues.md` (new deep-dive), `screens.html`,
   `database_schema.html` (2 table-cards, count 70→72),
   `architecture.html`, `dashboard_cards.html`, CLAUDE.md; judgment
   calls (SUS- prefix, description-as-placeholder-identity) flagged in
   MarinaCheckSoon; click-through checklist
   `docs/marina_notes/SessionTest_2026-08-28_b.html` (also covers the
   Smoke upgrades + search extensions).

**Parked [USER 2026-08-28]:** SPOT_CHECKS tab → its own similar
upload-and-view mini app, ANOTHER session. SMOKETEST_KT tab: ignored
(KT tracking lives on the Smoke scenarios instead — see Smoke item 9).

~~Search extensions~~ ✅ DONE 2026-08-28 — folded into step 4 above.


---

### Core South Sustainphase Monitoring (`/sustain/`) — PLANNED 2026-08-27

Daily GBS Operations checklist for the sustain phase (O2C DTC). Source
file: `…DTC_GBS Operations_checklist.xlsx` — the prefix before `DTC_GBS`
changes per file (it encodes the date window, e.g. `1_0109_0409-O2C`), so
the upload matches on the **filename suffix**. Deep-dive doc
`docs/claude/sustain.md` gets written in step 1 and grows with each step.

**Workbook structure.** ⚠ **Updated 2026-08-31 — a NEW version of the
same file arrived; the app follows it now** (details and the decoded
formulas: `docs/claude/sustain.md`, section "Change log"): headers moved
to row **5** (data from row 6) because the instruction line was dropped,
a free-text column **M "Comments/Observations"** was added, and the
workbook's own summary definitions changed (DUE excludes N/A, COMPLETED =
OK only). The importer now **locates** the header row instead of
hardcoding it, so both file versions import; `summary_counts` follows the
new definitions [USER 2026-08-31]; comments are imported and shown but
never affect a status. The description below is the ORIGINAL 2026-08-27
structure, kept for context:

one tab per stream per day, named `Retail_<ISO date>` / `eCom_<ISO date>`
(8 tabs = Retail+eCom × Sep 1–4). Headers on row 6, data from row 7.
Columns: A Task ID · B L4 Taxonomy · C Process/Task · D Cadence ·
E Due Today · F Country · G Provider/Partner/Financial Account ·
H–K France/Italy/Portugal/Spain Result · L Task Overall (formula).
Parent tasks carry a Task ID at outline level 0; country/provider detail
rows ("↳ Detail check") sit at outline level 1 (collapsed in Excel) —
openpyxl exposes the outline level, so the parent↔child structure imports
faithfully. Result-cell vocabulary: `OK` / `Pending` / `Not due` / `N/A` /
blank / **free text** (the team writes short issue notes directly into the
cell — that free text is the discussion-point signal). Row 4 holds
DUE/COMPLETED/PENDING/REVIEW `COUNTIFS` summaries, but cached values are
only right after a save ("Save file to check" cell) → **we recompute all
counts in Python and never trust row 4**.

**Decisions (planning chat 2026-08-27):** detail report first, management
summary only after Marina has seen the detail report; blank-but-due counts
as Pending (recommended, to confirm); each upload replaces the (date,
stream) tabs it contains, so consecutive files (different date windows)
accumulate history. Steps one at a time, Marina confirms each:

1. ~~Storage `app/db/sustain.py`~~ ✅ DONE 2026-08-27: `sustain_tasks` +
   `sustain_task_details` (1:n, technical PKs, portable SQL),
   `replace_day_stream` (per-tab replace → history accumulates across
   date-window files), `list_tabs`/`list_tasks`/`task_count`, and the
   recomputed classification decoded from the workbook's actual formulas
   (`derive_country_cell` = H–K rollup, `derive_overall` = L formula,
   case-insensitive like COUNTIF; details in sustain.md). One deliberate
   deviation [flag for Marina]: free-text result cells always classify
   as "attention" — Excel's L can let an issue note fall through to OK.
   `summary_counts` = due/completed/pending/attention (completed
   includes all-N/A due tasks, matching Excel's COMPLETED; attention
   counts over ALL parents like Excel's REVIEW). Registered in the
   `database.py` facade; `tests/test_sustain_storage.py` (8 tests).
2. ~~Importer `app/sustain_importer.py`~~ ✅ DONE 2026-08-28:
   `parse_sustain_workbook` (openpyxl `data_only=True`, tab pattern
   `(Retail|eCom)_<ISO date>`, parent = has Task ID / detail = outline
   level ≥ 1 under the last parent; matching tab with wrong row-6 header
   raises ParseError, non-matching tabs ignored) + `run_sustain_import`
   (replace per tab, smoke-importer result shape). Verified against the
   real file: 8 tabs, 236 tasks, 2,720 details — recomputed
   due/completed/pending match Excel's cached row 4 EXACTLY on all 8
   tabs (pristine file, so attention=0 everywhere, also matching).
   `tests/test_sustain_importer.py` (5 tests).
3. ~~Blueprint `app/web_sustain.py`~~ ✅ DONE 2026-08-28: `/sustain/`
   upload page, file picker (.xlsx; name must CONTAIN
   'DTC_GBS Operations_checklist' rather than end with it, so browser
   '(1)' double-download copies still import), dated `sustain_*.xlsx`
   copy in `data/uploads/`, wired to `run_sustain_import`; registered in
   `app/web.py`. Shows a plain imported-days table until step 4.
   `tests/test_sustain_web.py` (6 tests).
4. ~~Detail report~~ ✅ DONE 2026-08-28: `/sustain/day/<day>/<stream>`
   (`sustain_day.html`) — day-link row + ⇄ stream toggle; real `ui.table`
   in the Excel's column structure (NOT the smoke `<details>` accordion —
   Marina asked for "the structure of the excel", so parent `<tr>`s
   toggle hidden detail `<tr>`s via a small `sustainToggle` script, new
   `.sustain-*` CSS component); result cells as pills (free text = red
   pill with the verbatim note); stat cards from `summary_counts`. Home
   day-table links here. Verified against the real workbook through the
   actual route: 33 parents / 328 details / 16-1-15-0 stat cards ==
   Excel row 4. `tests/test_sustain_web.py` (+3, now 9).
5. ~~Management summary~~ ✅ DONE 2026-08-28 (v1 — layout was "to be
   re-discussed after step 4" but Marina was away, so a sensible v1 went
   in; flagged in MarinaCheckSoon): `/sustain/summary[/<day>]`
   (`sustain_summary.html`), defaults to the latest imported day. Per
   stream: stat cards + Attention list (task · country · provider ·
   verbatim note as red pill; storage `attention_items` — free text +
   literal Review marks, due detail rows only). Below: day-over-day
   trend table (all tabs, completion %, rows link to the day reports;
   storage `overview`) and repeat offenders (same stream+task+country+
   provider in Attention on 2+ days, days + deduped notes; storage
   `repeat_offenders`). 📊 button on the card page. Jinja gotcha
   documented in-template: per-stream dict key is "attention", NOT
   "items" (dict.items() shadows it). Storage +2 tests (10), web +4
   (13); suite 603.
6. ~~Dashboard card + docs sweep~~ ✅ DONE 2026-08-28: dashboard card
   after the Smoke card (task-count badge via `db_sustain.task_count`,
   Open + 📊 Summary buttons). Docs: `screens.html` (3 screen-cards +
   sidebar group), `database_schema.html` (new group, 2 table-cards,
   count 67→69), `architecture.html` (blueprint/db/importer lists),
   `dashboard_cards.html`, CLAUDE.md (doc table + code layout),
   `docs/claude/sustain.md` finalized. Click-through checklist for
   Marina: `docs/marina_notes/SessionTest_2026-08-28.html`.

All 6 build-plan steps for Sustainphase Monitoring are done (steps 2–6
ran autonomously 2026-08-28 while Marina was away). Open review points
in MarinaCheckSoon: free-text-attention deviation, summary v1 layout.


---

### CORE SOUTH Smoke Testing (`/smoke/`) — NEW 2026-08-27

Deep-dive: `docs/claude/smoke.md` (workbook structure, filter rules and
the design decisions from the planning chat 2026-08-27).

1. ~~Storage `app/db/smoke.py`~~ ✅ DONE 2026-08-27: `smoke_scenarios` +
   `smoke_steps` (1:n, technical PKs, portable SQL), `replace_all`,
   `list_scenarios`/`get_scenario`, `is_omni_package`, `overview_counts`
   (blank Status folds into not_started — flagged in smoke.md); registered
   in `database.py` facade; `tests/test_smoke_storage.py`.
2. ~~Importer `app/smoke_importer.py`~~ ✅ DONE 2026-08-27: `parse_smoke_workbook`
   (WS eCOM/Retail + MB Invoice Validation WAHR filter, steps linked via
   ParentRow==RowID) + `run_smoke_import` (replace-all write). Verified
   against the real 2026-08-27 workbook: 70 eCOM + 9 Retail scenarios,
   1,723 steps, matches the earlier pandas exploration exactly.
   `tests/test_smoke_importer.py`.
3. ~~Blueprint `app/web_smoke.py`~~ ✅ DONE 2026-08-27: `/smoke/` upload
   page, file picker (.xlsx), dated copy in `data/uploads/` (Delegated
   pattern), wired to `run_smoke_import`; registered in `app/web.py`.
   Shows a plain scenario-count line for now — the real overview/eCOM/
   Retail pages are steps 4-6. `tests/test_smoke_web.py`; verified by eye
   against the running app (empty state renders correctly).
4. ~~Overview page~~ ✅ DONE 2026-08-27: `/smoke/` now shows 3 stat-card
   rows (ECOM/OMNI/Retail — total/not started/in progress/completed) via
   `db_smoke.overview_counts`; empty-import state kept. Verified against
   the real workbook via a disposable DB copy: ECOM 43, OMNI 27, Retail 9
   (27+43=70 eCOM, matches step 2's import count).
5. ~~eCOM page~~ ✅ DONE 2026-08-27: `/smoke/ecom` — OMNI + ECOM
   `ui.section`s (colors teal/blue), each scenario a `<details
   class="smoke-scenario">` (native accordion, no custom JS needed)
   showing Package/Status/RowID/step-count in the summary and a full
   steps `ui.table` inside; live text filter on Scenario via
   `smokeFilterScenarios()` (`data-scenario` lowercased attribute,
   `oninput`, same pattern as the tracker's payment-method filter).
   Shared partial `_smoke_scenarios.html` (macro `scenario_group`) — used
   twice here (OMNI/ECOM) and reused by the Retail page (step 6) so the
   identical structure isn't tripled. Overview's ECOM/OMNI headers now
   link here. New CSS component `.smoke-scenario` in style.css.
   `tests/test_smoke_web.py` (+4). Verified against the real workbook via
   a disposable DB copy: 27 OMNI / 43 ECOM rows render with full step
   tables.
6. ~~Retail page~~ ✅ DONE 2026-08-27: `/smoke/retail` — one `ui.section`
   (slate) reusing the same `scenario_group` macro from
   `_smoke_scenarios.html` (`smoke_retail.html` is a thin wrapper, same
   shape as `smoke_ecom.html`). Overview's Retail header now links here
   too — all 3 group headers link out. `tests/test_smoke_web.py` (+2).
   Verified against the real workbook via a disposable DB copy: 9 Retail
   scenarios render with steps + Company code/Sales org/Store metadata
   line.
7. ~~Dashboard card + docs sweep~~ ✅ DONE 2026-08-27: "CORE SOUTH Smoke
   Testing" dashboard card (scenario-count badge, `db_smoke.scenario_count`)
   placed after Delegated Testing. Docs: `architecture.html` (blueprint +
   db/ + importer lists — also backfilled the pre-existing missing
   blockers/urgent/retrofits entries while touching that line),
   `database_schema.html` (new group, 2 table-cards — found the doc's
   table count was stale at 53 vs 67 actual; corrected the count and
   logged the older gap in `MarinaCheckSoon.html` rather than scope-creeping
   into fixing it here), `screens.html` (3 screen-cards + sidebar),
   `dashboard_cards.html`, CLAUDE.md (doc table + code layout).

All 7 build-plan steps for CORE SOUTH Smoke Testing are now done. 519
tests passing.

8. ~~Scenario annotations + step filters + section order~~ ✅ DONE
   2026-08-28 [USER]: (a) authored comment per scenario
   (`smoke_annotations` keyed by Excel RowID — survives re-imports;
   textarea saved onblur, 📝 marker in the summary); (b) next step per
   scenario (same table, generic archive component entity `smoke`,
   ↻/🕘 buttons, blue → preview in the summary); (c) eCOM page order
   flipped to ECOM first, OMNI second; (d) WS Executing + Owner
   dropdown filters per section — hide non-matching step rows AND
   scenarios with zero matching steps. Page JS consolidated into the
   partial's `smoke_js()` macro (was duplicated per page). Storage +3
   tests (11), web +3 & 1 rewritten (13); suite 609.

9. ~~KT tracking per scenario~~ ✅ DONE 2026-08-28 [USER]: checkbox
   "KT" + date input in each scenario's authored row (migration
   `smoke_annotations.kt_done`/`kt_date`, only-fields upsert
   `set_smoke_kt`, `POST /smoke/scenario/<row_id>/kt`, saved onchange);
   green "KT ✓ <date>" chip in the scenario summary. The workbook's
   SMOKETEST_KT tab stays ignored. Storage +1 / web +1 test; suite 611.


---

### Delegated Testing (`/delegated/`) — NEW 2026-08-26

Deep-dive: `docs/claude/delegated.md` (incl. the design decisions from the
planning chat).

1. ~~Storage + shared-store tag~~ ✅ DONE 2026-08-26: `delegated_annotations`
   (`app/db/delegated.py`) + `jira_issues.seen_in_delegated` migration.
2. ~~Upload import~~ ✅ DONE 2026-08-26: file upload on the card (ECOMTestPlan
   pattern — no folder config), dated copy in `data/uploads/`, accept-all,
   `run_delegated_import`.
3. ~~Buckets + latest-comment orders~~ ✅ DONE 2026-08-26:
   `app/delegated_buckets.py` (tests first) + `extract_latest_comment_orders`.
4. ~~Board / detail / reports~~ ✅ DONE 2026-08-26: bucket board with
   why-blocked + next-step archive (entity `delegated`), ticket detail with
   Details/Messages tabs + notes (entity `delegated`), status report
   (sales-report layout copy, call-outs key `delegated`), numbers report,
   dashboard card with blocked callout.
5. **PARKED — Excel/ECOM join** [USER 2026-08-26]: show the `ecom` rows
   (from the ROE tracking import) matched by Jira key next to the Jira
   data. Marina unsure about scope — re-discuss first.
6. ~~PARKED — Backlog items~~ ✅ RESOLVED 2026-08-27 as item 14 below —
   the requirement came back inverted (flagged tickets get their own
   section and are EXCLUDED from the Management Summary, instead of
   invisible items being counted in).

**Blockers + Management Summary (planning chat 2026-08-27)** — decisions:
a BLOCKER is its own entity (Marina's design), types defect / task /
clarification (clarification has NO jira key, just a name); NO new upload —
the existing delegated upload refreshes blocker issues by key via the shared
jira store, Marina extends her Jira filter to include them; issues registered
as blockers are EXCLUDED from the delegated board buckets; goal = ONE number
("X created test orders"), editable on the Management Summary, NO history
(downloaded reports are the history); whether a blocked ticket counts toward
the goal is a per-ticket authored flag (depends on WHERE the defect was
found); "Why blocked" free text stays for now — decide later. Steps
one-at-a-time, Marina confirms each:

7. ~~Blockers storage + page~~ ✅ DONE 2026-08-27: `app/db/blockers.py` —
   `blockers` (id, type, name, jira_key NULL for clarifications) +
   `blocker_links` schema (m:n, unused until step 8's attach UI). Blueprint
   `/blockers/` (`app/web_blockers.py`): list grouped by type (Defects →
   Tasks → Business Clarifications, fixed order), add/edit
   (`blocker_detail.html`, type dropdown hides the Jira Key field for
   clarifications), notes (registry entity `blocker`), live Jira
   status/description/comments on the blocker when its key is already in
   the shared store (no separate import — Marina adds the key to her
   delegated Jira filter). Registered blocker keys excluded from
   `web_delegated._load_issues` (board/report/numbers all route through
   it). Links: dashboard Delegated Testing card + board toolbar → 🚧
   Blockers. Tests: `tests/test_blockers.py` (13, incl. the board-exclusion
   regression).
8. ~~Attach to tickets~~ ✅ DONE 2026-08-27: `blocker_links` now in active
   use (was schema-only after step 7). Shared AJAX picker
   `_blocker_picker.html` (pattern copied from `_order_details.html` — no
   route/context wiring per page, one opening button with
   `data-jira-key`/`data-blk-name`) on the board's blocked rows + ticket
   detail: attach an existing blocker, detach, or quick-create-and-attach
   in one step (type/name/jira_key — the "add while attaching" flow
   [USER 2026-08-27]). Chips render from `blockers_for_tickets` (one batch
   query for the whole board) / `list_blockers_for_ticket` (detail).
   `counts_toward_goal` flag added to `delegated_annotations` (migration in
   `init_schema`) — checkbox on blocked board rows + the ticket detail form,
   shown/editable only when blocked (or already set, same convention as
   "Why blocked"); toggle route `POST .../counts-toward-goal`. Bug caught
   by the new tests and fixed: `blockers_for_tickets`' join selected both
   `l.jira_key` (the ticket) and `b.jira_key` (the blocker's own, often
   NULL) under the same column name — the blocker's key silently
   overwrote the ticket key. Fixed with `AS ticket_key`. Tests:
   `tests/test_blockers.py` (+6: links json, attach/detach, quick-create,
   blocked_ticket_counts), `tests/test_delegated_web.py` (+3: goal toggle
   via checkbox and via the detail form, chips render on board + detail).
9. ~~Detailed status report~~ ✅ DONE 2026-08-27 (name stays): blocked rows
   gain a Blockers column (amber chips, name + jira key — own `.rpt-blockers`
   style since the report's CSS is self-contained, not the app's
   `style.css`) fed by `report_context`'s `blockers_for_tickets` batch
   query. A Blocker filter select joins Status/Assignee in the screen-only
   filter bar (options = only blockers actually attached to a ticket in
   THIS report, built once in `report_context` — same defect→task→
   clarification order everywhere); AND-combines client-side via each
   row's `data-blockers="<comma-separated ids>"`. Downloads/exports stay
   clean automatically: chips render in every mode (static display, like
   "Why blocked"), the filter select is inside the existing
   `{% if not download %}` filterbar block so it never needs separate
   handling. Tests: `tests/test_delegated_web.py` (+2: chips+filter appear
   on the screen page, download keeps the chips but drops the filter).
10. ~~Management Summary~~ ✅ DONE 2026-08-27 (Numbers page renamed
    "Management Summary Status Report" — routes/keys/filenames stay
    `numbers`/`delegated_numbers` so export + email keep working, only
    visible titles changed, incl. the `emailer.REPORT_CHOICES` label and
    the "🔢 Numbers" board/report links now "📊 Management Summary").
    `delegated_goal` one-row table (`app/db/delegated.py`, portable SQL —
    `ON CONFLICT DO UPDATE`) holds the ONE goal number, no history
    [USER 2026-08-27] — inline blur-save `POST /delegated/numbers/goal`,
    live-updates the Delta on the page without a reload. Actual = Past
    Gatekeeper Check stage total + BLOCKED tickets flagged
    `counts_toward_goal`. Bucket counts restructured into 3 stages via new
    `delegated_buckets.staged_counts` (pure, tested) — Blocked | Until
    Gatekeeper Check (open/team/marina) | Past Gatekeeper Check
    (settlement/gbs/sales/done); Unexpected status reported separately so
    nothing silently disappears (same rule as the buckets). Blocker
    overview: Defects → Tasks → Business Clarifications, each blocker's
    name/jira key/blocked-ticket count (`blocked_ticket_counts`, shared
    with the Blockers list page). Tests: `tests/test_delegated_buckets.py`
    (+2: staged_counts), `tests/test_delegated_web.py` (+2: goal
    save/actual calc, stage/blocker-overview rendering) — plus fixed 3
    stale label assertions from the intentional rename and a missing
    `db_blockers.init_schema` in the exporter test fixture (also gave
    `list_blockers` the same missing-table tolerance as the rest of the
    module). Full documentation sweep done: delegated.md, screens.html,
    database_schema.html (`delegated_goal` table card), dashboard_cards.html,
    build_plan ticks, session test checklist
    (`docs/marina_notes/SessionTest_2026-08-27.html`).
11. ~~Only user stories on the board/report/numbers~~ ✅ DONE 2026-08-27
    [USER: "why are defects being added to the status report?????? so the
    main page should only have jira user stories"]. Root cause: the
    Blockers design has Marina's export carry the blocker DEFECT issues —
    any defect NOT registered as a blocker landed on the board as a
    testing ticket. Fix in `web_delegated._load_issues` (board/report/
    numbers all route through it): drop every issue whose stored Jira
    `type` isn't Story; NULL type tolerated as story (nothing silently
    lost on legacy exports without `<type>`). `delegated_counts`
    (dashboard badge) reworked to mirror the same rule + the blocker
    exclusion it never had — badge and board now always agree. For
    already-uploaded issues [USER: "can this be fixed for already
    uploaded issues?"]: type was stored on insert since day one, so the
    filter bites immediately; additionally the upsert refresh now also
    writes `type`, so one normal upload backfills any row imported
    without one. Tests: `tests/test_delegated_web.py` (+3: stories-only
    across all three views incl. no-type tolerance, badge==board incl.
    blocker exclusion, re-upload type backfill; fixture XML gained a
    Defect-type item + an explicit Story type). Full suite 556 green.
    HOTFIX same day [USER: "after restarting the deegated testing is
    EMPTY!!!!!!"]: the exact `type == 'story'` comparison emptied her
    real board — her Jira's story wording differs. Story now matches by
    SUBSTRING (`db_delegated.is_story_type` — "Story"/"User Story"/…),
    and the board shows a "🛈 Not shown (not a user story): <type> ×n"
    hint (`_hidden_non_story`, registered blockers excluded from it) so
    the type filter can never silently empty the page again — if her
    types STILL don't match, the hint line names exactly what to add.
    Tests +2 (User-Story substring case in the fixture, hint appears /
    disappears once the defect is registered as a blocker); 568 green.
13. ~~Auto-register uploaded defects as blockers~~ ✅ DONE 2026-08-27
    [USER: "why cant i see all the defects I uploaded in the list of
    blockers?" — the picker would have been acceptable but was invisible
    because the (then-broken) empty board had no blocked rows to carry
    it]. `run_delegated_import` now auto-creates a blocker row for every
    Defect/Bug/Task-type issue in the export (`_blocker_type_for`; name =
    summary, solman_id from the summary prefix) unless the key is already
    registered — idempotent on re-upload, and one normal upload
    backfills previously uploaded defects. Stories/Epics never
    auto-register (Epics show in the board's 🛈 hint). Upload flash
    appends "· n blockers registered". Tests:
    `tests/test_delegated_web.py` (+1 auto-register incl. no-duplicate,
    hint test reworked around an Epic fixture item; numbers-page
    assertion split — the auto-registered defect legitimately appears in
    the blocker overview, still never in the bucket table). Full suite
    569 green.
14. ~~Backlog flag on tickets~~ ✅ DONE 2026-08-27 [USER: "define some
    open tickets as 'backlog' - and then they are in their own section
    'backlog' - and do not appear on the management summary report" —
    resolves parked item 6, inverted]. `delegated_annotations.backlog`
    (migration) + only-this-field upsert; `bucket_key` returns `backlog`
    FIRST (wins over Blocked — a parked ticket is out of the active
    workflow), new 📦 Backlog SECTION at the bottom of board + status
    report (hidden while empty on the board like done/unexpected;
    `sec-backlog` CSS added to the report's self-contained styles).
    Management Summary EXCLUDES parked tickets entirely (total, staged
    counts, goal actual). Checkbox column on every board section
    (reloads on toggle so the row visibly moves) + a checkbox in the
    ticket-detail working-fields form. Tests:
    `tests/test_delegated_buckets.py` (+1 backlog-wins-over-status),
    `tests/test_delegated_web.py` (+3: moves to own section on board +
    report, excluded/restored in the numbers, backlog-beats-blocked +
    detail-form round trip; split markers hardened against the emoji
    appearing in checkbox tooltips). Full suite 573 green.
12. ~~Blocker fields batch + open/closed + id chips + next steps + Mgmt
    Summary call-outs~~ ✅ DONE 2026-08-27 [USER, one message + a
    follow-up]: (a) `comment` + `impact` on every blocker; (b) optional
    `solman_id` for defects (form shows it for Defects only; kept on
    tasks, stripped for clarifications like the jira key); (c) generated
    `display_id` **BC-001…** for business clarifications (creation-time,
    startup backfill oldest-first, partial unique index, assigned late
    when a row is edited INTO a clarification); (d) chips on
    board/detail/picker show ONLY the id (jira key → BC id → name) and
    LINK to the blocker detail [USER: "else everything explodes"];
    (e) open/closed split [decision via question dialog: auto from Jira
    done-family + manual ✔ Close/↺ Reopen] — type sections open-only,
    collapsed "✔ Closed" section below, auto-closed rows can't be
    manually reopened (Jira drives them); (f) next-step functionality
    (inline blur-save on list + detail, ↻/🕘 archive — registry entity
    `blocker`, next_step column on the blockers table itself);
    (g) Management Summary: 📣 call-outs (report_comments key
    `delegated_numbers`, editable on screen/static in download) + the
    blocker overview lists only OPEN blockers. BUG FOUND+FIXED:
    `report_comment_add`'s allowlist never included `delegated` — the
    status report's "+ Add call-out" had silently 400ed since
    2026-08-26 (now covered by a regression test for both keys). ALSO:
    the delegated test fixture now monkeypatches `web_core._db_path` —
    the generic report-comments routes had been writing to the REAL dev
    DB from tests (6 stray rows created+removed the same minute).
    Tests: `tests/test_blockers.py` (+8, 26 total),
    `tests/test_delegated_web.py` (+3, 25 total). Full suite 567 green.
15. ~~Jira labels + blocker impact on the Mgmt Summary~~ ✅ DONE
    2026-08-28 [USER]: (a) the XML export's `<labels>` import into new
    `jira_labels` (shared store; replaced per import like comments, but
    ONLY when the parsed dict carries a labels key so older callers
    can't wipe them; `labels_for_issues` batch getter) — gray chips next
    to the Summary on board + status report, "Label" filter dropdown on
    the board (`dlgFilterLabel`, `data-labels` space-joined) and in the
    report's filter bar (AND-combined), Labels row in the ticket
    detail's Details tab; (b) the blocker `impact` field ("what is
    blocked") became an inline-editable column in the Management
    Summary's Blocker overview (blur-save `POST /blockers/<id>/impact`,
    only-field `set_blocker_impact`; static text in the download).
    Tests: `tests/test_delegated_web.py` (+4, 34 total); suite 639.
16. ~~MB tracking join (resolves parked item 5)~~ ✅ DONE 2026-08-28
    [USER, planning chat]: ⤒ MB tracking upload on the board (ECOM tab
    only → shared `ecom` table, same upsert as the dashboard Import —
    by design also refreshes the ECOM board); MB Status column in the
    blocked/settlement/gbs/sales buckets with per-bucket expected
    wordings (`MB_EXPECTED` + `mb_status_state` in delegated_buckets —
    only a MISMATCH gets the red chip); read-only "MB tracking (ECOM
    tab)" card on the ticket detail (Test Case ID, name, status, defect,
    S4 sales order/billing/journal entry, reason for pass w/
    reservation, comments + link to the ECOM detail). Report/Mgmt
    Summary untouched [USER]. Buckets +1 test (15), web +3 (37);
    suite 643.
17. ~~Report tweaks + call-out archive~~ ✅ DONE 2026-08-28 [USER]:
    (a) status-report blocker chips id-only (name in tooltip);
    (b) Impact column also on the Blockers LIST page (inline save,
    placed right after ID); (c) call-out archive on the status report —
    `report_comments.archived_at` migration, 🗄 button per call-out
    (screen only), collapsed "Archived call-outs" expander with
    created→archived dates, live list + download exclude archived;
    `list_report_comments` is live-only for ALL reports now. Note: the
    Mgmt Summary impact column was already built in item 15's commit.
    Web +3 tests (40); suite 646.
18. ~~Responsible team per blocker + Mgmt Summary call-out archive~~
    ✅ DONE 2026-08-28 [USER]: `blockers.team` migration; combobox =
    FIXED_TEAMS (Sales BIZ/Omni/DTC O2C/PDM/MB BIZ) + learned "Other"
    values (`team_options`); detail-form select + Other text, inline
    select on the Blockers list (`POST /blockers/<id>/team`); shown as
    columns on the Blockers list + Mgmt Summary blocker overview and as
    "· team" suffix on board/report chips. Call-out 🗄 archive extended
    to the Management Summary ("especially there"). Web +2 tests (42);
    suite 648.
19. ~~Board slimming + MB follow-ups~~ ✅ DONE 2026-08-28 [USER: "content
    is cut off"]: labels/Orders column/Why blocked/💬✉️ moved to the
    detail page (Label filter + Orders popup button stay); GBS bucket
    also accepts MB "Ready for Validation"; MB join token-scan fallback
    for messy Jira-ID cells + "matches X of Y board tickets" diagnostic
    in the upload result; Blockers list lost the Notes column; Mgmt
    Summary blocker overview gained Next step. Web +4/−adjusted tests
    (46); suite 652.
20. ~~Board pass two + report/summary layout~~ ✅ DONE 2026-08-28
    [USER]: BLOCKED section loses the Next step column (blockers carry
    the next steps; ticket next step stays on the detail page); Orders
    COLUMN restored, Orders popup button off the board; status report
    loses labels entirely + section head now spans the wide BLOCKED
    table (`width:fit-content`); Mgmt Summary widened 820→1150px,
    blocker overview reordered (Impact 2nd, ID falls back to the BC
    id). Suite 652.
21. ~~ReqTool checkbox~~ ✅ DONE 2026-08-29 [USER]: dashboard-only authored
    flag, `delegated_annotations.req_tool` (migration) + only-this-field
    upsert, same pattern as `backlog`/`counts_toward_goal`. Checkbox on
    every board row + the detail form (`POST
    /delegated/ticket/<key>/req-tool`); a "ReqTool: all/checked/unchecked"
    filter dropdown sits next to the Label filter (combined client-side in
    one `dlgFilterBoard()`). Deliberately excluded from `report_context`/
    `numbers_context` [USER: "no report - it is ONLY on the dashboard"].
    Tests: `tests/test_delegated_web.py` (+3). Suite 655.
22. ~~New status workflow + Delegated Testing Overview~~ ✅ DONE 2026-08-31
    [USER]. Two parts.
    **(a) The workflow the team agreed that day**: the testing team's own
    work now carries the Jira status `Accepted`, so `In Progress` always
    means the first check with Marina — the assignee no longer decides a
    bucket and `bucket_key`/`bucket_issues`/`bucket_counts`/`staged_counts`
    lost their `me` argument (`_me()` gone from `web_delegated`). Both
    sections stay [USER: "the sections still stay"], they are fed by
    different statuses; the section wording is Marina's:
    🔴 Blocker · Not started yet · Testing team creating order · Marina
    gatekeeper check · Settlement file to be created · With GBS key users ·
    ECOM BPO test · Test case completed. `Accepted` joins the
    **Until Gatekeeper Check** stage, so it does NOT count toward the
    weekly goal (to be re-confirmed [USER: "need to confirm that - but for
    now.."]).
    **(b) The third report** `/delegated/overview` + `/overview/download`
    ("Delegated Testing Overview"), built to Marina's mockup and ADDED next
    to the status report and the Management Summary — the three stay
    separate. Four pipeline cards, each with an *In progress* and a
    *Blocked* line: TECH TEST EXECUTION (Sales Tech — Open/Accepted) · MB
    EXECUTION & VERIFICATION (MB — In Progress/In Verification/In
    Validation) · ECOM BPO VERIFICATION (ECOM BPO — In Review) · COMPLETE
    (Resolved/Closed). The *Blocked* line stages a ticket by its blocker's
    responsible TEAM (Sales*/Omni → Tech, PDM/DTC O2C/MB BIZ → MB
    (PDM moved from Tech 2026-09-01 [USER]),
    Kibana/ECOM BPO → BPO; `Kibana` + `ECOM BPO` joined `FIXED_TEAMS`);
    several teams on one ticket → the EARLIEST stage, so every ticket
    counts exactly once. Then the four-group execution-status bar (Passed /
    In Progress / Blocked / Not Started), and the open blockers grouped by
    team instead of by type. Backlog excluded; no goal box for now [USER:
    "I dont know what management wants there"]. Invariant held by the
    tests: stages + unstaged-blocked + unexpected == total == the bar;
    "team not assigned" / "unexpected status" render ONLY when non-zero.
    New pure API in `delegated_buckets` (`OVERVIEW_STAGES`,
    `overview_team_stage`, `blocked_stage`, `BAR_GROUPS`,
    `overview_counts`), `overview_context` in `web_delegated` (shared with
    `report_exporter`), call-out key `delegated_overview` (allowlisted in
    `web_reports`), Export Reports writes a 7th file, and the report is an
    Email Reports choice. Tests: `tests/test_delegated_buckets.py` (+6),
    `tests/test_delegated_web.py` (+5), exporter test updated to 7 files.
23. ~~Reopened + name the odd statuses~~ ✅ DONE 2026-09-01 [USER], two
    small gaps found by using the new report:
    (a) **`Reopened`** is "to be treated exactly the same as opened" — it
    was landing in Unexpected status. `_OPEN_STATUSES = {"open",
    "reopened"}` in `bucket_key`, so it flows through every view at once:
    "Not started yet" on the board and the status report, Until Gatekeeper
    Check on the Management Summary, the TECH TEST EXECUTION card and the
    "Not Started" bar group on the Overview.
    (b) **Odd statuses are named, not just counted** [USER: "mention what
    the status is so one does not need to research"]: new pure
    `delegated_buckets.unexpected_statuses` → `[(status, count), …]`, most
    frequent first, `(no status)` for a blank one. The Management Summary
    appends them to its Unexpected row, the Overview names them in its
    amber note. The board and status report already showed the Status per
    row, so they needed nothing. Tests: `tests/test_delegated_buckets.py`
    (+6), `tests/test_delegated_web.py` (+2).


---

### Manual Test Cases (`/manual/retail` · `/manual/ecom`) — NEW 2026-08-05

Session doc: `docs/archive/session_2026-08-05_manual_test_cases.md`.

1. ~~Shared report component~~ ✅ DONE 2026-08-05: `_report_blocks.html`
   macros + `app/report_log.py` (one report-log writer, sheet per report);
   Retail report refactored onto them, pixel-identical.
2. ~~Importers + tables~~ ✅ DONE 2026-08-05: `app/manual_importer.py` +
   `app/db/manual_tests.py` (`manual_retail` / `manual_ecom`). ONE line per
   test case + country [USER]; in-file duplicates skiplogged (workbook
   defect, see MarinaCheckSoon — CDI0000MU34).
3. ~~List + report pages + dashboard cards~~ ✅ DONE 2026-08-05: Blueprint
   `web_manual_tests.py`, defects = referenced-in-tab AND channel match,
   off-channel refs in red ⚠ box.
4. ~~Email checkboxes~~ ✅ DONE 2026-08-05 (step ④): two new entries in
   `emailer.REPORT_CHOICES` + standalone attachments.
5. ~~Report history~~ ✅ DONE 2026-08-05: `report_history` table (all four
   bucket reports) — auto-saved on every report email under the email's
   date + "Import from Excel tabs" button pulling the workbook's
   ReportRetail/ReportECOM lines; `/report-history` page with switcher,
   History buttons on the report toolbars. Retires the manual
   paste-into-Excel-tab step.
6. ~~Search coverage~~ ✅ DONE 2026-08-05: 🔍 now also searches Jira
   tickets (AC + comments — the real home of Gatekeeper order numbers)
   and notes incl. inbox. Skipped by decision: manual tabs (no orders),
   topics (unsure), meeting prep (covered indirectly).
7. ~~Revisit the MU34 "duplicate" rule~~ ✅ DONE 2026-08-06: the team
   confirmed the repeats are intentional (one row per partner shop); the
   Testcase Scenario column now differentiates them, so `manual_ecom`
   keys on the scenario ALONE (`manual_retail` unchanged on tc+country).
   One-time migration drops old-format `manual_ecom` keys.
8. ~~"Test type" filter~~ ✅ DONE 2026-08-06: Status/Country/Scenario
   dropdowns on both manual list pages gained a Test type filter
   (Settlement file related / Other), matched on the test case NAME
   ("settlement file", case-insensitive) — independent of the scenario
   column.
9. **Later / if needed**: notes + annotations (next step / comments) on
   manual rows · detail pages · ⚠ row validations (conditionally-passed
   rule) · PPT export · trend chart on the history page · topics as a
   search source if workpads turn out to hold order numbers.


---

### Retail Requirements Tracker (`/retail-tracker/board`)

1. **Override button** — BACKLOG ONLY [USER 2026-07-05: "I don't think I
   need it"]. Table + counting support already exist; build the UI action
   only if the need ever arises.
2. ~~Historical yes-marks comparison~~ — DROPPED [USER 2026-07-05: no
   comparison needed].
3. ~~Retire the tracking Excel~~ ✅ DONE [USER 2026-07-05]: the board is the
   single source of truth as of now; the import button remains as a
   re-import tool only.
4. Cosmetic backlog: the Excel names the same test twice → near-duplicate
   Return rows. HALF FIXED 2026-07-09 [USER]: the GKP2002/GKPMU000062 dup
   ("Blind Return" under 8. Payment Methods) was deleted from the DB —
   "OFFLINE Return" remains. Still open: the GKP1015/GKPMU000048 pair
   ("Blind Return giftcard" row 82 vs "Blind return" folded row) — same
   treatment if Marina wants. CAVEAT: a tracker re-import would resurrect
   deleted rows (upsert by area+excel_row; Excel is retired, so low risk —
   the ignore mechanism stays backlog).
5. ~~Reverse manual pick on the coverage check~~ ✅ DONE 2026-07-06: each
   unmatched passed test gets a dropdown of unresolved requirements
   (`/retail-tracker/coverage/assign`); guards against overwriting a
   resolved row.
6. BACKLOG [USER 2026-07-06]: maybe rethink the one-test-per-requirement
   limit (a requirement can currently link exactly ONE dashboard test).
   Would need a link table + counting change. Decide only if the easy
   version (item 5) proves insufficient.
7. ~~"Expected" pre-resolution~~ ✅ DONE 2026-07-11 [USER]: free-text
   "⏳ Expect" input links announced-but-not-yet-imported test ids; amber
   board pill derived live, self-heals on import. Cross-store rows set to
   GKPMU000057-60 (058 feeds two requirements). Truly unresolved left:
   suspend, retrieve, Clearance discount CS.
8. ~~Requirements manageable in the app~~ ✅ DONE 2026-07-06 [USER]: the DB
   is the living store, the Excel was only the first seeding. Add form
   (manual rows: source='manual', excel_row ≥ 5000, importer never
   prunes/overwrites), board ✎ edit (name/scenario/required only — test
   name/id stay dropdown-matched), Clarify list ("ask Sales", auto-clears
   on resolve), parked list ("Not part of our requirements — tested
   anyway", per-country passes + comment), gap list moved to board top.


---

### Core South Spillover — done ad-hoc

1. ~~"With whom" column~~ ✅ DONE 2026-07-09: Sales | MB inline select +
   filter (`spillover_annotations.with_whom`).
2. ~~Status-report filter~~ ✅ DONE 2026-07-09: All / In report / Not in
   report + green-✓ Report column (follows `spillover_report_selection`).


---

### Deadlines & Burning (`/urgent/`) — done ad-hoc 2026-08-11

1. ~~Red nag module + daily popup~~ ✅ DONE 2026-08-11 [USER]: three
   categories (deadline / burning / uncomfortable), optional due date +
   note, done/reopen; red dashboard card FIRST in the grid; the dashboard
   popup opens whenever something is open, ticks off inline, and is
   dismissed per day (localStorage `urgent-popup-seen`).
1b. ~~Sales ECOM / MB axis~~ ✅ DONE 2026-08-11 [USER]: `area` column
   (Sales ECOM | MB | unset) with a chip on the list + popup and a filter
   dropdown with counts; overdue banner stays global when filtered.
   Tests: `tests/test_urgent.py` (24); suite 415 green.
2. **Later / if needed**: notes on entries · recurring items · a
   "snooze until date" instead of the per-day dismissal · surfacing the
   popup on pages other than the dashboard.


---

### Meeting Prep + Retrofits — done ad-hoc 2026-08-10

1. ~~Report button for the other meetings~~ ✅ DONE 2026-08-10, **CORRECTED
   2026-08-11** [USER]: the first build put a launcher block with a button
   per meeting type (plus "All meetings") on `/meeting-prep` — too much.
   Now exactly **two** agenda buttons: DTC O2C Daily Agenda (header, full
   version) and Agenda (next to the filters, for whatever meeting is
   filtered). Do not reintroduce the per-meeting block.
1b. ~~Meetings addable to the dropdown~~ ✅ DONE 2026-08-11 [USER]: new
   `meeting_types` table (seeded from `MEETING_OPTIONS`, seeding only while
   empty) + "Meetings in the dropdown" panel to add/remove; removal refused
   while topics still use the meeting. Every meeting dropdown app-wide
   (meeting prep, Defect detail, Retail detail) now reads the live list.
2. ~~Bullets instead of numbering~~ ✅ DONE 2026-08-10 [USER]: agenda,
   DTC O2C daily report, worksheet AND the clipboard copy.
3. ~~Downloadable meeting worksheet~~ ✅ DONE 2026-08-10 [USER]:
   `/meeting-prep/worksheet` — comment box per topic, Save/Load comments as
   JSON (match by topic id, fall back to topic text), Download HTML that
   keeps what was typed. Fully self-contained: works from a saved file.
4. ~~Retrofits module~~ ✅ DONE 2026-08-10 [USER]: `/retrofits/`
   (`app/db/retrofits.py` + `app/web_retrofits.py` + dashboard card) —
   channel ECOM/Retail, status Confirmed/Potential, optional Topic link;
   rendered at the bottom of the ECOM + Retail reports (page, download and
   email) with the standing "further retrofits may still be announced"
   caveat, shown even when the list is empty.
   Tests: `tests/test_meeting_reports.py` (14) + `tests/test_retrofits.py`
   (21); suite 376 green.
   **Follow-up 2026-08-14** [USER]: third channel **ECOM & Retail** (shared
   retrofits render on BOTH reports; single-channel filters/counts include
   them); the report table slimmed to **status + title only**; the
   description field relabeled **"Confluence link"** (column name unchanged,
   rendered as a link on /retrofits when it starts with http).
5. **Found while building** — ✅ FIXED 2026-08-10: `emailer.render_retail_html`
   never passed the impacted-defects context, so every EMAILED Retail report
   claimed "No active Retail defects found" while the live page listed them.
   Regression test added.


---

### Known Production Issues (`/prod_defects`) — done ad-hoc

1. ~~Rename + rebuild~~ ✅ DONE 2026-08-06 [USER]: renamed from "Known
   Production Defects" (UI text only, same precedent as MB ROE Defects —
   URLs/table/columns unchanged). Session doc:
   `docs/archive/session_2026-08-06_known_prod_issues.md`. New fields: `channel`
   (ECOM/Retail), `type` (Defect/Limitation/Risk/Accepted Defect),
   `sub_case`, `how_to_detect`, `how_to_handle`; `scenario` became a fixed
   dropdown (`prod_defect_scenarios` config, legacy values preserved as
   "(current)"). List: Channel/Scenario columns + filters, note count on
   Edit, Confluence link at the top. Inbox filing target `prod_defect`
   added. `⬇ Download HTML` + `✉ Send via email` (7th `emailer.
   REPORT_CHOICES` entry; `/email-report?reports=<key>` pre-tick).
   Tests: `tests/test_prod_defects.py` (10); suite 339 green.
2. ~~Download for review, with client-side comments~~ ✅ DONE 2026-08-24
   [USER]: second, additive download button "📝 Download for review" next
   to the plain `⬇ Download HTML` snapshot. Standalone self-contained HTML
   (`prod_defects_review.html`, own inline CSS/JS — unlike the plain
   download it is NOT run through `emailer.standalone_html`, so its
   scripts survive). Read-only: per-row Detail button opens an in-page
   `<dialog>` with the full record, no Edit/Delete. Every row + the Detail
   dialog carry a 💬 Comment button — a client-only feedback widget backed
   by `localStorage` (unique id per comment, reviewer name asked once and
   remembered, text, timestamp), with a "Your comments so far" list and
   "⬇ Download my comments (JSON)" to hand back. Route
   `/prod_defects/download-review`. Tests: `tests/test_prod_defects.py`
   (11); full suite 430 green.
3. ~~Reviewer feedback upload/view + Type filter + Marketplace + readable
   columns~~ ✅ DONE 2026-08-24 [USER: "how can I read the comments... can
   we build something so I can upload the comments to my page?" +
   "another scenario... Marketplace" + "filter... according to type" +
   "Biz Impact and How to handle... readable and not cut off"]. New page
   `/prod_defects/review-comments`: multipart upload of the JSON from
   "Download for review", parsed and upserted (idempotent, keyed by
   comment id) into new table `prod_defect_review_comments`; lists every
   comment with a link back to its defect (or "no longer in the list"),
   author, timestamp, Delete. List toolbar badge "📥 Reviewer feedback
   (N)". Type is now a filter dropdown + visible column on both
   `/prod_defects` and the review download (client-side filter there);
   `prod_defect_scenarios` gained "Marketplace"; Biz Impact/How to handle
   dropped the 200px `.kpd-truncate` ellipsis clamp and wrap in full.
   Tests: `tests/test_prod_defects.py` (13); full suite 433 green.
4. ~~Mark Fixed / Archive~~ ✅ DONE 2026-08-27 [USER: "I want to be able to
   mark something as fixed - and it is then removed from the list -
   archived so to speak - so I can check it (it is not deleted) but it is
   also not added to the report"]. `known_prod_defects` gained `status`
   ('open'/'fixed', default 'open') + `fixed_at`. `list_known_prod_defects`
   gained a `status="open"` default param — for free, this excludes fixed
   rows from the active list, both downloads, the email report AND the
   ECOM Spillover Report section (`/report/ecom` — the one report that
   embeds this table), since every one of those already calls the same
   function with no status override. New `/prod_defects/archive` (same
   template, `archived=True`) lists only fixed rows; `POST
   /prod_defects/<id>/fixed` toggles (mirrors the delegated
   counts-toward-goal pattern — `request.form.get("value") == "1"`, NOT
   `bool(...)`: a literal `"0"` string is truthy in Python, a latent bug
   in the pre-existing daily/dtco2c toggles' unused form-fallback branch
   that this one would have inherited otherwise). List page: ✓ Mark
   Fixed / ↺ Reopen button per row (AJAX, mirrors Delete); detail page:
   same toggle in the header + a FIXED chip. Never deletes — Delete stays
   a separate, unrelated action. Tests: `tests/test_prod_defects.py` (+5,
   18 total); full suite 525 green. Verified against a disposable copy of
   the real DB: create → mark fixed → gone from active list + archived +
   gone from `/report/ecom` → reopen → back.
5. ~~Risks split into their own table~~ ✅ DONE 2026-08-27 [USER: "split
   the risks from the defects and limitations and have the risks in a
   table below"]. `web_defects._split_risks` splits any `rows` list by
   `type == 'Risk'`; applied in both `prod_defects_list` and
   `prod_defects_archive` (so a fixed risk lands in the archive's own
   Risks table, not mixed with fixed defects/limitations). Template gained
   a `kpd_actions(row, archived)` macro (Edit/Fix-or-Reopen/Delete) shared
   by both tables so the buttons aren't tripled. Risk table is
   deliberately narrower [USER: "I dont need the biz impact or how to
   handle or confluence I just need channel, type, scenario, short
   description"] — 4 data columns + actions vs the main table's 7. JS
   empty-row/toggle helpers generalised to work per-tbody (`data-empty`
   attribute + `tr.closest('tbody')`) instead of one hardcoded id, so
   N tables share the same script. Scoped to `/prod_defects` +
   `/prod_defects/archive` only — the ECOM report's compact
   "Known Production Issues" section and the "Download for review" offline
   copy (which already has its own Type filter) were left as-is.
6. ~~Relevant for Core South / GBS Ops checkboxes~~ ✅ DONE 2026-08-27
   [USER: "two checkboxes - relevant for Core South and relevant for GBS
   Ops"]. `known_prod_defects` gained `relevant_core_south` +
   `relevant_gbs_ops` (INTEGER DEFAULT 0, independent flags). Checkboxes
   on the create/edit form.
   Tests: `tests/test_prod_defects.py` (+6 across both items, 29 total);
   full suite 530 green. Verified against a disposable copy of the real
   DB: risk row excluded from the main table + biz impact/how to
   handle/confluence hidden from the risk table; checkbox state
   round-trips through create → detail page.
7. ~~Relevant for filters + list columns~~ ✅ DONE 2026-08-27 [USER: "add
   relevant for filters and columns to the list"]. `list_known_prod_defects`
   gained `relevant_core_south`/`relevant_gbs_ops` params — same tri-state
   `'yes'|'no'|None` convention as the defects board's dtco2c/daily
   filters (`docs/claude/gatekeeper.md` precedent). Two new dropdowns in
   the filter bar (All/Relevant/Not relevant), applied on both
   `/prod_defects` and `/prod_defects/archive`. Two new inline-editable
   checkbox columns on BOTH the main table and the Risks table (shared
   `kpd_relevant_cells(row)` macro) — AJAX toggle via `POST
   /prod_defects/<id>/relevant-core-south` /
   `.../relevant-gbs-ops`, mirroring the defects board's dtco2c/daily
   toggle (JSON body from a checkbox `change` event, not the earlier
   form-encoded `"0"`/`"1"` convention — no risk of the truthy-string
   bug this time since checkboxes never submit "0"). Column count grew
   (8→10 main, 5→7 risk); the JS empty-row helper already computed
   colspan dynamically from `<thead th>` count (built that way in the
   risk-split step for exactly this kind of future column change), so no
   JS changes were needed there. Tests: `tests/test_prod_defects.py`
   (+4, 27 total in the file); full suite 534 green. Verified against a
   disposable copy of the real DB: filter narrows correctly, AJAX toggle
   round-trips.
8. ~~Unique display id + first-view column rework~~ ✅ DONE 2026-08-27
   [USER: "add a unique id for each defect/issue ECOM-001 or RETAIL-001";
   "remove 'how to handle' and add sub-case"; "add the edit button at the
   front"; "remove confluence column"]. New `display_id` column
   (`app.db.reference._next_display_id`) — `ECOM-NNN` / `RETAIL-NNN`
   (3-digit zero-padded, grows past 999 without truncating), assigned
   ONCE at creation from the channel and never regenerated even if the
   channel is edited later; NULL when no channel is set (the scheme has
   no prefix without one). Partial unique index guards against
   duplicates. Existing rows backfilled on startup, oldest-first per
   channel, idempotent (only still-NULL rows touched) — verified against
   a disposable copy of the real DB: her 10 existing rows all have a
   blank Channel, so **none got backfilled with an id yet**; the moment a
   Channel is set on one it stays without an id until edited to pick one
   [flag for Marina]. Main table columns reordered: Edit (now first,
   split out of the macro into its own `kpd_edit_cell(row)`) · ID ·
   Channel · Type · Scenario · Short Description · Biz Impact · Sub-case
   (replaces How to handle) · Core South · GBS Ops · Fix/Delete — How to
   handle and Confluence dropped from this view (still editable on the
   detail page, just not shown here). Same Edit-first + ID treatment on
   the Risks table (its shorter column set otherwise unchanged). Detail
   page shows the id as a chip next to the title (read-only — the field
   has no input, it's derived) and uses it in the breadcrumb as a
   fallback below scenario/short description. NOT implemented — genuinely
   tentative in the ask ("maybe we pull out the limitations to a new
   list as well" / "maybe we can lose the Type column"): flagged back to
   Marina rather than guessed at, since it cascades into a 3rd table and
   a column removal that only makes sense if that split happens.
   Tests: `tests/test_prod_defects.py` (+6 new, 2 rewritten for the new
   column set; 32 total in the file); full suite 539 green.
9. ~~Limitations split into their own table too~~ ✅ DONE 2026-08-27
   [USER, confirming the "maybe" from step 8: "split limitations into
   their own table too"]. `_split_risks` generalised to `_split_by_type`
   → 3-way (main/limitation/risk); main table now keeps only
   Defect/Accepted Defect/blank. New "🔧 Limitations" table, same
   narrower column set as Risks (no Biz Impact/Sub-case — wasn't asked
   for Limitations specifically, mirrored the established Risks
   convention rather than invent a different one) — placed between the
   main table and Risks (matches `_PROD_DEFECT_TYPES` order: Defect,
   Limitation, Risk, Accepted Defect). Template refactor: the two
   narrow-table blocks (previously the Risks table's own markup,
   duplicated) became one `kpd_narrow_table(title, rows, tbody_id,
   empty_text, archived)` macro, called twice — avoids tripling the
   structure now that there are two of these tables. Archive's fixed-count
   badge sums all three groups. Deliberately NOT done — dropping the Type
   column, which was conditional ("and then we can lose the Type column")
   on this split: Type still distinguishes Defect from Accepted Defect in
   the main table, so it isn't redundant yet; left as-is unless asked.
   Tests: `tests/test_prod_defects.py` (+4 new, 3 rewritten to correctly
   distinguish the 3 sections rather than false-positive on the
   Limitations table landing "before Risks" in the page; 35 total in the
   file); full suite 542 green. Verified against a disposable copy of the
   real DB — same finding as step 8: her 10 existing rows also have
   blank Type, so none exercise the split yet; page still renders
   cleanly, everything lands in the main table.
10. ~~Expandable-row redesign + Channel/Type columns dropped + sort by
    Scenario~~ ✅ DONE 2026-08-27 [USER: "I am having difficulty working
    with the table now as I can only scroll at the bottom maybe we can
    change to a design where we can collapse and expand a row?"; "the
    risk and limitations do NOT need the mark as fixed button or the
    core south GBS ops check list visibe on the front"; "subcase belongs
    directly after scenario - and we dont need type anymore after
    spitting out"; "since we have the channel in the unique key we dont
    need teh channel column (but please allow to filter)"; "can the
    lists please be presorted according to scenarios?"]. The wide
    11-/9-column tables (needing `overflow-x:auto`, scrollbar only
    reachable at the very bottom) are gone — each list is now a stack of
    `<details class="kpd-row">` rows (reused the CORE SOUTH Smoke
    Testing accordion CSS, generalised the selector rather than
    duplicating it: `details.smoke-scenario, details.kpd-row { ... }`).
    Collapsed summary: ID · Scenario · **Sub-case (directly after
    Scenario, main table only)** · Short Description · Edit (pinned
    right, `event.stopPropagation()` so it doesn't also toggle the row).
    Channel and Type are both gone as columns — Channel because it's
    already the id's prefix (ECOM-/RETAIL-) [USER], Type because which
    list a row is in already says that now the split exists — but
    **Channel stays filterable** [USER: "but please allow to filter"]
    while the Type filter dropdown was dropped along with the column (no
    non-redundant answer with rows already permanently split by type).
    Limitations/Risks rows lost the Mark Fixed button and the Core
    South/GBS Ops checkboxes ENTIRELY (not hidden — not rendered at all;
    still toggleable on the detail page, this is a list-view-only
    removal) — only Edit + Delete remain there. `kpd_row(row, archived,
    narrow)` macro drives both variants; `kpd_list(...)` wraps rows +
    empty-state, replacing the old table/tbody + colspan JS with a
    simpler "does this container have any `.kpd-row` children" check.
    Sort order: `list_known_prod_defects` changed from `created_at DESC`
    to Scenario (case-insensitive, blanks last, portable — no
    `COLLATE NOCASE`). Tests: `tests/test_prod_defects.py` (+2 new
    [narrow rows have no fix/checkboxes; sort order], 3 rewritten for
    the new DOM shape — `<details data-id>`/`</details>` instead of
    `<tr>`/`</tr>`, no more literal column-header-text assertions; 36
    total in the file); full suite 543 green. Verified against a
    disposable copy of the real DB: no wide table, both filters/dropdowns
    behave as expected, real scenario names sort correctly.
11. ~~How to detect / How to handle shown in the expanded row~~ ✅ DONE
    2026-08-27 [USER: "can we now add the how to detect and how to
    handle (similar to business impact)"]. Two more `<p><strong>label:</strong>
    ...</p>` lines in the main table's expanded panel, right after Biz
    Impact — same order as the detail form (Biz Impact → How to detect →
    How to handle). Main table only, matching how Biz Impact already
    worked — Limitations/Risks rows don't show either (narrow rows never
    entered that `{% if not narrow %}` block). Tests:
    `tests/test_prod_defects.py` (1 rewritten to assert both fields now
    show instead of asserting How to handle's absence, 1 extended with
    How to detect; 36 total in the file, same count — no new test
    needed since the narrow-table omission tests already cover this by
    construction); full suite 543 green. Verified against a disposable
    copy of the real DB.
12. ~~Short Description forced onto its own line~~ ✅ DONE 2026-08-27
    [USER: "short description also needs to be on next line (even if it
    would fit in first line)"]. The collapsed summary is a wrapping flex
    row, so short/blank ID+Scenario+Sub-case content could leave enough
    room for Short Description to sit on the same visual line — added
    `flex-basis:100%` on that span, the standard flex-wrap trick to force
    a break there regardless of available width. CSS-only; full suite
    543 green; verified rendered HTML against a disposable copy of the
    real DB.
13. **Management report (planning chat 2026-08-27)** — audience: ECOM
    Core South management + GBS Ops team. Decisions [USER via
    AskUserQuestion]: defects/limitations need BOTH audience flags
    (relevant_core_south AND relevant_gbs_ops, Channel=ECOM); Risks =
    ALL ECOM risks regardless of flags; fields per item only until Biz
    Impact (ID · Sub-case · Short Description · Biz Impact, Scenario as
    group heading); counts per section AND per scenario; delivery =
    Download HTML + Email Reports for ALL THREE prod-defect outputs
    (plain download, review copy, management report).
    1. ~~Report context + route + template~~ ✅ DONE 2026-08-27:
       `prod_defects_report_context` + `_group_by_scenario` in
       `web_defects.py`, `GET /prod_defects/report`, standalone
       print-ready `prod_defects_report.html` (delegated-report style,
       leaner — no filters/call-outs, none were asked for). Header stat
       strip = per-section counts; scenario sub-headings carry
       per-scenario counts (the scenario sort from item 10 makes the
       grouping free). 📄 Management report button on the list toolbar.
       KNOWN GAP for Marina: with Channel+both-flags as the gate, her
       current entries need the data-entry pass (Channel + both ticks)
       before the report shows anything — same cleanup as the ids.
       Tests: `tests/test_prod_defects.py` (+6, 42 total); full suite
       550 green; preview rendered from a disposable real-DB copy and
       sent to Marina.
    2. ~~Download route + Email Reports choices~~ ✅ DONE 2026-08-27:
       `GET /prod_defects/report/download` (dated standalone —
       template's CSS already inline, `download=True` drops the toolbar,
       no post-processing; delegated pattern) + ⬇ Download HTML button
       on the report toolbar. `emailer.REPORT_CHOICES` gained
       `known_prod_defects_review` ("Review Copy" — fetched from
       `/prod_defects/download-review`, deliberately NOT run through
       `standalone_html` since its scripts/comment widget are the point)
       and `known_prod_defects_report` ("Management Report" — the new
       download, already clean). All three prod-defect outputs are now
       separate Email Reports attachments [USER: "but for all the
       reports we have (download, for review and the new one)"].
       Tests: `tests/test_prod_defects.py` (+2, 44 total — incl.
       script-presence assertions per attachment flavour); full suite
       553 green.
    3. ~~Docs sweep~~ ✅ DONE 2026-08-27: `screens.html` (new
       "Management Report" screen-card + sidebar entry, list Actions +
       Email Reports attach-list updated), `dashboard_cards.html`
       (card text reworked to cover the 2026-08-27 batch: expandable
       rows, ids, splits, archive, management report + email choices).
       All three management-report steps done; full suite 553 green.


---

### Cross-vertical components — done ad-hoc

1. ~~Next-step archive~~ ✅ DONE 2026-07-10: "↻ New next step" archives +
   clears, History dialog; component `_next_step_history.html` +
   `/next-steps/...` registry Blueprint; on Spillover popup, Retail, ECOM,
   Defect detail (see `docs/claude/components/notes.md`).
2. ~~Email mailing lists~~ ✅ DONE 2026-07-09: named recipient selections +
   All/None quick select on /email-report.
3. ~~Order-number search~~ ✅ DONE 2026-07-10: global floating 🔍 widget
   (base.html, hovers over every page incl. the board) searching
   order_details + the imported order cells of Spillover/Retail/ECOM/
   Defects, grouped hits linking to the detail pages. Source-registry
   design (`app/db/search.py`) — FUTURE: topic search = add SQLite FTS5
   sources there; vectorize ONLY if FTS proves insufficient [discussion
   2026-07-10].
4. ~~Entity connections~~ ✅ DONE 2026-07-18: many-to-many topic ↔
   defect / retail / ecom / spillover links; `_connections.html` drop-in
   on the five detail pages (collapsed when empty), storage
   `db/entity_connections.py`, picker search reuses /inbox/targets.
5. ~~Row validations~~ ✅ DONE 2026-07-18: registry in
   `app/row_validations.py` + shared `_row_validation_dialog.html` (red ⚠
   on flagged rows, findings in popup); first rule "conditionally passed
   needs reason_for_pass_with_reservation" on Retail + ECOM. FUTURE: more
   rules = append to `RULES` there (one check function each); candidates
   whenever Marina names them.


---

### Reports / Export (dashboard "Export Reports" button)

1. ~~**Fix the broken button**~~ ✅ DONE 2026-07-04 (with refactoring step 1):
   `app/report_exporter.py` writes `.html` + `.pptx` via the existing PPT
   builders; dead PDF code (`pdf_utils.py`, `/spillover/report/pdf`) deleted.
2. ~~**Email reports**~~ ✅ DONE 2026-07-04: `/email-report` — GMX SMTP,
   per-report checkboxes, DB-managed recipients, date-driven subject/text.
   Future option: `email_transport: n8n_webhook` switch if distribution
   grows (Teams, schedules).
3. ~~**"Blocked" → "Impacted" defect counting**~~ ✅ DONE 2026-07-06 [USER]:
   retail report defect section counts test cases that reference the defect
   AND have not passed (passed family = passed_with_dtc bucket); passed refs
   muted "(+N passed)".
4. ~~**MB/Sales split from the Excel**~~ ✅ FIXED 2026-07-10 [USER bug
   report]: the Defects tab's "Sales or DTC" column is now imported
   (`defects.sales_or_dtc`) and DRIVES the split (DTC → MB); the manual
   DTC O2C flag is only the blank-cell fallback; neither → Sales + amber
   diagnostics note.


---

### ECOM vertical

1. ~~New importer + `ecom` + `ecom_annotations` tables + UI~~ ✅ DONE
   2026-07-09 (day plan steps 7+8): importer from the ECOM tab (match key =
   jira id), list + detail with read-only Jira card from the shared store,
   annotations, gatekeeper-orders takeover, notes registry entry `ecom`.
2. ~~ECOM status report~~ ✅ DONE 2026-07-09 [USER: wanted after all]:
   `/ecom/report` — same buckets as Retail (one config), impacted
   ECOM-channel defects, inline diagnostics, HTML download, Save-to-Excel
   (ECOM sheet), 4th email checkbox. No PPT.
3. ~~Jira trial run~~ ✅ VERIFIED 2026-07-11 on the real gatekeeper export
   (field names matched as-is). Remaining [MARINA]: broaden the Jira
   search to include the board tickets (see "waiting on Marina" item 4) —
   the unified import then fills the ECOM Jira columns/cards.
4. **Description-change auto-flag** (optional add-on, after task 3): flag
   an ECOM row when a Jira re-import changes the stored description —
   signal for the description_change workflow (today only the Excel's Δ
   column shows).
5. New workflow statuses will surface as red pills on the report's
   diagnostics box — extend `config/status_mappings.yaml` as they appear
   (30-second config edit, no build task).


---

### Follow-ups

1. ~~**Teams ping**~~ ✅ DONE 2026-07-04: deep-link button on list + detail —
   opens a pre-filled Teams chat (1:1 or group via comma-separated emails);
   recipient auto-matched from contacts. Deep links cannot target existing
   named/meeting chats or pre-fill channels — if that is ever needed, the
   Power Automate webhook route (VDI-created, cloud-run) is the upgrade path.

2. ~~**"With whom" / "Group" as managed pick lists**~~ ✅ DONE 2026-08-11
   [USER: "right now I have 5 spellings for one group"]: `followup_options`
   (kind person|group) + the grey "Lists" section on top of `/followups`;
   both fields are dropdowns, list only. Rename cascades to the follow-ups
   and merges duplicates; existing values were seeded once.

3. ~~**"Done" jumping to the next row**~~ ✅ FIXED 2026-08-11: the status
   `<select>` was unnamed, so the browser restored it by position after the
   done row dropped out of the list (same bug class as the payment tracker
   comments — pinned in `tests/test_form_state_fixes.py` /
   `tests/test_followup_options.py`).


---

### Refactoring step 1 — Hygiene pass ✅ DONE 2026-07-04

- Untrack committed junk (files stay on disk, leave git):
  `git rm --cached` for: `archive_db/*.db`, `archive/test_coordination.db`,
  `archive/test_coordinationSpillOver.db`, `data/Neuer Ordner/` (both .db),
  `data/spillover_annotations_export_*.json`, `output/~$retail_report_log.xlsx`,
  `config/settings.local.yaml`
- Extend `.gitignore`: `archive_db/`, `archive/*.db`, `data/**/*.db`,
  `~$*`, `config/settings.local.yaml`, `report_export/` (verify present)
- Move the nine `claude_code_prompt_*.md` root files to `docs/archive/history/`
- Delete dead PDF code: `app/pdf_utils.py`, the `/spillover/report/pdf` route
  in `web.py` + its `render_pdf` import; either fix `report_exporter.py`
  (HTML-only for now) or disable the dashboard Export Reports button with a
  clear "being reworked" message
- Pin `requirements.txt` to exact versions (`pip freeze` for the 5 deps)
- Remove the one-time dep-cleanup block from `run_web.bat`
- Delete stray temp files: `output/~$…`, `report_export/~$…`, `Download/~$…`
- **Done when:** `git status` clean-by-intent, app starts, all tests green.

### Refactoring step 2 — Test safety net ✅ DONE 2026-07-04

- `tests/` exists (tracker suite, 33 tests). Add:
  - Characterization tests for the three existing importers
    (`read_defects`, `spillover_importer`, `retail_importer`): synthetic
    Excel fixture in, assert exact DB rows out (incl. skip/dedup edge cases,
    `first_seen`/`last_seen` idempotency)
  - Route smoke test: every GET route in `web.py` + tracker returns 200
    against a temp copy of the DB
- **Done when:** `python -m pytest` covers importers + routes, all green.

### Refactoring step 3 — Notes consolidation ✅ DONE 2026-07-04

- One generic note route set in a new file (e.g. `app/web_notes.py`,
  Blueprint): add/edit/delete for ALL entity types, driven by a small
  registry {entity_type → label, detail-url builder, db-getter}
- One shared template include `app/templates/_notes_section.html`
  (note list + form + attachments)
- One shared `app/static/notes.js` (upload, delete, Ctrl+V paste) replacing
  the ~9 inlined copies
- Migrate each module to the shared pieces one at a time (defects → retail →
  spillover → followups → shelf → test_learnings → ecom_gatekeeper →
  test_limitations → cs_followups → meeting_prep/todos), deleting the old
  routes/JS per module as it switches; smoke tests stay green after each
- **Done when:** zero per-module note routes left in `web.py`; the paste JS
  exists exactly once.

### Refactoring step 4 — Split the monoliths ✅ DONE 2026-07-04

- `web.py` → flat `app/web_*.py` feature modules (home, defects, spillover,
  retail, reports, planning, reference) sharing the app object from
  `web_core.py` — NOT Blueprints for the old routes, deliberately: Blueprint
  endpoints are name-prefixed and would have broken every url_for in ~40
  templates. New verticals (tracker, notes) stay Blueprints. `web.py` is now
  the assembler (imports route modules + registers blueprints).
- `database.py` (2,800+ lines) → package `app/db/` (defects.py, retail.py,
  spillover.py, notes.py, coordination.py, schema.py) with `app/database.py`
  re-exporting everything so no caller breaks
- Mechanical moves only — no logic changes; tests green after every move
- **Done when:** no file in `app/` exceeds ~600 lines; `from app import
  database` still works everywhere.

### Refactoring step 5 — Docs & CLAUDE.md split ✅ DONE 2026-07-04

- Split CLAUDE.md: lean core (rules, stack, key files) + `docs/claude/`
  per-vertical files (defects, retail, tracker, coordination, ecom-when-built)
- Fix docs drift: document `solman_sync.py` + `/solman-sync` (key files +
  screens tables), add `main.py`/`archiver.py` to key files
- Rewrite `README.md` for what the app is today (web UI first, correct
  install incl. flask + python-pptx)
- Mark `docs/archive/code-review-findings.md` findings as resolved / archive it
- **Done when:** CLAUDE.md under ~150 lines; README matches reality.

### Refactoring step 6 — UI component library ✅ DONE 2026-07-04

- `app/templates/_macros.html`: shared Jinja macros — page header (title +
  action buttons), filter bar, data table shell, pills/badges, stat cards,
  result box — so every module's UI is assembled from the same components
- Consolidate the repeated inline `<style>` blocks into `style.css`
  component classes (one visual language; new modules inherit it)
- Replace hardcoded `href="/..."` in templates with `url_for(...)` wherever
  a template is touched
- Migrate templates opportunistically (each template switched = old markup
  deleted), starting with the list pages that share the most structure
- **Done when:** a new module's list+detail UI can be built from macros
  without copying HTML from a sibling template.

