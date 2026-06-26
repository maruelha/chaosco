# Ways of Working with Claude

Lessons learned from building chaosco together.

---

## Break plans into steps — and do them one by one

Even when a plan feels straightforward, split it into discrete steps and execute them one at a time.

**Why:** Each step is independently testable. Errors get caught before they compound into the next step. A mistake in step 1 that goes unnoticed will be silently built on by steps 2, 3, and 4 — much harder to untangle later.

**How to prompt:** After agreeing on a plan, list the steps explicitly, then say "start with step 1". After each step is done and verified, say "ready for step 2".

**Even simple tasks:** The temptation is to say "just build it all in one go" for small changes. Resist this — the benefit is not about complexity, it is about testability. One step = one thing that can be confirmed to work before moving on.

---

## Always update documentation after completing a task

After every feature or refactor, update the relevant docs before moving on.

**Files to consider each time:**
- `CLAUDE.md` — key files table, screens table, output/reports section
- `docs/architecture.html` — module descriptions, key files, any architecture sections affected
- `docs/screens.html` — screen cards for any new or changed screens/buttons
- `docs/tech_backlog.md` — mark completed items as done, add new known gaps

**Rule of thumb:** Ask "which documents would you touch?" before starting the doc update. Claude will list the files — confirm or adjust, then say go ahead.

**Never touch:** `docs/screens_visual.html` (contains real screenshots, manually maintained).

---
