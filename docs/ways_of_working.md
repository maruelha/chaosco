# Ways of Working with Claude

Lessons learned from building chaosco together.

---

## Break plans into steps — and do them one by one

Even when a plan feels straightforward, split it into discrete steps and execute them one at a time.

**Why:** Each step is independently testable. Errors get caught before they compound into the next step. A mistake in step 1 that goes unnoticed will be silently built on by steps 2, 3, and 4 — much harder to untangle later.

**How to prompt:** After agreeing on a plan, list the steps explicitly, then say "start with step 1". After each step is done and verified, say "ready for step 2".

**Even simple tasks:** The temptation is to say "just build it all in one go" for small changes. Resist this — the benefit is not about complexity, it is about testability. One step = one thing that can be confirmed to work before moving on.

**The deeper why:** see [why_step_by_step.md](why_step_by_step.md) (2026-08-27) — attention dilution, re-anchoring, self-memory vs. reality, why turn boundaries help even within one session, and how the benefit scales with cheaper models.

---

## Always update documentation after completing a task

After every feature or refactor, update the relevant docs before moving on.

**Files to consider each time:**
- `CLAUDE.md` — key files table, screens table, output/reports section
- `docs/architecture.html` — module descriptions, key files, any architecture sections affected. This is the architecture doc YOU read; the same facts exist as a terse map in `CLAUDE.md` (loaded into Claude's context every session). Both get updated together — deliberately no `architecture.md` as a third copy.
- `docs/screens.html` — screen cards for any new or changed screens/buttons
- `docs/tech_backlog.md` — mark completed items as done, add new known gaps

**Rule of thumb:** Ask "which documents would you touch?" before starting the doc update. Claude will list the files — confirm or adjust, then say go ahead.

**Archived 2026-08-30:** `docs/screens_visual.html` and its screenshots moved to `docs/archive/` — they are not maintained by anyone, and `docs/screens.html` is the single screen reference.

**Also consider:** `docs/dashboard_cards.html` (a card added/renamed/removed), `docs/database_schema.html` (a table or column changed), and the module's own file — since 2026-08-30 **every mini app has one file** in `docs/claude/` and **every shared component one file** in `docs/claude/components/`, indexed by `docs/claude/mini-apps.md` (the map, which also records how the apps connect). A new mini app = its own file (skeleton `_template.md`) + a row in the map + a card row in dashboard_cards.html. Never a combined doc again — and `tests/test_docs_structure.py` fails the
suite if a doc drifts (missing headings, a table or module that no longer
exists, a file missing from the map).

---

## Finished docs go to docs/archive/ (2026-08-30)

A day plan that is executed, a review that is worked off, a session write-up, a
concept that is now built — those move to `docs/archive/`. Nothing there is
maintained and nothing there may be quoted as current; `docs/archive/README.md`
lists what is in it and what was deliberately left out.

**Why:** the docs folder was mixing living reference with three-month-old
plans, and the pairs that existed twice (`v2_blueprint.md` + `.html`) had
silently drifted apart.

---
