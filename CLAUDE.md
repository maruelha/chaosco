# chaosco — Project Context for Claude

Marina's personal UAT coordination toolkit for a retail SAP S/4 migration.
Reads a shared Excel workbook (`DTC_UAT_testtracking_ROE.xlsx`), serves a local
Flask UI at `http://127.0.0.1:8010`. Four workstreams: Retail, Core South,
ECOM, Omni. **Start:** `run_web.bat` (or `python -m app.web`).

## Deep-dive docs (read the one relevant to the task)

| Topic | File |
|---|---|
| Import verticals (Defects / Spillover / Retail), reports, PPT | `docs/claude/verticals.md` |
| Retail Requirements Tracker | `docs/claude/tracker.md` (+ spec `retail-tracker-handoff.md`) |
| Planning/reference modules, notes module, inbox, shelf | `docs/claude/coordination.md` |
| To-do list (features per module + refactoring steps) | `docs/build_plan.md` |
| Screen-by-screen reference | `docs/screens.html` (update this; NEVER `docs/screens_visual.html`) |
| How we work together | `docs/ways_of_working.md` |

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

## How to add a new module (the tracker is the reference implementation)

1. Own DB module `app/db_<name>.py` or a file in `app/db/` (schema +
   `init_schema` + all its SQL).
2. Own Flask **Blueprint** `app/web_<name>.py`; register in `app/web.py`.
3. Templates assembled from `_macros.html` + style.css components.
4. Notes: add an entry to `web_notes.REGISTRY` + `{% include
   '_notes_section.html' %}` — done.
5. Tests for the logic in `tests/test_<name>_*.py`.

## Code layout (post-refactor 2026-07-04)

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
  web_retail_tracker.py   tracker Blueprint (/retail-tracker/...)
  database.py       facade over app/db/
  db/               core(schema) defects spillover retail notes planning
                    reference topics entity_links email jira gatekeeper
                    ecom next_steps order_archive inbox_autofile search
  db_retail_tracker.py    tracker storage
  read_defects.py / spillover_importer.py / retail_importer.py /
  ecom_importer.py / importer.py
  retail_tracker_importer.py / retail_tracker_counting.py
  jira_importer.py  Jira XML → shared jira store (newest .xml per folder)
  solman_sync.py    SolMan status sync (POST /solman-sync)
  archiver.py       Excel archive w/ SHA-256 dedup;  main.py = CLI pipeline
  reporter.py       retail report buckets;  report_exporter.py = HTML+PPTX export
  web_topics.py     Topics card (/topics) — active work: steps, workpad, notes;
                    storage in db/topics.py; teams_link.py/web_teams.py = Teams
                    ping + channel picker; web_email.py + emailer.py below
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

- After every task: update the relevant docs (`docs/claude/*.md`,
  `docs/screens.html`, `docs/build_plan.md`) — ask "which documents would
  you touch?" if unsure.
- Work in verifiable steps; the user confirms each before the next.
- DB migrations: additive `ALTER TABLE` guarded by try/except in
  `app/db/core.py` (and each vertical's `init_schema`), safe to re-run.
