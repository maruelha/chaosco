# Session 2026-09-03 — Jira "Blocks" auto-attach · Sales XLS row 2 + reverse check · Links per mini app · Blockers back-to-row

Archived session summary — written once, never updated, not a source of
truth. Current docs: `docs/claude/delegated.md`, `docs/claude/links.md`,
`docs/claude/components/jira-store.md`, `docs/claude/mini-apps.md`,
`docs/screens.html`, `docs/database_schema.html`, `CLAUDE.md` (file map),
`docs/coding_guidelines.md` § Naming, `docs/lessons_learned.md`.
Click-through: `docs/marina_notes/SessionTest_2026-09-03.html`.

## What changed

- `427efbb` — **Sales XLS**: the column is "Solman ID" (space); header
  match ignores case and spaces.
- `a8d5415` / `3bd8b01` / `b1cbbd9` — **Auto-attach blockers from the
  export's "Blocks" issue links**, planned in chat and built in four
  verified steps: parser (`issue["blocks"]`, `blocked_pairs`), storage
  (`blocker_links.source` manual|jira, `jira_missing_since`), import
  (`_attach_from_blocks_links`: attach to stories, never overwrite or
  delete, stamp links the export does not confirm), UI (⚠ amber chip on
  board/detail/picker/report + the upload message's list).
- `24057d4` — **Sales XLS**: the header ROW is located (real file: empty
  row 1); "Delegated testing = yes but not on the board" reverse check,
  stored one-row (`delegated_sales_xls_check`), amber section on the
  board.
- `00b1391` — **Links per mini app**: `app/mini_apps.py` registry (first
  code list of mini apps: delegated, sustain), `link_apps` table, form
  checkboxes + list filter/chips on the Links card, ONE global 🔗 dialog
  in `base.html` with open/copy/Copy all, `ui.app_links_button` on the two
  boards.
- `801a3ac` — **Blockers**: detail page returns to its row (`#blk-<id>`,
  `tr:target` tint); list keeps scroll across `blkRefresh()`.

Suite: 906 → 913 tests, green at every step (one red full run in between,
see lessons).

## Decisions and WHY

- **Only the "Blocks" link type, both directions.** Marina's real
  `<issuelinks>` block confirmed the shape; "Cloners" sits next to it and
  must be ignored. Reading inward AND outward means a pair is found even
  when only one side is in the export.
- **Never overwrite, never delete; stamp instead.** Her rule verbatim:
  "if a blocker is already there that is NOT referenced in the xml - it
  should not overwrite - but comment on it". The stamp is set once and
  cleared when a later export confirms the pair, so the "since" date is
  honest. A blocker absent from the export gets no verdict — the file
  cannot say anything about it.
- **Blocked section only, no reverse marker** — her calls: "defects stay
  connected to ticket even after they are closed. no hint"; "we do not
  need to test that jira linking is working properly".
- **Header row located, not fixed** — she does not own the sales
  workbook; same idea as the sustain importer.
- **Reverse-check result stored, not flashed.** A flash message cannot
  hold a list; a one-row table survives restarts and the board shows it
  until the next upload.
- **Links per app: dialog over page.** She was torn; the argument that
  decided it: a two-second open/copy action must not leave the board.
  Editing stays on the Links card.
- **A mini-app registry in code** (`app/mini_apps.py`), Flask-free like
  `note_pages.py` — the first code list of mini apps; two entries to
  start, on her instruction.
- **Not merged with the Teams-chat dialog** — component question asked
  and answered: different registries, different keys, inline-register
  logic only chats need. Noted as the pair to generalize if a third
  "attach registry rows to X" dialog appears.
- **Copy all = names as links** (HTML flavor) + "• name — url" (plain).
  Same technique as the delegated Teams lists.

## Considered and rejected

- **Storing issue links in the jira tables** — not needed; the pairs are
  consumed at import time only. Keeps the shared store untouched.
- **Auto-detaching links Jira dropped** — violates her never-overwrite
  rule; the stamp covers the case.
- **A page instead of a dialog for the app links** — see above.
- **Buttons on all ~25 apps** — offered, declined: two to start.
- **Merging the links dialog into the Teams-chat dialog** — see above.
- **Back-to-referrer for the blocker detail** — not asked; noted in
  MarinaCheckSoon.

## Open threads

- Marina to run her real Jira export and sales workbook through the two
  uploads (SessionTest boxes 1–2) — the ⚠ list and the missing-ID list
  depend on real data.
- MarinaCheckSoon 2026-09-03: yes-values for "Delegated testing",
  backlog in the reverse-check scope, ⚠ on the status report, no-verdict
  rule, non-story links skipped, dialog in the base layout, wording,
  blocker back-target.
- Review round 2 candidate: a test that fails on duplicate public
  function names across `app/db/` (the facade star-imports everything).
