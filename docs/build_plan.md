# Build Plan

The single to-do document. Two halves: **feature work by module** (the dashboard
cards) and **refactoring steps** (numbered — "do refactoring step 1" means exactly
what is written under that number).

Sources consolidated here: `docs/project_review_2026-07-04.md` (cleanup plan),
`retail-tracker-handoff.md` (tracker spec + decisions), `docs/tech_backlog.md`.
When an item here is done: mark it done here AND update the source doc.

Last updated: 2026-07-14

> Day plan for 2026-07-05: `docs/build_plan_2026-07-05.md`

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

## Part 1 — Feature work by module

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

### Inbox (`/inbox`)

1. Screenshot-first capture (attach before saving a note) — "maybe" in
   `docs/tech_backlog.md`; silent AJAX-create approach sketched there.
2. ~~ECOM filing target~~ ✅ DONE 2026-07-10: picker option "ECOM", search
   by jira id / test case / name.

### Core South Spillover — done ad-hoc

1. ~~"With whom" column~~ ✅ DONE 2026-07-09: Sales | MB inline select +
   filter (`spillover_annotations.with_whom`).
2. ~~Status-report filter~~ ✅ DONE 2026-07-09: All / In report / Not in
   report + green-✓ Report column (follows `spillover_report_selection`).

### Cross-vertical components — done ad-hoc

1. ~~Next-step archive~~ ✅ DONE 2026-07-10: "↻ New next step" archives +
   clears, History dialog; component `_next_step_history.html` +
   `/next-steps/...` registry Blueprint; on Spillover popup, Retail, ECOM,
   Defect detail (see `docs/claude/coordination.md`).
2. ~~Email mailing lists~~ ✅ DONE 2026-07-09: named recipient selections +
   All/None quick select on /email-report.
3. ~~Order-number search~~ ✅ DONE 2026-07-10: global floating 🔍 widget
   (base.html, hovers over every page incl. the board) searching
   order_details + the imported order cells of Spillover/Retail/ECOM/
   Defects, grouped hits linking to the detail pages. Source-registry
   design (`app/db/search.py`) — FUTURE: topic search = add SQLite FTS5
   sources there; vectorize ONLY if FTS proves insufficient [discussion
   2026-07-10].

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

### Omni vertical (planned, not started)

1. Same as ECOM, after ECOM.

### Follow-ups

1. ~~**Teams ping**~~ ✅ DONE 2026-07-04: deep-link button on list + detail —
   opens a pre-filled Teams chat (1:1 or group via comma-separated emails);
   recipient auto-matched from contacts. Deep links cannot target existing
   named/meeting chats or pre-fill channels — if that is ever needed, the
   Power Automate webhook route (VDI-created, cloud-run) is the upgrade path.

### Jira card — concept REFINED 2026-07-05, see docs/build_plan_2026-07-05.md items 2-6 (do not build until templates provided)

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

> From `docs/project_review_2026-07-04.md`. Each step is shippable on its own;
> the app keeps running throughout. "Do refactoring step N" = do exactly the
> bullet list under N, nothing more.

### Refactoring step 1 — Hygiene pass ✅ DONE 2026-07-04

- Untrack committed junk (files stay on disk, leave git):
  `git rm --cached` for: `archive_db/*.db`, `archive/test_coordination.db`,
  `archive/test_coordinationSpillOver.db`, `data/Neuer Ordner/` (both .db),
  `data/spillover_annotations_export_*.json`, `output/~$retail_report_log.xlsx`,
  `config/settings.local.yaml`
- Extend `.gitignore`: `archive_db/`, `archive/*.db`, `data/**/*.db`,
  `~$*`, `config/settings.local.yaml`, `report_export/` (verify present)
- Move the nine `claude_code_prompt_*.md` root files to `docs/history/`
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
- Mark `docs/code-review-findings.md` findings as resolved / archive it
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
