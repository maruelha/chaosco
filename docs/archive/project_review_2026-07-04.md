# Project Review — 2026-07-04

Full review of chaosco (docs + code) with a recommendation on cleanup vs rebuild.
Requested by Marina; performed by Claude (Fable 5).

---

## Verdict up front: clean up, don't rebuild

The parts of this codebase that were hard to get right — the schema, the importers, the
unified notes/attachments model — are genuinely good. The mess is almost entirely
**mechanical duplication** in the web layer, plus repo hygiene. That kind of mess can be
removed step by step while the tool keeps running, which matters because it's the daily
driver mid-UAT. A from-scratch rebuild would compete with the actual job for weeks and
risks stalling at 80% with two half-apps to maintain.

Notably, `docs/v2_blueprint.md` half-agrees: its manifest marks the importers, schema,
notes layer, config, and DB as "copy verbatim" — roughly 70% of the system. When a rebuild
plan says "keep most of it unchanged," that's evidence the foundation is sound and only the
top layer needs work.

---

## The docs

The documentation is unusually good for a personal tool, but it has drifted:

- **CLAUDE.md is excellent as a spec but too big as a context file** (~370 lines, loaded
  every session). The tech backlog already has the fix: split into a lean core +
  per-vertical files. The trigger was "when ECOM is built" — pull that forward, since the
  file already carries the full table/screen inventory.
- **Docs drift:** `app/solman_sync.py` and the `/solman-sync` route/screen exist but appear
  **nowhere** in CLAUDE.md — not in the key files table, not in the screens table. Also
  `main.py` and `archiver.py` are missing from the key files table.
- **README.md is stale** — it describes only the original defects CLI pipeline (`run.bat`,
  `python -m app.main`) and says `pip install pandas openpyxl pyyaml` (missing flask and
  python-pptx). It never mentions the web UI, which is now the whole product.
- **`docs/code-review-findings.md` is mostly resolved but doesn't say so.** Findings 1 and 3
  are verified fixed in the code (routes use `try/finally`; `init_db` runs once at startup,
  `web.py:38-43`). The doc should be marked done or archived — otherwise it reads as an
  open bug list.
- **Nine `claude_code_prompt_*.md` scratch files sit tracked in the repo root.** They're
  historical build prompts, not docs. Move to `docs/history/` or delete.

---

## The code

The good news first: **within functions, quality is high.** Type hints, docstrings,
parameterized SQL everywhere (no injection issues found), sensible error handling in the
importers, `with conn:` transactions in the DB layer. `solman_sync.py` — the newest
module — is genuinely clean. The architecture rules in CLAUDE.md (all SQL in `database.py`,
importers never touch annotations) are actually followed. That discipline is rare and it's
why the tool still works after growing this much.

The problems are structural:

### 1. Copy-paste at scale — the number one issue

- `web.py` is 3,039 lines with 145 routes, including **~10 near-identical sets of note
  add/edit/delete routes** (defect, retail, spillover, ecom_gatekeeper, followup, shelf,
  test_learning, test_limitation, cs_followup, meeting_prep). Each set is ~90 lines
  differing only in entity type, label, and back-URL. The irony: the `notes` table is
  already fully generic (`entity_type` + `entity_id`), so the data model supports one
  route set today — only the web layer never caught up.
- `database.py` is 2,822 lines with ~140 functions, of which roughly 60 are clone CRUD for
  the simple entities (links, contacts, todos, followups, cs_followups, test_learnings,
  test_limitations, known_prod_defects, encouragements...). `create_link` and
  `create_contact` differ only in column names.
- The attachment/Ctrl+V-paste JavaScript is **inlined in 9 separate templates.** A fix to
  paste handling means 9 edits, and they will drift.

The tech backlog's "Notes module — consolidate into shared components" entry describes
exactly the right fix and says *"do before adding notes to any further module (ECOM,
Omni)"*. That's the single highest-value refactor available, and it's overdue.

### 2. Dead code from the PDF retirement

`pdf_utils.py`, the `/spillover/report/pdf` route (`web.py:523`), and the top-level
`render_pdf` import are all dead, and the dashboard "Export Reports" button still errors
because `report_exporter.py` calls the retired PDF step. Known and documented — but it's a
broken button on the home screen; delete/rework it before anything else since it's about an
hour of work.

### 3. No tests. None.

For daily solo use this was fine, but it's the real blocker to *any* cleanup — every
refactor is currently done on faith. Before touching the duplication:

- (a) characterization tests on the three importers (feed a sample Excel, assert the rows)
- (b) smoke tests that every GET route returns 200

That's maybe a day of work and it converts every future change from "hope" to "proof".
The v2 blueprint says the same thing in §7.

### 4. Repo hygiene — the git repo is carrying junk

Tracked in git right now:

- five SQLite database snapshots (`archive_db/*.db`, `archive/*.db`,
  `data/Neuer Ordner/*.db` — with real authored data in them)
- an Excel **lock file** (`output/~$retail_report_log.xlsx`)
- a personal annotations export JSON (`data/spillover_annotations_export_*.json`)
- the nine prompt scratch files

The `.gitignore` covers `data/*.db` but not subfolders or `archive_db/`. Also sitting
untracked in the working tree: a `Download/` folder with real exports, an MSI installer,
and PPT temp files. One cleanup session sorts all of this.

### 5. Small things

- `requirements.txt` uses `>=` — pin exact versions so the environment is reproducible a
  year from now (blueprint §8 agrees).
- The one-time dep-cleanup block in `run_web.bat` can go, per the backlog's own note.

---

## On the v2 blueprint — honest opinion

It's a thoughtful document with the right instincts (keep schema/importers, generic entity
pattern, restraint clause, characterization tests first). But **advise against executing it
as a parallel `v2/` build**, for three reasons:

1. **The stall risk is real and the blueprint knows it** — it has a cutover checklist
   precisely because parallel rebuilds stall. One person, mid-UAT, with a go-live: every
   hour on v2 scaffolding is an hour not spent on the tool used tomorrow morning.
2. **The payoff is reachable without the rebuild.** The three big wins — one generic note
   route set, one shared notes template + one `notes.js`, splitting `web.py` into
   blueprints and `database.py` into a package — can each be done *in place* as a shippable
   step. Same target architecture, no cutover, no frozen feature work.
3. **It fits the existing way of working.** `ways_of_working.md` says: discrete steps, each
   independently testable. An in-place strangler refactor *is* that. A parallel rebuild is
   the opposite — a long stretch where nothing is testable in daily use.

Keep the blueprint — it's the best description of the target architecture available. Just
execute it inside `app/` instead of beside it.

---

## Suggested order

1. **Hygiene pass** (half a day): untrack DBs/lock files, fix `.gitignore`, move prompt
   files, delete dead PDF code, fix or remove the Export Reports button, pin requirements.
2. **Safety net** (a day): pytest + importer characterization tests + route smoke tests.
3. **Notes consolidation** (the backlog item): one generic note route set driven by a small
   entity registry, one `_notes_section.html` include, one `static/notes.js`. Kills ~900
   lines of `web.py` and 9 JS copies. **Do this before building ECOM/Omni** — then those
   verticals get full notes for free.
4. **Split the monoliths**: `web.py` → Flask blueprints per area; `database.py` → a package
   (`db/defects.py`, `db/notes.py`, `db/simple_entities.py`...) with re-exports so nothing
   else breaks.
5. **Generic CRUD repository** for the simple entities — only if/when more of them get
   added; don't do it just for elegance.
6. **CLAUDE.md split + docs drift fixes** (solman_sync, README, close out
   code-review-findings).

After steps 1–4 the app would have essentially the v2 architecture, while running every
single day in between. **Recommendation: this project earned a renovation, not a
demolition.**
