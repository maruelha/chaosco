# Session 2026-09-01 (c) — Sustain Call-outs

Archived session summary — written once, never updated, not a source of
truth. Current docs: `docs/claude/sustain.md`,
`docs/claude/components/next-steps.md`, `docs/claude/components/notes.md`,
`docs/screens.html`, `docs/database_schema.html`.

## What changed

- `22b207f` — **Storage layer.** New `app/db/sustain_callouts.py` →
  `sustain_callouts` table: channel (retail/ecom/both), fixed type list,
  topic, responsible, status (open/in_progress/closed), date_captured.
  Own table, never touched by the importer. `list_open_for_channel`
  folds `channel='both'` into each stream's filtered list up front, so
  step 4 needed no extra logic later.
- `1d93847` — **Card-page section + cycling status chip.** "Call-outs"
  section above the imported-days table on `/sustain/`: add-row form,
  list with a one-click cycling status chip (open → in_progress →
  closed → open, saves instantly — SalesXLS chip pattern), inline edit,
  delete, show/hide-closed toggle.
- `c9a81c2` — **Next step + notes wiring.** `next_step` added directly
  on `sustain_callouts` (additive `ALTER TABLE`, blocker pattern):
  inline onblur save + ↻ archive / 🕘 history through the generic
  `/next-steps` component. Notes reuse the generic `/n/sustain_callout/…`
  JSON routes (list-only entity, no detail page) with an expandable
  per-row widget (todo_list.html pattern).
- `fe4607d` — **Management summary block.** Each stream's section on
  `/sustain/summary` gained a Call-outs table (open/in-progress items
  for that channel) right below the stat cards; `channel='both'` items
  render in BOTH the Retail and eCom sections.
- `03a9479` — mid-build docs pass (mini-apps.md, sustain.md Tests line
  and Change log).
- Wrap-up commit: coherence fixes to the two shared component docs (see
  below), SessionTest_2026-09-01_c, MarinaCheckSoon entries, this
  summary.

Tests 815 → 839 (24 new: 9 storage, 15 web; every step landed green
before the next began).

## Decisions and WHY

- **Own table, not an annotation on an existing one** — call-outs are
  Marina's independent monitoring log, not a comment thread on an
  imported row (unlike `sustain_issue_annotations`, which does hang off
  an imported issue). Keeps "importers never touch authored data"
  literally true without a special case.
- **Cycling status chip over a dropdown** [USER: pattern from the
  SalesXLS marker] — one click per state change for a list reviewed
  daily; states/colors/order live once, server decides the next state
  (no value posted, unlike SalesXLS which posts an explicit value) since
  there's no reason a client would need to skip a state.
- **Fixed type list, not config-driven** [USER] — six values (Issue,
  Spotcheck, Observation, MigrIssue, OrgIssue, Question) are stable
  enough that YAML indirection isn't worth it; a new type is a one-line
  code change if it ever comes up.
- **`next_step` lives directly on `sustain_callouts`**, not a separate
  annotations table — call-outs are already 100% authored, so there's no
  imported/authored split to preserve (unlike blockers, which also do
  this, vs. sustain_issues, which needs a separate annotations table
  because the issue itself is imported).
- **Notes as an inline expandable row, not a detail page** — call-outs
  have no detail page (list-only entity in the notes registry, like
  `todo`/`meeting_prep`), so `_notes_section.html` (built for a full
  page) doesn't fit; reused the JSON endpoints with page-local glue,
  same shape as `todo_list.html`.
- **Open call-outs show on every historical day's summary, not just the
  latest** — a call-out is ongoing state, not tied to one day's import;
  restricting it to "latest day only" would hide it the moment a newer
  day is imported even though nothing changed. Flagged in
  MarinaCheckSoon in case it clutters older days in practice.
- **Dashboard badge left as task-count** — changing it to reflect open
  call-outs (or showing both) wasn't asked for; flagged as a question
  rather than decided silently.

## Considered and rejected

- **A detail page per call-out** (mirroring blockers/delegated tickets)
  — rejected: the daily-review use case is a short list glanced at once
  a day, not something that needs its own URL and page. If notes threads
  grow long this may need revisiting (MarinaCheckSoon asks).
- **Reusing `_notes_section.html` directly** — doesn't fit a list row
  without restructuring the table into cards; the todo_list precedent
  already established the inline-widget alternative, so followed it
  instead of inventing a third pattern.
- **A separate `sustain_callout_annotations` table for next_step** (the
  sustain_issue shape) — unnecessary: call-outs have no imported
  counterpart to protect from, so the field lives directly on the row
  (the blocker shape) instead.

## Coherence catches at wrap-up (the additive-edit trap, again)

- `docs/claude/components/next-steps.md`'s "Currently on" list was
  already stale before this session (missing delegated, blocker, smoke,
  sustain_issue) and would have gone one more entry stale with
  sustain_callout added silently — backfilled the whole list.
- `docs/claude/components/notes.md` said "**Never** create a
  module-specific notes table, route set, or **script**" — read
  literally, both `todo_list.html` (pre-existing) and this session's
  `sustain.html` violate that: each renders notes with its own small
  page-local script rather than `static/notes.js`. Documented the
  list-only-entity exception explicitly instead of leaving the doc
  silently contradicted by two modules now.
- `sustain.md`'s Related section didn't link `[[next-steps]]` /
  `[[notes]]` despite the mini app now using both shared components —
  added.

## Open threads

- MarinaCheckSoon questions (2026-09-01, Sustain Call-outs): call-outs
  showing on every historical summary day vs. latest-only; dashboard
  badge unchanged; notes' own small widget vs. a dedicated page.
- SessionTest_2026-09-01_c.html awaits Marina's click-through (needs an
  app restart for the `sustain_callouts` table + `next_step` migration).
- Test-suite runtime observation (unrelated to this feature): two clean
  runs mid-session clocked ~128s, later runs ~54–67s — not chased down;
  worth profiling if it keeps drifting slower.
