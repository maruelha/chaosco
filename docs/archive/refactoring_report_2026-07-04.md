# Refactoring Report — 2026-07-04

Full-codebase refactoring of chaosco, executed in six verified steps.
Goal (as requested): a sustainable, modular application with separation of
concerns and no unneeded duplication; identical functionality; groundwork for
a component-based UI; test suites so modules can be added and changed without
breaking things; an architecture where modules are added relatively
independently.

**Result: all six steps complete. 86 tests green. Functionality and data
unchanged. Every step is its own commit and individually revertible.**

---

## Safety measures (before and throughout)

- Timestamped database backup taken before any change:
  `archive_db/test_coordination_backup_20260704_*_pre_refactor.db`.
  The live DB was never modified — the refactor touched code only.
- After every step: full pytest run + smoke checks against the real app
  (pages rendered with real data, POST flows exercised).
- One commit per step with a detailed message; any step can be reverted
  alone.

---

## Step 1 — Hygiene pass (commit `6531446`)

- **Untracked committed junk** (files stay on disk, git stops carrying them):
  5 SQLite DB snapshots, an Excel lock file (`~$retail_report_log.xlsx`), a
  personal annotations-export JSON, and `config/settings.local.yaml` (which
  the project rules had always declared gitignored — it never was).
- `.gitignore` extended: `archive_db/`, `data/**/*.db`, `~$*`,
  `config/settings.local.yaml`, `.pytest_cache/`.
- The nine historical `claude_code_prompt_*.md` build prompts moved from the
  repo root to `docs/history/`.
- **Dead PDF code deleted**: `app/pdf_utils.py` and the `/spillover/report/pdf`
  route (WeasyPrint had been retired but the corpses remained).
- **The broken Export Reports dashboard button fixed**: `report_exporter.py`
  now writes dated **HTML + PowerPoint** for both status reports (reusing the
  existing PPT builders). Verified: 4 files written.
- `requirements.txt` pinned to exact versions (+ pytest as dev dependency);
  the obsolete one-time dep-cleanup block removed from `run_web.bat`.

## Step 2 — Test safety net (commit `c2bb623`)

- `tests/test_importers.py` — **characterization tests** that pin the current
  behavior of the three original importers: messy-header normalization
  ("ECOM/\nRETAIL"), blank-row/blank-key/duplicate skip rules,
  first_seen/last_seen idempotency, retail's case-insensitive match key,
  spillover's excel-row identity.
- `tests/test_routes_smoke.py` — every parameterless GET route must return
  200/302. This was the tripwire for the later monolith split.
- These joined the existing tracker suite (importer + counting) and the new
  notes tests from step 3 — **86 tests total, running in under 5 seconds**.

## Step 3 — Notes consolidation (commit `cdf72a2`)

The notes DATA layer was always right (one `notes` table). The web layer was
copy-pasted per module. Now:

- **`app/web_notes.py`** — ONE generic add/edit/delete route set
  (`/n/<entity_type>/<entity_id>/...`) plus JSON endpoints for the
  expand-row list UIs, driven by a small registry (label, list/detail
  endpoints, row getter per entity type). **33 old route functions deleted**
  from web.py (3,039 → 2,272 lines).
- **`_notes_section.html`** — one shared notes block included by all 9
  detail templates. Test Limitations and CS Follow-ups were thereby
  *upgraded* from bare AJAX notes to the full module (headings, edit/delete,
  attachments, Ctrl+V paste) — exactly what the tech backlog had planned.
- **`static/notes.js`** — ONE copy of the attachment upload / paste / delete
  JS, loaded globally via event delegation. The 8 inline copies it replaced
  had already drifted apart (one ended `}());`, the rest `})();` — the
  textbook argument for this step).
- `tests/test_notes_generic.py` — functional coverage on a temp DB
  (roundtrip, empty-note rejection, quick-add redirect, entity-mismatch 404).

## Step 4 — Split the monoliths (commit `e11f7a4`)

- **`database.py` (2,822 lines) → `app/db/` package**, one module per domain:
  `core` (connection + schema + migrations), `defects`, `spillover`,
  `retail`, `notes` (notes + inbox + attachments), `planning` (meeting prep,
  todos, followups, cs_followups, enhancements), `reference` (shelf, links,
  contacts, encouragements, learnings, limitations, order details, ecom
  gatekeeper, report comments, known prod defects).
  `app/database.py` remains as a **facade** re-exporting every public name —
  `from app import database` works unchanged in all callers.
- **`web.py` (2,272 lines) → feature route modules**
  (`web_home/defects/spillover/retail/reports/planning/reference.py`) that
  register on the shared app object from `web_core.py`. `web.py` is now a
  small assembler; `python -m app.web` unchanged.
- **Deliberate deviation from the original plan**: existing routes were NOT
  converted to Flask Blueprints. Blueprint endpoints are name-prefixed
  (`defects.defects_list`), which would have broken every `url_for` in ~40
  templates for zero functional gain. New verticals (tracker, notes) are
  Blueprints — that is the pattern for future modules.
- Mechanical moves only, no logic changes. Verified: 129 routes intact,
  identical endpoint names/URLs, detail pages + reports + export exercised
  with real data. Largest file now 770 lines (was 3,039).

## Step 5 — Documentation (commit `949c774`)

- **CLAUDE.md: ~430 → ~110 lines** — architecture rules (updated for the new
  layout), the 5-step new-module recipe, a code map, and pointers. Details
  moved to `docs/claude/verticals.md`, `docs/claude/tracker.md`,
  `docs/claude/coordination.md` (read only the one relevant to a task).
- **README.md rewritten** for what the app is today (web UI first, correct
  install, tests, config semantics, CLI pipeline as secondary).
- `docs/code-review-findings.md` marked **ARCHIVED** with a per-finding
  resolution note (all nine findings are fixed).
- Old docs drift closed: `solman_sync.py`, `main.py`, `archiver.py` are now
  documented.

## Step 6 — UI component library (commit `fb7c1ab`)

- **`app/templates/_macros.html`** — shared Jinja components: page header,
  breadcrumb, flag banner, pill, stat cards, collapsible colored sections,
  data-table shell. New pages are assembled from these, never copied from a
  sibling template.
- **`style.css` component classes** for the whole app (stat-card, ui-section,
  ui-table, ui-filterbar, chip, comment-input, alarm-box, print rules). The
  tracker pages' large inline `<style>` blocks were moved there (the rt-*/pm-*
  names are aliases of the same rules), so the visual language is defined
  exactly once.
- The board's stat cards were converted to the macros as the reference
  adoption. Hardcoded template URLs: none left except one dynamic JS URL.

---

## The numbers

| | Before | After |
|---|---|---|
| Largest Python file | 3,039 lines (web.py) | 770 (db/reference.py) |
| Note route implementations | ~10 copies (33 functions) | 1 generic set |
| Attachment JS copies | 8 inline (drifting) | 1 file |
| Tests | 0 (before this week) | 86, < 5 s |
| CLAUDE.md | ~430 lines | ~110 + 3 deep-dive files |
| Committed junk (DBs, lock files) | 8 files | 0 |
| Broken dashboard buttons | 1 (Export Reports) | 0 |

## How the goals are met

- **Separation of concerns**: storage (`app/db/`) / routes (`app/web_*`) /
  presentation (templates + macros + one stylesheet) / pure logic (counting,
  importers) are distinct layers with one-way dependencies.
- **No unneeded duplication**: notes, attachment JS, and page styling each
  exist exactly once.
- **Component-based UI groundwork**: `_macros.html` + style.css components.
- **Safe change**: the test suite pins importer behavior, counting rules,
  notes flows, and every route — run `python -m pytest` before any commit.
- **Independent modules**: the recipe in CLAUDE.md (own db module + Blueprint
  + macros + notes-registry entry + tests); the Retail Requirements Tracker
  is the reference implementation. ECOM/Omni can now be built without
  touching existing files beyond two registration lines.

## Follow-ups recorded in docs/build_plan.md

1. `docs/architecture.html` / `docs/database_schema.html` still describe the
   pre-refactor layout — regenerate when convenient.
2. `app/db/reference.py` (770) and `app/web_reference.py` (652) are stacks of
   small independent CRUD groups — split further only if they keep growing.
3. `config/settings.local.yaml` replaces rather than merges the base config —
   a small config_loader improvement.

## User verification requested

Restart the app (`run_web.bat`) and click through the daily pages (defect
detail, spillover report, retail tracker board, inbox). Everything is
test-verified, but the final sign-off is yours.
