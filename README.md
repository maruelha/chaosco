# chaosco

A personal toolkit for the chaos coordinator of a retail SAP S/4 UAT —
defect tracking, test-case execution, sign-off readiness, requirements
coverage, and day-to-day coordination (meetings, todos, follow-ups, notes
with screenshots) in one local web app.

It reads the team's shared Excel workbook (`DTC_UAT_testtracking_ROE.xlsx`)
**read-only**, keeps everything in a local SQLite database, and never writes
back to the Excel.

## Quick start

Double-click **`run_web.bat`** — it installs dependencies, frees port 5000,
and opens `http://127.0.0.1:5000`.

Manually:

```
pip install -r requirements.txt
python -m app.web
```

## What's inside

- **Dashboard** with cards for every module
- **Import** (button on the dashboard): finds the newest Excel export in the
  configured downloads folder, archives it (SHA-256 dedup), and upserts the
  Defects / Core South Spillover / Retail tabs — idempotent, never deletes
- **Defects, Spillover, Retail** — filterable lists, detail pages with
  personal annotations, status reports (HTML / PowerPoint / Excel log)
- **Retail Requirements Tracker** — live requirements-vs-test-executions
  board derived from current Retail statuses (see
  `retail-tracker-handoff.md`)
- **Coordination**: inbox capture pad, shelf, meeting prep + agenda exports,
  todos, follow-ups, links, contacts, encouragements, test learnings &
  limitations, ECOM gatekeeper
- **Notes everywhere** — one shared notes module (headings, edit/delete,
  file attachments, Ctrl+V screenshot paste) on every detail page

## Configuration

`config/settings.yaml` (committed) holds paths, sheet names, hidden statuses.
Machine-specific overrides go in `config/settings.local.yaml` (gitignored) —
note it **replaces** the base file when present, so copy the whole file.

## Tests

```
python -m pytest
```

Fast (<5 s). Covers the importers (characterization), the tracker counting
service, the generic notes routes, and a smoke test over every GET route.
Keep it green before committing; add tests for any new logic.

## CLI pipeline (headless import)

`run.bat` / `python -m app.main` runs parse → archive → import → summary
without the web UI. `python -m app.read_defects` prints the parsed Defects
tab without writing anything.

## Documentation

- `CLAUDE.md` — architecture rules + code layout (start here)
- `docs/claude/*.md` — per-area deep dives
- `docs/build_plan.md` — the consolidated to-do list
- `docs/screens.html` — screen-by-screen reference
- `docs/database_schema.html`, `docs/architecture.html` — visual docs
