# chaosco — Project Context for Claude

Marina's personal UAT coordination toolkit for a retail SAP S/4 migration.
Reads a shared Excel workbook (`DTC_UAT_testtracking_ROE.xlsx`), serves a local
Flask UI at `http://127.0.0.1:8010`. Four workstreams: Retail, Core South,
ECOM, Omni. **Start:** `run_web.bat` (creates/uses the project venv
`.venv`, gitignored). Since 2026-08-06 prefer the venv for everything:
`.venv\Scripts\python -m app.web` / `.venv\Scripts\python -m pytest`
(fall back to global `python` only if `.venv` doesn't exist yet).

## Deep-dive docs (read the one relevant to the task)

| Topic | File |
|---|---|
| **START HERE — the map: one line per mini app + per component, and how they connect** | `docs/claude/mini-apps.md` |
| What documentation exists, each doc's ONE job + update trigger + enforcement (GENERATED — rerun `tools/gen_docs_map.py` after adding/removing a doc) | `docs/docs_map.html` |
| One file per mini app | `docs/claude/<app>.md` (skeleton: `_template.md`) |
| One file per shared component (notes, next steps, order details, …) | `docs/claude/components/<component>.md` |
| The shared Excel-import pattern (one tab = one importer + one table) | `docs/claude/import-pattern.md` |
| To-do list (features per module + refactoring steps) | `docs/build_plan.md` |
| Screen-by-screen reference | `docs/screens.html` — the ONE screen doc |
| Readable architecture (layers, data flow) | `docs/architecture.html` |
| How we work together | `docs/ways_of_working.md` |
| Dev tools in `tools/` — helpers for working ON chaosco, NOT part of the app (e.g. getting a screenshot into the chat) | `docs/dev_tools.md` |
| Coding guidelines = the code-review checklist (HOW code is written; architecture.html = WHERE it lives). Rule of rules: every table gets a technical primary key [USER 2026-09-01] | `docs/coding_guidelines.md` |
| Finished plans/reviews/session write-ups (NOT maintained, never a source of truth) | `docs/archive/` (+ its README) |

**Doc rule [USER 2026-08-30]:** every mini app has its OWN file and every
component has its own file — never a combined doc again (`coordination.md` had
grown to 502 lines for 20 apps). Adding a mini app = its file + a row in
`mini-apps.md` + a card row in `docs/dashboard_cards.html`. Enforced by
`tests/test_docs_structure.py` (template headings, the header block's tables
and files must exist, map ↔ folder parity, no dangling `[[links]]`).

## Architecture — non-negotiable rules

1. **Each Excel tab = its own importer + its own SQLite table.** Importers
   write only to imported tables (`defects`, `spillover`, `retail`, `ecom`),
   NEVER to `*_annotations` (user-authored). Never modify the source Excel.
2. **All SQL lives in the storage layer** — the `app/db/` package
   (`app/database.py` is a facade re-exporting it; `from app import database`
   works everywhere). The web layer never writes SQL.
3. **One notes system.** Single `notes` table, generic routes in
   `app/web_notes.py` (registry-driven), shared `_notes_section.html` +
   `static/notes.js`. Never create module-specific notes tables/routes/JS.
4. **Config-driven:** `config/settings.yaml` (machine overrides in gitignored
   `settings.local.yaml` — MERGED over the base since 2026-07-05, local wins) and
   `config/status_mappings.yaml` (retail report buckets).
5. **UI from components:** import `_macros.html` (page header, stat cards,
   sections, tables, pills) + the component classes in `style.css`
   (stat-card, ui-section, ui-table, chip, alarm-box…). Don't copy HTML
   between templates or add inline `<style>` blocks.
6. **Tests are the safety net:** `python -m pytest` (fast, <5s) must be green
   before any commit. New logic (importers, counting, services) gets tests
   first; UI is verified by eye + the route smoke test.
7. **Portable SQL [USER 2026-08-06]:** SQLite is a stepping stone — a later
   move to a hosted Postgres (e.g. Supabase) must stay simple. New or touched
   SQL must be Postgres-compatible: `ON CONFLICT DO UPDATE/NOTHING` is fine;
   NO `INSERT OR IGNORE/REPLACE`, NO `COLLATE NOCASE`, never rely on SQLite's
   case-insensitive `LIKE` (use `LOWER(col) LIKE LOWER(?)`), one datetime
   format only (`isoformat(timespec="seconds")` — no SQL-side
   `datetime('now')`, it's UTC while Python writes local time).

## How to add a new module (the tracker is the reference implementation)

1. Own DB module `app/db_<name>.py` or a file in `app/db/` (schema +
   `init_schema` + all its SQL).
2. Own Flask **Blueprint** `app/web_<name>.py`; register in `app/web.py`.
3. Templates assembled from `_macros.html` + style.css components.
4. Notes: add an entry to `web_notes.REGISTRY` + `{% include
   '_notes_section.html' %}` — done.
5. Tests for the logic in `tests/test_<name>_*.py`.

## Code layout (post-refactor 2026-07-04)

The **terse file map** lives here on purpose [USER 2026-08-30]: this file is
loaded into every session, so the map costs nothing to have at hand. Its pair
is `docs/architecture.html` — Marina's readable version (layers, data flow,
"what may this layer do / not do"). **Do not write the same content twice:**
one line per module here, the explaining prose there; update BOTH when a
module, layer or pattern changes. There is deliberately no `architecture.md`
— a third copy in a third place is what makes docs drift.

```
app/
  web.py            assembler: imports route modules, registers blueprints
  web_core.py       Flask app object + shared web plumbing (no routes)
  web_home|defects|spillover|retail|reports|planning|reference.py
                    feature route modules (flat endpoint names, shared app)
  web_notes.py      generic notes Blueprint (/n/...)
  web_next_steps.py next-step archive Blueprint (/next-steps/..., registry;
                    storage db/next_steps.py; include _next_step_history.html)
  web_search.py     global 🔍 widget Blueprint (/search; source registry in
                    db/search.py — order numbers now, topics via FTS later)
  web_missing_tests.py  Missing Test Cases Blueprint (/missing-tests/ — the
                    ONE list of RETAIL test cases that do not exist yet
                    (ECOM out of scope for now [USER 2026-08-30]); seeds the
                    Retail status report AND the Requirements board ⚠ list,
                    mirrors the Retail retrofits read-only with a coverage
                    note; HTML report + email attachment + copy&paste email
                    text; storage db/missing_tests.py)
  web_retrofits.py  retrofits Blueprint (/retrofits/ — coming system changes
                    per channel; storage db/retrofits.py; rendered at the
                    bottom of the ECOM + Retail reports)
  web_urgent.py     Deadlines & Burning Blueprint (/urgent/ — the nag list;
                    storage db/urgent.py; red dashboard card + the once-a-day
                    dashboard popup _urgent_popup.html)
  web_delegated.py  Delegated Testing Blueprint (/delegated/ — own uploaded
                    Jira XML tagged seen_in_delegated; buckets in
                    delegated_buckets.py; storage db/delegated.py)
  web_blockers.py   Blockers Blueprint (/blockers/ — defects/tasks/business
                    clarifications blocking delegated tickets; own entity,
                    no separate import (shared jira store); storage
                    db/blockers.py; registered keys excluded from the
                    delegated board via web_delegated._load_issues)
  web_smoke.py      CORE SOUTH Smoke Testing Blueprint (/smoke/ — EU CS
                    Smoke Test execution workbook, file-picker upload;
                    overview + eCOM (OMNI/ECOM split) + Retail scenario
                    lists with expandable steps; storage db/smoke.py,
                    importer smoke_importer.py)
  web_sustain.py    Core South Sustainphase Monitoring Blueprint
                    (/sustain/ — daily GBS Operations checklist
                    …DTC_GBS Operations_checklist.xlsx, file-picker
                    upload, one tab per stream per day replaced per tab;
                    Excel-structure day reports w/ expandable detail
                    rows + management summary with attention list;
                    storage db/sustain.py — recomputes ALL statuses,
                    never trusts the workbook's cached formulas;
                    importer sustain_importer.py)
  web_sustain_issues.py  Sustainphase Issues Blueprint (/sustain-issues/
                    — Defects tab of DTC_Sustainphase_Tracking….xlsx,
                    upserted by ASPEN Defect ID with SUS-nnn placeholder
                    keys until the id arrives (then searchable as former
                    id); expandable rows, filters, authored call-outs +
                    next steps; storage db/sustain_issues.py, importer
                    sustain_issues_importer.py)
  web_retail_tracker.py   tracker Blueprint (/retail-tracker/...)
  web_connections.py      entity-connections Blueprint (/connections/...,
                    many-to-many topic↔defect/retail/ecom/spillover;
                    storage db/entity_connections.py; include _connections.html)
  row_validations.py      per-row data-check registry (⚠ button on boards;
                    add a rule = one entry; include _row_validation_dialog.html)
  reporters.py      expected ECOM reporter matching (config ecom_reporters)
  backup.py         DB + uploads backup to backup_folder (dashboard card)
  database.py       facade over app/db/
  db/               core(schema) defects spillover retail notes planning
                    reference topics entity_links entity_connections email
                    jira gatekeeper ecom next_steps order_archive
                    inbox_autofile teams_chats message_types search
                    retrofits urgent delegated blockers smoke sustain
                    sustain_issues missing_tests
  db_retail_tracker.py    tracker storage
  read_defects.py / spillover_importer.py / retail_importer.py /
  ecom_importer.py / importer.py
  retail_tracker_importer.py / retail_tracker_counting.py
  jira_importer.py  Jira XML → shared jira store (newest .xml per folder)
  smoke_importer.py EU CS Smoke Test execution workbook → smoke_scenarios/
                    smoke_steps (WS eCOM/Retail + MB Invoice Validation
                    WAHR filter, steps linked via ParentRow==RowID)
  sustain_importer.py  GBS Operations checklist → sustain_tasks/
                    sustain_task_details (tab pattern (Retail|eCom)_<date>,
                    parent = Task ID row, detail = outline level ≥ 1)
  sustain_issues_importer.py  Sustainphase tracking Defects tab →
                    sustain_issues (columns mapped by header name,
                    Exists-in-production ignored, upsert w/ placeholders)
  solman_sync.py    SolMan status sync (POST /solman-sync)
  archiver.py       Excel archive w/ SHA-256 dedup;  main.py = CLI pipeline
  reporter.py       retail report buckets;  report_exporter.py = HTML+PPTX export
  web_topics.py     Topics card (/topics) — active work: steps, workpad, notes;
                    storage in db/topics.py; teams_link.py/web_teams.py = Teams
                    ping + channel picker; web_teams_chats.py = Teams chats &
                    channels registry (/teams-chats, floating 💬 widget,
                    per-ticket refs); issue_messages.py + web_issue_msg.py =
                    ✉️ issue-message builder (/message-types card, fixed
                    special texts); web_email.py + emailer.py below
  emailer.py        email reports via GMX SMTP (creds ONLY in settings.local.yaml);
                    web_email.py = /email-report Blueprint; recipients in db/email.py
  ppt_utils.py / ppt_retail.py / ppt_spillover.py
  templates/        _macros.html, _notes_section.html, base.html, pages
  static/           style.css (component library), notes.js
tests/              pytest suite (importers, counting, notes, route smoke)
data/test_coordination.db    SQLite (gitignored); uploads in data/uploads/
```

## Stack

Flask (Jinja2, server-rendered) · SQLite · pandas + openpyxl · PyYAML ·
python-pptx · pytest. Pinned in `requirements.txt`. PDF export is retired
(WeasyPrint/GTK failed on Windows) — PowerPoint replaced it; browser
Print → Save as PDF is the manual fallback.

## Conventions

- **`docs/marina_notes/`** — running check-notes for Marina. Whenever
  something comes up mid-work that she should check/decide later, APPEND it
  to `docs/marina_notes/MarinaCheckSoon.html` (dated section, checkbox per
  item) instead of only mentioning it in chat.

- After every task: update the docs the change touches. Which doc has
  which job (+ update trigger + enforcement) is ONE lookup:
  `docs/docs_map.html`. Since 2026-09-01 the FACTS are test-enforced —
  `tests/test_docs_structure.py` fails the suite on an undocumented
  table/column/screen/card, an orphan table, or a stale docs_map — so
  what remains is the judgment part: does the prose still tell the truth?
- At session end (Marina types `/wrap-up`, or asks to wrap up): run the
  **wrap-up skill** — coherence re-read of edited docs, SessionTest,
  MarinaCheckSoon, session summary to `docs/archive/`, lesson promotion
  (`docs/lessons_learned.md`), build_plan pruning ("when something is
  added, something goes"). The checklist lives ONLY in
  `.claude/skills/wrap-up/SKILL.md` — this file and
  `docs/ways_of_working.md` only point at it.
- Work in verifiable steps; the user confirms each before the next.
- **`docs/archive/`** holds finished material (day plans, reviews, session
  write-ups, the old blueprint). Never update a file there and never quote it
  as current; when a plan is executed or a concept is built, MOVE it there.
  `docs/screens_visual.html` + the `ss_*.png` screenshots were archived on
  2026-08-30 [USER]: nobody maintains them, `docs/screens.html` is the one
  screen reference.
- DB migrations: additive `ALTER TABLE` guarded by try/except in
  `app/db/core.py` (and each vertical's `init_schema`), safe to re-run.
