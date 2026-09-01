# Session 2026-09-02 — Call-out notes fix · Blockers fixes · nextInLine · Working-notes pages

Archived session summary — written once, never updated, not a source of
truth. Current docs: `docs/claude/delegated.md`, `docs/claude/sustain.md`,
`docs/claude/components/note-pages.md`, `docs/claude/components/notes.md`,
`docs/screens.html`. (Session ran across the midnight boundary
2026-09-01 → 09-02; the SalesXLS work earlier the same evening has its
own summary, `session_2026-09-01_salesxls_automatch.md`.)

## What changed

- `652bb62` — build_plan: test-inventory idea parked under Round 3
  [USER: a list of every test and what it tests, to judge over-testing].
- `ab6a6f4` — **Sustain call-out notes got the real shared component
  back.** The first build had copied the To-Do quick-add widget (plain
  text, no heading, no attachments); swapped for one `_notes_section.html`
  instance per row. Shared fixes to make that possible: per-entity wrapper
  id (was hardcoded `notes`) and `note_entity=<id>` on note redirects so
  the "saved" banner shows only on the touched instance.
- `db44607` — **Blockers close-shift fixed**: browsers restore form
  values BY POSITION on reload, so ✔ Close made every Team/Next step
  appear one row lower. `autocomplete="off"` + `location.replace` instead
  of `location.reload`. Same commit: closed blockers out of the attach
  picker's pick list (attached ones stay visible/detachable).
- `c65d047` — **Jira-status investigation**: a reproduction test proves
  the refresh flow works end-to-end (resolve in Jira → re-upload →
  status + auto-close), so her machine's data differs; the "as of
  <last_seen>" stamp on the Status column is the built-in diagnostic.
- `1f23fe7` — **nextInLine label rule**: Open/Reopened tickets without
  the label wait in 📦 Backlog; `backlog` became tri-state (NULL = label
  decides) via a one-time table rebuild; manual park/unpark beats the
  label both ways; Management Summary/Overview exclude via `bucket_key`.
- `61d6d8d` — **Working-notes pages**: one registry
  (`app/note_pages.py`) + one generic route/template pair serve every
  Ways-of-Working-style page; WoW migrated in (notes moved, old URLs
  redirect), 💡 Testing Insights added; inbox files into ONE type whose
  search lists every page.
- `389d8a3` — **📝 Meeting Summaries** (Sustainphase card):
  `heading_mode='date'` option on the shared form (date picker only,
  today prefilled), date-sorted notes, client-side keyword filter box on
  all note pages. Built on Sonnet after the plan was settled on Fable
  [USER asked "do we need you fable for this?" — honest answer: no].
- Wrap-up commit: filter scoped to heading+text (button labels matched
  before), notes.md contradiction fixed, SessionTest_2026-09-02,
  MarinaCheckSoon, this summary.

Tests 847 → 873, green throughout.

## Decisions and WHY

- **Blockers shift bug is browser-side, not data-side** — the DB was
  always right. Fix at the restoration mechanism (autocomplete=off +
  fresh navigation), not by rewriting the save logic. Any list page
  combining inline form controls with a row-removing reload has the same
  latent trap (noted in delegated.md).
- **"as of" stamp instead of more guessing** [USER: "the export INCLUDES
  all status values!"] — her observation ruled out my filter theory; the
  reproduction test pins the mechanism green, so the next step is making
  the broken link VISIBLE on her machine rather than theorizing from a
  sandbox with an empty dev DB (two-machines setup).
- **nextInLine lives in bucket logic, not the importer** — the importer
  never writes user-authored fields (architecture rule 1); deriving from
  the labels the import already refreshes gives "it happens on import"
  for free AND keeps the label live (add/remove in Jira moves the ticket
  next upload). Marina picked both recommendations.
- **Tri-state backlog with old 0 → NULL** — the manual flag must beat
  the label in BOTH directions, which needs "no manual decision" as a
  state. Old `backlog=0` rows were almost all side effects of saving
  other fields, so they reset to "label decides"; the cost (an explicit
  pre-rule un-park is forgotten once) is flagged in MarinaCheckSoon.
- **Note pages: registry, not table; buttons, not index** [USER] — she
  will always ask for new pages ("i would always be coming to you with
  that request"), so in-app page creation, a dashboard card and an index
  were all declined. Separate pages for the user, one mechanism
  underneath.
- **`heading_mode` reads off the entity's ROW, not the NoteEntity** —
  the `note_page` registry entry serves many pages with different
  behavior, so a static per-entity-type field could not distinguish
  them; any entity's get_row dict may carry the key (generic).
- **Search without AI** [USER: "the app itself NEVER EVER uses ai"] —
  client-side substring filter over the already-rendered notes; honest
  limitation stated (finds the word, not the meaning); SQLite FTS named
  as the non-AI upgrade path, not built.

## Considered and rejected

- **Import writes the backlog flag** (what the request literally said) —
  rejected with Marina: violates importer/authored separation and
  creates overwrite conflicts with her manual choices on every upload.
- **Per-page dropdown options in the inbox picker** for note pages —
  rejected: one type + search listing every page needs zero per-page
  wiring; also deleted the delegated_wow JS singleton special case.
- **An index page / dashboard card for note pages** — offered, declined
  [USER], buttons live where she works instead.
- **TXT export for Meeting Summaries** — parked by Marina until she
  knows how she wants to use it.
- **Global 🔍 for meeting summaries** — declined; on-page filter is
  enough.
- **FTS5 for the topic search** — not attempted; LIKE-scale filtering is
  adequate at one-summary-per-day scale, and FTS5 is SQLite-only
  (portable-SQL rule) while Postgres has a different FTS.

## Coherence catches at wrap-up (the additive-edit trap, again)

- `components/notes.md` still listed `sustain_callout` among the
  lightweight-widget entities — the very thing this session's first fix
  removed. Rewrote the bullet and labeled the quick-add widget as the
  LESSER pattern so it doesn't get copied again (that copy caused the
  bug).
- The keyword filter matched the whole note tile's textContent —
  including "Edit"/"Delete"/"Add screenshot" button labels, so searching
  "edit" matched every note. Scoped to heading + text.
- Docs-structure test caught `/delegated/wow[/download]` shorthand not
  literally containing the redirect URL — written out. The enforcement
  from Part 0 is earning its keep.

## Open threads

- **Blockers Jira status** — waiting on Marina reading the "as of" stamp
  after her next real upload (MarinaCheckSoon has the decision tree).
- nextInLine first pull will visibly move unlabeled open tickets to
  Backlog — expected, flagged in the SessionTest.
- Parked: TXT export (Meeting Summaries), Excel/ECOM join scope,
  SalesXLS substring-risk review, test-inventory idea (Round 3).
- SessionTest_2026-09-02.html awaits the click-through (needs git pull +
  restart — two startup migrations).
