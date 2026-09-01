---
name: wrap-up
description: End-of-session wrap-up for chaosco — the judgment pass no test can do. Coherence re-read of edited docs, SessionTest when screens changed, MarinaCheckSoon, session summary with the WHY, lesson promotion, build_plan one-in-one-out, then commit and push. Run when Marina types /wrap-up, says "wrap up" / "end of session", or before she closes for the day.
---

# /wrap-up — close the session properly

The facts are already guarded by the suite (`tests/test_docs_structure.py`
fails on undocumented tables, columns, screens, cards, orphan tables, or a
stale `docs_map.html`). This skill is the **judgment pass** — the part no
test can do — plus Marina's material. Do the steps in order; skip a step
only when its trigger genuinely did not fire, and say so in the final
report.

**Session scope** = everything since the last session summary in
`docs/archive/` (or since this session's first commit if summaries are
newer). Establish it first:

```
git log --oneline <last-wrapped-commit>..HEAD
git diff --stat <last-wrapped-commit>..HEAD
```

## 1 · Facts pass (mechanical)

- Full suite green: `.venv\Scripts\python -m pytest -q` — do not proceed red.
- Docs added/removed this session → `.venv\Scripts\python tools\gen_docs_map.py`
  (the suite fails anyway until this is done).

## 2 · Coherence pass — the additive-edit trap

For **every doc section edited this session**: re-read the whole section
top to bottom, not just the added lines. Look for old prose that the new
prose now contradicts (2026-09-01: two docs said the opposite of
themselves because edits were bolted on top — see
`docs/lessons_learned.md`).

Then: did a **shared** thing change (a component, a convention, a table
several apps use)? Check the docs of the *other* apps that use it —
`docs/claude/mini-apps.md` § "How the apps connect" says which.

## 3 · Marina's material

- **SessionTest** — run
  `git diff --stat <scope> -- app/templates app/static app/web*.py` .
  Anything there = something she can click → write
  `docs/marina_notes/SessionTest_<date>.html` (mirror the existing files'
  format: numbered colored boxes, checkbox per step, `expect` spans,
  localStorage ticks with a `st<MMDD>-` key prefix). Nothing there = say
  "no SessionTest — no screen changed" in the report instead.
- **MarinaCheckSoon** — every decision made on her behalf this session
  becomes a dated entry in `docs/marina_notes/MarinaCheckSoon.html`,
  phrased as a question with a checkbox (append a
  `<h2 class="date">Added <date></h2>` section before the `<script>`).
- **build_plan.md** — mark done what got built, and MOVE finished sections
  to `docs/archive/` — **when something is added, something goes**
  [USER 2026-09-01].

## 4 · Session summary — the WHY, for the record

Write `docs/archive/session_<date>_<topic>.md` (existing naming pattern):

- **What changed** — a few lines, with commit hashes
- **Decisions and WHY** — each decision with its reason
- **Considered and rejected** — the roads not taken and why; this is the
  part that exists nowhere else (commits only record what WAS built)
- **Open threads** — what the next session should know

Archive rule applies: written once, never updated, never quoted as current.

## 5 · Promote lessons (story → rule → test)

Anything this session that should not have to be relearned?

- technical → `docs/lessons_learned.md` (what happened · what it cost ·
  what we do now · where the rule lives)
- about how we collaborate → `docs/ways_of_working.md`
- a lesson that keeps recurring → a rule in `docs/coding_guidelines.md`;
  a rule a machine can check → a test (say so, it goes into review round 2)

## 6 · Ship and report

Commit (message says wrap-up), push, verify `origin/master == master`.
Then tell Marina, briefly: what this session shipped, what the wrap-up
added, what is open, and which MarinaCheckSoon questions wait for her.
