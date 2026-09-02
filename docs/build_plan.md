# Build Plan

The single to-do document. Two halves: **feature work by module** (the dashboard
cards) and **refactoring steps** (numbered — "do refactoring step 1" means exactly
what is written under that number).

Sources consolidated here: `docs/archive/project_review_2026-07-04.md` (cleanup plan),
`retail-tracker-handoff.md` (tracker spec + decisions), `docs/tech_backlog.md`.
When an item here is done: mark it done here AND update the source doc.

Last updated: 2026-09-01 — finished sections MOVED to
`docs/archive/build_plan_done_2026-09-01.md`; standing rule since then:
**when something is added, something goes** [USER 2026-09-01].

> Day plan for 2026-07-05: `docs/archive/build_plan_2026-07-05.md`

## Open decisions & tasks waiting on Marina (parked 2026-07-09)

1. **Teams review list placement** — dashboard card (Claude's
   recommendation) vs Inbox section vs both; the only blocker for that
   build (`docs/teams_review_concept.md`).
1b. ~~Sales report v1~~ ✅ BUILT 2026-07-12: `/ecom-gatekeeper/sales-report`
   — all tickets assigned to Marina, grouped in-gatekeeping /
   in-validation, next steps + order numbers + editable call-outs (key
   'sales'), print + HTML download. Layout iterations still to come
   [USER: "we will talk about layout later"].
2. **Day-plan confirmations**: Excel push mode (dated snapshot files with
   only-new rows — recommended) · step 9: file inbox→To-Do as NEW todo
   only, or also into existing? · step 10: due date on promises?
3. **Tracker data tasks** (5–15 min of clicking, list in
   `docs/marina_notes/MarinaCheckSoon.html`): work the unresolved picks,
   judge/park the passed tests that match no requirement (Assign / Park /
   → Clarify buttons on Import & admin), set the unknown payment-method
   categories.

✅ Jira XML folders RESOLVED 2026-07-09: `Download/jira_gatekeeper/` and
`Download/jira_ecom/` created; paths in `settings.yaml`
(`jira_gatekeeper_folder` / `jira_ecom_folder`); importer takes the newest
`.xml` per folder.

4. **Jira exports** — gatekeeper export ✅ RECEIVED 2026-07-11 (trial
   verified). SUPERSEDED 2026-07-12 by the ONE unified import
   (`jira_folder` = the old gatekeeper folder; `jira_ecom` retired).
   STILL OPEN [MARINA]: broaden the saved Jira search so the export also
   CONTAINS the ECOM-board tickets — recommended JQL:
   `assignee WAS currentUser()` OR the board epics. That lights up the
   ECOM board's Jira columns/cards + enables the description-change
   auto-flag.

---

## Part 0 — Docs & quality cleanup (concept agreed 2026-09-01)

The concept itself lives at the top of `docs/docs_map.html` (one job per
doc · facts generated/tested, meaning hand-written · story → rule → test).
Round 1 is done, round 2 is agreed, round 3 is noted:

**Round 1 — the docs cleanup, six steps:**

1. ✅ DONE 2026-09-01 — `docs/docs_map.html` (GENERATED index:
   `tools/gen_docs_map.py`, parity test in `test_docs_structure.py`) +
   `docs/coding_guidelines.md` skeleton seeded with the ONE new rule
   (every table gets a technical primary key [USER 2026-09-01]; 68/70
   comply, the two email join tables are round-2 work).
2. ✅ DONE 2026-09-01 — four facts-coverage tests in
   `test_docs_structure.py`: every table AND column → its card on
   `database_schema.html`; every user-facing GET page + every URL namespace
   → the docs (two altitudes ON PURPOSE — the Nth per-row CRUD sub-route is
   prose, never a bullet each; `.json` endpoints auto-exempt); dashboard
   cards ↔ the dashboard template, both directions; every table claimed by
   at least one doc header (per-doc completeness deliberately NOT required —
   core.py/planning.py are shared schema modules; `defect_notes` = the one
   named legacy exception). Audits first, tests second: the audits found
   ZERO real gaps (the 2026-09-01 email-docs repair had covered them), so
   the tests freeze a clean state. Verified they bite (probe table failed
   2 tests; unlisted doc fails the map test).
3. ✅ DONE 2026-09-01 — `.claude/skills/wrap-up/SKILL.md` (in git, both
   machines): coherence re-read of edited sections · SessionTest when
   templates/static/web changed (git-diff check, else say why not) ·
   MarinaCheckSoon for decisions taken for Marina · session summary WITH
   the rejected alternatives to `docs/archive/session_<date>_<topic>.md`
   (existing naming) · promote lessons (story → rule → test) · build_plan
   one-in-one-out · push + report. `docs/lessons_learned.md` created,
   seeded with 8 real stories (additive-edit contradictions, hand-typed
   facts, the moved header row, cached Excel formulas, the two-renderer
   wrong email report, the 502-line combined doc, SQLite-only SQL, the
   WeasyPrint dead end). The what-to-document lists in `CLAUDE.md` and
   `ways_of_working.md` are now POINTERS (docs_map + the skill) — the
   checklist lives once, in the skill. ways_of_working gained the
   "/wrap-up ends the session" section.
4. ✅ DONE 2026-09-01 — `dashboard_cards.html` trimmed to the MENU:
   every card says what it is FOR, nothing more [USER 2026-09-01]. Checked
   first: every fact in the long cards already existed in `screens.html`
   (the two files had become near-duplicates — which is why they were
   hard to tell apart), so nothing needed moving and nothing was lost.
   Titles, URLs and accent colors unchanged (the parity test pins the
   card set); subtitle + footer now state the job and the enforcement.
5. ✅ DONE 2026-09-01 — this file went 1615 → 467 lines: 17 finished
   sections (9 whole modules, the done logs of 7 mixed ones, refactoring
   steps 1–6) moved VERBATIM to
   `docs/archive/build_plan_done_2026-09-01.md`; every still-open bullet
   was carried back under a slim heading. Verified line-by-line: the only
   line in neither file is the old "Last updated" stamp. Standing rule
   from now on: when something is added, something goes [USER 2026-09-01]
   (a wrap-up skill step).
6. ✅ DONE 2026-09-01 — `.claude/settings.json` (checked in → both
   machines): (a) PreToolUse hook on Bash — a command containing
   `git commit` first runs `tests/test_docs_structure.py`; on failure the
   commit is BLOCKED (exit 2) with the failing output. Verified live: the
   sentinel proof fired in-session, and a probe doc made the gate return
   exit 2. (b) SessionStart hook — counts commits since the newest
   `docs/archive/session_*.md`; when > 0 it hands Claude the context to
   offer /wrap-up for the previous session before new work. It will nag
   from the first session start onward until the FIRST real /wrap-up
   writes a summary — that is correct; the first one ran the same day.

**Round 2 — code review after every build (planned):** full review of the
app; findings fill `docs/coding_guidelines.md`; greppable guidelines become
tests (incl. the technical-PK scan); fix `email_list_members` /
`email_list_reports` PKs; review-after-build joins the routine.

**Round 3 — ideas noted 2026-09-01 [USER], not planned yet:**

- **Slim CLAUDE.md** — move what does not earn its always-loaded cost to
  the correct home (no duplication; save at the right place). CAUTION
  recorded with it: the seven rules are load-bearing BECAUSE they are
  always in context — the portable-SQL rule nearly got lost when it lived
  only in prompts (lessons_learned.md #7); a rule Claude must look up is
  not in its head while writing code. The bulk of CLAUDE.md is the ~90-line
  file map, not the ~30-line rules — evaluate THAT first. Each rule's
  story/why already lives outside (architecture.html, lessons_learned).
- **Markdown sources, generated HTML** — a tool that renders docs/*.html
  from .md sources: Claude edits the md, /wrap-up regenerates the html.
  Would resolve the html/md duality properly (the "no architecture.md"
  rule banned a third COPY; a generated rendering is not a copy — same
  facts/meaning concept applied to format), possibly also for
  architecture.html alone as a first slice. Costs to weigh: a template
  pipeline (screens.html / database_schema.html are styled card layouts,
  not naive markdown), converting 2300-line files, and marina_notes/
  stays html on purpose (checkboxes + localStorage are the point).
- **Test inventory** [USER 2026-09-01]: a list of every test and, in
  plain words, what it is actually testing — so Marina can manually
  scan it and judge whether we are over-testing (too many tests for the
  same behavior, tests that don't earn their keep). Not scoped yet:
  could be a generated doc (parsed from test names/docstrings) or a
  page in the app; where it lives and how it's kept current (generated
  vs. hand-maintained) still to be decided.

---

## Part 1 — Feature work by module

**Fully built, logs in the archive** (no open items left here): Email
Reports · Core South Sustainphase Monitoring · CORE SOUTH Smoke Testing ·
Manual Test Cases · Core South Spillover · Meeting Prep + Retrofits ·
Cross-vertical components · Reports/Export · Follow-ups. The sections
below keep only their OPEN items — their build logs are in the archive
too.

### Missing Test Cases (`/missing-tests/`) — ✅ BUILT 2026-08-30

Build log → `docs/archive/build_plan_done_2026-09-01.md`. Still open:

- report heading wording on the Retail status report ("Missing test cases
  (on top of total test cases)") — to confirm
- ECOM has no equivalent list yet; the module is Retail-only on purpose

### Sustainphase Issues (`/sustain-issues/`) — ✅ BUILT 2026-08-28

Build log → `docs/archive/build_plan_done_2026-09-01.md`. **Parked [USER 2026-08-28]:** SPOT_CHECKS tab → its own
similar upload-and-view mini app, ANOTHER session. SMOKETEST_KT tab stays
ignored (KT tracking lives on the Smoke scenarios).

### Delegated Testing (`/delegated/`) — ✅ BUILT 2026-08-26…09-02

23 build items done — log → `docs/archive/build_plan_done_2026-09-01.md`;
chat-driven additions are logged ONLY in the session summaries under
`docs/archive/session_2026-09-0*_*.md` (no running list here any more —
it only grew); deep-dive `docs/claude/delegated.md` +
`docs/claude/components/note-pages.md`. Still open:

5. **PARKED — Excel/ECOM join** [USER 2026-08-26]: show the `ecom` rows
   (from the ROE tracking import) matched by Jira key next to the Jira
   data. Marina unsure about scope — re-discuss first.
- **PARKED — TXT export for Meeting Summaries** [USER 2026-09-01:
  "revisit later when I know how i want to use it"].
- `Accepted` not counting toward the weekly goal is to be re-confirmed
  with management [USER 2026-08-27] — tracked in MarinaCheckSoon.
- Blockers "Jira status never updating" — open investigation, the "as of"
  stamp on /blockers/ is the diagnostic; tracked in MarinaCheckSoon.

### Retail Requirements Tracker (`/retail-tracker/board`)

Built; log (items 2, 3, 5, 7, 8) → `docs/archive/build_plan_done_2026-09-01.md`. Backlog:

1. **Override button** — BACKLOG ONLY [USER 2026-07-05: "I don't think I
   need it"]. Table + counting support already exist; build the UI action
   only if the need ever arises.
4. Cosmetic backlog: the Excel names the same test twice → near-duplicate
   Return rows. HALF FIXED 2026-07-09 [USER]: the GKP2002/GKPMU000062 dup
   ("Blind Return" under 8. Payment Methods) was deleted from the DB —
   "OFFLINE Return" remains. Still open: the GKP1015/GKPMU000048 pair
   ("Blind Return giftcard" row 82 vs "Blind return" folded row) — same
   treatment if Marina wants. CAVEAT: a tracker re-import would resurrect
   deleted rows (upsert by area+excel_row; Excel is retired, so low risk —
   the ignore mechanism stays backlog).
6. BACKLOG [USER 2026-07-06]: maybe rethink the one-test-per-requirement
   limit (a requirement can currently link exactly ONE dashboard test).
   Would need a link table + counting change. Decide only if the easy
   version (item 5, done) proves insufficient.

### Inbox (`/inbox`)

1. Screenshot-first capture (attach before saving a note) — "maybe" in
   `docs/tech_backlog.md`; silent AJAX-create approach sketched there.
2. ~~ECOM filing target~~ ✅ DONE 2026-07-10: picker option "ECOM", search
   by jira id / test case / name.

### Deadlines & Burning (`/urgent/`) — ✅ BUILT 2026-08-11

Build log → `docs/archive/build_plan_done_2026-09-01.md`. **Later / if needed**: notes on entries · recurring
items · a "snooze until date" instead of the per-day dismissal · surfacing
the popup on pages other than the dashboard.

### Known Production Issues (`/prod_defects`) — ✅ BUILT ad-hoc 2026-08-06…27

13 build items done incl. the management report — log → `docs/archive/build_plan_done_2026-09-01.md`. Still open
[MARINA]: the data-entry pass — the management report gates on
Channel=ECOM + BOTH audience ticks, so existing entries need Channel and
the two flags set before the report shows them (same cleanup as the ids).

### Teams end-of-day review list (planned, placement open)

1. Clickable list of saved Teams chat/channel links with a "check" mark and
   a checked-only filter for Marina's end-of-day sweep — full concept,
   decisions, and implementation sketch in `docs/teams_review_concept.md`.
   OPEN [USER]: placement — separate dashboard card (recommended) vs Inbox
   section vs both. Reuses the Links storage (tool = "Teams Channel") and
   the AJAX component pattern; NO walkthrough automation (decided
   2026-07-06).

### Topic dossiers / focus-switch view (DISCUSSION NOTES 2026-07-14 — not yet a build plan)

Captured from the planning discussion with Marina; open questions below must
be answered before anything is built.

**Core insight [USER]:** the expensive part of the day is the FOCUS SWITCH —
"when I go to a topic I want to at a glance see what happened and what needs
to happen next." Copying items in as she goes is fine ("cool to have
everything in one space"); the missing payoff is the consolidated per-topic
view, not a capture tool. (The original "alternative snipping tool" idea is
superseded by this.)

**Hard constraints [USER]:**
- Nothing leaves the computer — no cloud services, no external AI APIs.
  Any OCR/embedding/parsing must run locally.
- No Jira API (or Teams read/API) without OFFICIAL confirmation first —
  "important to do everything correctly." Jira API + Teams read access
  should go into ONE approval request; Claude offered to draft the scope
  text. Playwright-scraping Teams as an approval workaround: REJECTED
  (compliance + the Teams web client is automation-hostile).
- Second computer reaches neither Jira nor chaosco; Teams stays the
  transfer channel from there.

**Target shape — topic dossier page:** a topic is a BUNDLE (discussion-
shaped, not ticket-shaped: emails, long conversations, meeting fragments +
linked tickets/test cases/defects accumulating over weeks):
1. "Next" headline on top (reuse the next-step + history component).
2. Merged timeline, newest first, across ALL sources: notes, filed Teams
   snippets, Jira status/comments, Excel status changes, order logs.
3. Two entry kinds: short EVENTS shown in full; long DOCUMENTS (email
   threads, chat discussions, minutes) collapsed to one gist line —
   date, source, gist — expandable to full text.
4. Linked entities' status changes flow in automatically (entity_links
   table + Topics module exist as seeds).

**Inputs:** paste-as-you-go (~30 items/day, auto-routing by known
identifiers — jira keys, order numbers, test case ids — with auto-file on
a single confident match + review list); emails via .eml/.msg text
extraction (stdlib/extract-msg, local); meeting minutes LATER [USER
2026-07-14: "ideally at some point"] — docling (local) is the candidate
parser if minutes/PDF/DOCX volume materialises, overkill for pasted text.

**Search (load-bearing, decided direction):**
1. FTS5 full-text over notes/documents/emails first — free, local, exact
   for identifier-rich queries.
2. Local SEMANTIC layer as a PLANNED second step — [USER 2026-07-14]: "I
   would be searching with different words because I am just coordinating,
   not a topic expert" — the vocabulary-gap case is exactly where
   embeddings help. Local-only (e.g. small sentence-transformers model +
   sqlite-vec); NO cloud embedding APIs. Supersedes the earlier
   "vectorize only if FTS proves insufficient" lean for topic content.

**Outbound:** compose day-close/report text in-app, deliver via prefilled
Teams deep links (teams_link.py mechanism exists) — Marina reviews and
presses send herself. Day-close cockpit (SAP-checks pending → Jira
round-trip → reports) as a later phase.

**OPEN [USER — decide when fresh]:**
1. Gist line on long documents: typed by Marina at paste time vs
   auto-first-sentence + edit (Claude's lean: auto + edit; discipline
   requirements kill tools).
2. Is the existing Topics card the seed of the dossier, or unused — and if
   unused, why? (Decides upgrade-in-place vs rethink.)
3. Approval request for Jira API + Teams read: does Marina want the draft?

### ECOM vertical — built 2026-07-09/11

Build log → `docs/archive/build_plan_done_2026-09-01.md`. Still open:

4. **Description-change auto-flag** (optional add-on): flag an ECOM row
   when a Jira re-import changes the stored description — signal for the
   description_change workflow (today only the Excel's Δ column shows).
   Needs the broadened Jira search first (→ "waiting on Marina" item 4).
5. New workflow statuses will surface as red pills on the report's
   diagnostics box — extend `config/status_mappings.yaml` as they appear
   (30-second config edit, no build task).

### Omni vertical (planned, not started)

1. Same as ECOM, after ECOM.

### Jira card — concept REFINED 2026-07-05, see docs/archive/build_plan_2026-07-05.md items 2-6 (do not build until templates provided)

Parked 2026-07-04 after a feasibility chat. Known so far:
- Source: Jira **XML export** (issue search → Export → XML) — unlike CSV it
  includes the full comment thread (author, timestamp, HTML body). ~1000-issue
  cap per export. Python stdlib ElementTree reads it fine, no new deps.
- Architecture (per the existing future-integration rule): own tables
  (`jira_issues` upserted by key + `jira_comments` replaced per import),
  NEVER merged into Excel-sourced tables. Importer mirrors the Excel pattern
  (newest matching file in downloads_folder, first_seen/last_seen).
- Card sketch: filterable list; detail with description + comment thread
  (rendered HTML) + open-in-Jira link + notes module + inbox filing.
- Before building: Marina defines the concept; then ONE real sample XML
  export to pin the parser + tests against.

### Cross-module navigation

1. Make `defect_id_ref` on Retail rows a clickable link to the Defect detail.
2. ~~Clarify the follow-up trackers~~ ✅ RESOLVED 2026-07-05 [USER]: three
   deliberately distinct cards — CS Follow-ups = topics needing attention
   before go-live (topic tracker); Follow-ups = what others promised MARINA;
   Promises (planned, day plan step 10) = what Marina promised others.
   No consolidation.

---

## Part 2 — Refactoring steps (do in order; each is one instruction)

> From `docs/archive/project_review_2026-07-04.md`. Each step is shippable on its own;
> the app keeps running throughout. "Do refactoring step N" = do exactly the
> bullet list under N, nothing more.

### Refactoring steps 1–6 — ✅ ALL DONE 2026-07-04

Hygiene pass · test safety net · notes consolidation · monolith split ·
docs/CLAUDE.md split · UI component library. Full logs → `docs/archive/build_plan_done_2026-09-01.md`.

### Follow-ups discovered during the refactor

- Architecture/DB-schema HTML regeneration → moved to the 2026-07-05 day
  plan (step 11).
- `app/db/reference.py` (770 lines) and `app/web_reference.py` (652) are the
  two largest files — both are stacks of small independent CRUD groups;
  split further only if they keep growing.
- ~~settings.local.yaml replace-instead-of-merge~~ ✅ FIXED 2026-07-05
  (config_loader merges, local wins; tests added).

### Conditional (not scheduled)

- Generic CRUD repository for the simple entities (links, contacts, todos, …)
  — only worth it when the NEXT simple entity gets added; don't do it for
  elegance alone (review recommendation).

---

## Part 2b — Modular-architecture retrofit (from the 2026-08-06 code review)

> Goal [USER 2026-08-06]: reuse instead of duplication; feature modules run
> independently around a shared kernel (dashboard + cross-cutting services
> like order search plug features in via registries, features never import
> each other); ONE shared look (style.css/_macros/base.html carry the whole
> UI). End-state test after step 10: unregister one feature in `web.py` →
> app still boots, its dashboard card / search source / notes entity simply
> disappear. Steps ordered by value-per-effort; each is shippable alone with
> the 318-test suite as tripwire. Review details: chat session 2026-08-06.
>
> **Model guidance per step [2026-08-06]:** Sonnet is fine for the
> careful-but-mechanical steps — 7, 8, 9 and the inline-style sweep in 13
> (self-contained instructions + "Done when" checks + test tripwire).
> Prefer Fable/Opus for the judgment-heavy ones: **10** (registry design —
> everything else plugs into this shape), **12** (schema split, migration
> correctness on a live DB on two machines), and the `web_reference.py`
> breakup in **13**. Step 11 is in between: Sonnet OK, but run the full
> suite after each module, no batching. If a Sonnet session goes sideways
> (repeated test failures, "simplifying" things), switch to Fable for that
> step instead of pushing through — the step boundaries make that clean.

### Refactoring step 7 — Shared plumbing (kill the 15× duplication)

- ONE `_cfg` + `_get_conn`: every web module imports them from `web_core`
  (currently re-defined in 15 modules; config exists as 15 copies).
- `_rows_to_dicts` imported from `db/core` everywhere (verbatim copies live
  in `db/jira.py`, `db_retail_tracker.py`).
- Break the circular facade imports: `db/ecom.py`, `db/jira.py`,
  `db_retail_tracker.py` import `app.database` only for `get_connection` —
  change to `from app.db.core import get_connection` (3 one-liners).
- Fix cross-module reach-ins: `web_search.py` imports `web_notes.REGISTRY`
  + private `_urls` → move the notes registry to a neutral module both can
  import. `web_reference.py` deferred-imports parsing helpers from
  `jira_importer` (5 sites) → extract `extract_order_numbers` /
  `extract_ac_order_pairs` into a pure text-utils module.
- Replace the `assert` guard in `db/jira.py:94` with a `ValueError`;
  fix the `database.init_schema` name collision (7 modules export
  `init_schema`, last star-import wins silently).
- **Done when:** `_get_conn` is defined exactly once; no web module imports
  another web module's internals; the facade exports no colliding names.

### Refactoring step 8 — One importer engine

- Generalize `manual_importer`'s `_SPECS` pattern (sheet name, header map,
  key fields per vertical) into ONE shared parse routine for defects /
  retail / ecom / spillover / manual (~250 duplicated lines deleted;
  ecom & spillover currently ~74% verbatim copies of retail).
- This automatically gives ecom + spillover the header-alias first-wins
  guard that only retail/manual have today (latent silent-garbage bug).
- Delete the dead duplicate paths: `spillover_importer.run_spillover_import`
  + its private skiplog writer; unused `parse_manual_retail/_ecom` wrappers.
- Guard `_write_skiplog` inside `run_import`'s per-tab try/except so a full
  disk / bad skiplog folder can't 500 an otherwise-successful import.
- **Done when:** one parse routine, per-vertical specs only; all importer
  tests green incl. new alias-guard tests for ecom + spillover.

### Refactoring step 9 — Shared report + annotation toolkit

- ONE `_report_context` / report-download / save-excel helper parameterized
  by vertical (currently 2–3 near-identical copies across `web_retail`,
  `web_ecom`, `web_manual_tests`).
- `gather_attachments` (emailer) checks `resp.status_code` before attaching
  — today a 500 error page gets mailed to stakeholders as "the report".
- ONE single-field annotation-save helper (5+ near-identical savers in
  `web_spillover` / `web_retail`); shared query-flag banner helper for the
  `saved / note_added / …` blocks re-typed in every detail route.
- **Done when:** the duplicates are deleted and a broken report page fails
  the email send loudly instead of attaching the error page.

### Refactoring step 10 — Registries for the cross-cutting services

- Search: `db/search.py`'s hardcoded 7-block function becomes a source
  registry — each feature registers its search source (SQL + URL builder).
- Dashboard: card registry — each feature registers its card(s); the home
  template renders the registry.
- Email reports: each `REPORT_CHOICES` entry carries its render URL /
  attachment builder (no hardcoded branch list in `gather_attachments`).
- Notes: registry entries contributed by feature modules at registration,
  endpoint strings validated at startup (typos currently fail silently).
- `base.html` widgets (search 🔍, chats 💬, enhancements) become pluggable
  includes so a deployment without a feature doesn't carry dead fetches.
- **Done when:** the end-state test above passes (unregister one feature →
  everything else keeps working, its entries vanish).

### Refactoring step 11 — Blueprint conversion of the legacy seven

- Convert `web_home/defects/spillover/retail/reports/planning/reference`
  from flat `@app.route` to Blueprints like the other 15 modules.
  Endpoint names change → sweep `url_for` in templates + notes registry;
  route-smoke suite is the tripwire (this was deliberately skipped in
  step 4 to avoid breaking ~40 templates — do it template-sweep-first now).
- **Done when:** every feature is a Blueprint; one route pattern app-wide.

### Refactoring step 12 — Schema ownership split

- Move each feature's tables out of `db/core.py`'s 26-table `executescript`
  into the owning module's `init_schema` (14 newer modules already work this
  way). `core` keeps only genuinely shared infra (notes/attachments if kept
  central, connection helper, migration helper).
- Consolidate the 21 scattered try/except `ALTER TABLE` migrations behind
  one shared migration helper in `db/core`.
- **Done when:** "feature = blueprint + storage module + own schema +
  templates" holds for every feature; a feature's files can be copied into
  a new app without carrying foreign DDL.

### Refactoring step 13 — Break up `web_reference.py` + UI consistency sweep

- Split the 1,064-line grab-bag: shelf / contacts / links / prod defects /
  encouragements / learnings / limitations → small feature modules;
  gatekeeper pages → the jira/gatekeeper vertical; `report_comments` →
  the shared report toolkit (it is called by exporter + emailer).
  Also move the 3 raw SQL statements in `web_reference.py` into `db/ecom.py`.
- Inline-style sweep [USER 2026-08-06: one shared look]: migrate the ~980
  inline `style="…"` attributes into `style.css` component classes, worst
  pages first (`inbox.html` 65 · `retail_tracker_board.html` 57 ·
  `retail_report_diagnostics.html` 52 · `ecom_gatekeeper.html` 51);
  extract `base.html`'s ~200 lines of inline widget JS into `static/`.
- **Done when:** no module is a multi-feature grab-bag; the app's look is
  controlled solely by `style.css` (inline styles ≈ 0).

### Refactoring step 14 — ONE 📣 report call-outs partial (added 2026-09-02 [USER])

- The editable 📣 call-outs block (`report_comments`: "+ Add call-out",
  inline edit, 🗄 archive + the archived expander, static text in
  downloads) is copied into FIVE report templates today:
  `delegated_report.html` · `delegated_numbers.html` ·
  `delegated_overview.html` · `gatekeeper_sales_report.html` ·
  `spillover_report_table.html` (the read-only bullets macro
  `_report_blocks.additional_comments` is shared, the EDITING is not).
  Extract one `_report_callouts.html` include (parameters: report key,
  comments, archived list, `download` flag) + one shared JS block; swap the
  five copies to it. Replace `web_reports.report_comment_add`'s hardcoded
  key tuple with a registry so a new report is one entry (the missing
  `delegated` key silently 400ed for a day in August).
- **Done when:** the five templates contain only the include, the route
  smoke tests still see "+ Add call-out" on every report, and a sixth
  report (or a per-day page) can use call-outs with one include line.

### Cross-cutting rules (apply during every step above)

- **Portable SQL [USER 2026-08-06, standing]:** new/touched SQL must stay
  Postgres-compatible — no `INSERT OR IGNORE` (use `ON CONFLICT DO
  NOTHING`), no `COLLATE NOCASE`, case-insensitive matching via `LOWER()`
  not SQLite's `LIKE` default, one datetime format
  (`isoformat(timespec="seconds")`, no SQL-side `datetime('now')` UTC mix).
  Candidate CLAUDE.md rule — add on Marina's go.
- **Foreign tables only via the owning db module's functions** — features
  may share data, never write their own SQL against another feature's
  tables (also fix the 4 stray statements in `jira_importer.py`).
- Test hygiene when convenient: a `tests/conftest.py` (tmp DB + config
  patch before `app.web` import) removes the real-DB touch at import time
  and the ~30 hand-rolled fixtures.
