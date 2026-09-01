# Session 2026-09-01 — the documentation concept + cleanup round 1

The first session summary written by the new `/wrap-up` step. Archive rule
applies: frozen once written; the live docs are the truth.

## What changed (commits c280bdd..d5d6cbc + this wrap-up)

Morning: audited the email-page work after the previous session's PowerShell
crash — everything was pushed, but the docs had fact-gaps and two
self-contradictions (c280bdd, 4a06f30). That repair session became the
evidence for the day's real work: a documentation concept and cleanup
round 1, all six steps (0e90f37, fdd00df, a61107b, 5d85e1b, 9fa6f5b,
28b1d24), plus the round-3 notes (d5d6cbc).

The concept (top of `docs/docs_map.html`): every doc has ONE job · facts
are generated or tested, meaning is hand-written · story → rule → test.

## Decisions and WHY

- **Facts vs meaning is the axis.** All of the morning's doc bugs were
  hand-typed FACTS (columns, routes, defaults); nobody got the meaning
  wrong. Growth data sealed it: architecture.html stayed flat for two
  months (instance-free) while screens/database_schema/build_plan grew
  55%/120%/10× — per-instance, hand-typed docs grow without bound.
- **Tests ride the existing "suite green before commit" rule** because the
  doc rules that had survived in this project were exactly the ones
  `test_docs_structure.py` already enforced.
- **docs_map.html is generated** so the doc-of-docs cannot itself drift;
  the hand-written job lines live once, in the generator's registry.
- **dashboard_cards = the menu** ("what is this FOR, nothing more"
  [USER]) — Marina could no longer tell it apart from screens.html, and
  that confusion was itself the drift: the menu had grown manual entries.
- **build_plan one-in-one-out** [USER: "when something is added, something
  goes"] — it had become a history book (10× growth) with the to-do list
  buried; 17 finished sections moved verbatim to the archive, verified
  line-by-line (only the old "Last updated" stamp exists in neither file).
- **The close-the-window problem is solved by a next-session check**, not
  at close time — nothing can fire when a window closes; a forgotten
  wrap-up now costs one day, never more.
- **Session summaries carry the rejected alternatives** [USER, via her
  tutor's lessons-learned suggestion] because commits only record what WAS
  built.
- **PK rule** [USER]: every table gets a technical primary key — 68/70
  comply; the two email join tables are round-2 work.

## Considered and REJECTED (the part that exists nowhere else)

- **Splitting screens.html like coordination.md** — recommended by an
  earlier model, overturned: coordination.md was Claude-facing (monolith
  costs context per task); screens.html is a browser reference with a TOC,
  and Marina declared it "the ONE screen doc" on 2026-08-30. Its problem
  was hand-copied facts, not size.
- **"Every route must be documented" at route granularity** — the audit
  flagged 179 of 300 routes, almost all per-row CRUD endpoints the docs
  rightly cover as prose. A test that cries wolf gets deleted. Final rule:
  pages literally + namespaces anywhere (1 real flag, a .json helper).
- **"A doc lists ALL tables of the module it names"** — broke on shared
  schema modules (core.py: 28 tables). Inverted to "no orphan tables";
  `defect_notes` is the single named legacy exception.
- **A Stop hook for the wrap-up reminder** — fires on every turn; pure
  noise. PreToolUse-on-commit + SessionStart carry the job instead.
- **Hand-writing the docs index** — it would be drift victim #48.
- **Generating database_schema.html / screens.html from code** — deferred,
  not rejected: a rewrite of docs Marina likes reading; tests freeze the
  facts for now. Round 3 notes the md→html generator idea as the clean
  path in.
- **Writing coding guidelines in advance** — guidelines invented ahead of
  reviews are guesses; the file is a skeleton (PK rule only) and gets
  filled from real round-2 findings.
- **A separate concept document** — the concept lives at the top of the
  generated docs_map instead; a standalone concept doc would drift.

## Lessons promoted

To `lessons_learned.md` this session: "audit before freezing a rule into a
test" and "a broken settings.json fails silently — edit hooks through a
JSON parser" (both added at wrap-up), on top of the 8 seeds.

## Open threads

- **Round 2** (build_plan Part 0): full code review; findings fill
  `coding_guidelines.md`; greppable guidelines become tests (incl. the
  technical-PK scan); fix `email_list_members` / `email_list_reports` PKs;
  review-after-every-build joins the routine.
- **Round 3** (noted, not planned): slim CLAUDE.md (caution: the seven
  rules earn their always-loaded cost — the file map is the bulk);
  markdown sources with generated HTML.
- **MarinaCheckSoon "Added 2026-09-01 (docs cleanup round 1)"**: four
  judgment calls awaiting her sign-off (route-test altitude, orphan rule,
  commit-gate cost, menu wording) — plus the older open sections.
- The email page's own checklist (`SessionTest_2026-09-01.html`) is still
  unticked — it covers the PREVIOUS session's four email changes.
