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

**Which docs?** One lookup: **`docs_map.html`** — every doc, its ONE job,
its update trigger, and what enforces it. (The list of files used to be
written out here AND in `CLAUDE.md`; the two copies had already drifted
apart by 2026-09-01, which is exactly the disease — now both point at the
map and the list lives once.)

**What changed on 2026-09-01:** the FACTS side of this rule no longer
relies on remembering. `tests/test_docs_structure.py` fails the suite on
an undocumented table, column, screen or dashboard card, an orphan table,
or a stale docs_map — so a missed doc update cannot be committed. What
remains human is the judgment: does the prose still tell the truth after
the edit? That is the wrap-up skill's coherence pass.

**Rule of thumb:** Ask "which documents would you touch?" before starting
the doc update. Claude will list the files — confirm or adjust, then say
go ahead.

**Archived 2026-08-30:** `docs/screens_visual.html` and its screenshots
moved to `docs/archive/` — they are not maintained by anyone, and
`docs/screens.html` is the single screen reference.

---

## The session ends with /wrap-up (2026-09-01)

Before closing for the day, type **`/wrap-up`** — one word. Claude runs
the checklist in `.claude/skills/wrap-up/SKILL.md` (its ONLY home):
coherence re-read of every doc section edited this session · SessionTest
when a screen changed · MarinaCheckSoon entries for decisions taken on
Marina's behalf · a session summary with the WHY (and the roads NOT
taken) to `docs/archive/session_<date>_<topic>.md` · promote lessons
(technical → `lessons_learned.md`, collaboration → this file) ·
build_plan pruning — when something is added, something goes · commit,
push, report.

**Why a summary with the WHY:** commit messages record what WAS built;
the alternatives considered and rejected exist nowhere else, and they are
exactly what gets re-litigated months later.

**Closing the window without wrapping up** cannot be detected — but the
next session start checks for unwrapped work and offers to run the
wrap-up first (cleanup step 6), so a forgotten wrap-up costs one day,
never more.

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

## Getting a screenshot into the chat (2026-08-31)

`Ctrl+V` does not paste images into the Claude Code prompt on this machine
(tried 2026-08-31 — nothing arrives). Three ways that DO work:

1. **Clipboard → Claude.** Take the shot with `Win+Shift+S`, then say
   *"grab the clipboard"*. Claude runs `tools/clip_image.ps1`, which saves
   whatever image is in the Windows clipboard to
   `%TEMP%\claude_clip\clip_<timestamp>.png` and prints the path — Claude
   reads that file. Images only: copied text or a file copied in Explorer
   are not clipboard images and the script says so.
2. **Screenshots folder.** `Win+PrtScn` (or the Snipping Tool's auto-save)
   writes to `Pictures\Screenshots\` — name the file in the chat and
   Claude opens it.
3. **Any file at all** — just give the path, or drag the file onto the
   terminal. No clipboard involved; Claude reads files directly.

Details, limits and the by-hand command: **`docs/dev_tools.md`** (the
`tools/` folder is workflow helpers only — never part of the app).

---
