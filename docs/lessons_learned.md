# Lessons Learned — technical

**Job:** the STORIES behind the rules — what broke, what it cost, what we
do now. Rules themselves live elsewhere and are pointed at, never
restated: the non-negotiables in `CLAUDE.md`, review rules in
`coding_guidelines.md`. Collaboration lessons live in
`ways_of_working.md`; UAT/testing-domain lessons live in the app itself
(`/test-learnings`). New entries come from the `/wrap-up` skill's
promote-lessons step (story → rule → test). Newest first.

---

## Browsers restore form values BY POSITION on reload (2026-09-02)

**What happened:** closing a blocker on `/blockers/` made every Team and
Next-step value appear one row lower — Marina reported it as data
corruption ("copied down the line"). The DB was never wrong: the page's
inline form controls were repainted by the browser's form-state
restoration after `location.reload()`, which matches remembered values
to controls by their position in the page — and the closed row's removal
shifted every position by one.
**What it cost:** a corruption-grade bug report and an evening
investigating a save path that was correct all along.
**Now:** inline form controls on list pages carry `autocomplete="off"`,
and a script that removes/reorders rows navigates fresh
(`location.replace`) instead of reloading. Any list page combining
inline controls with a row-removing reload has the same latent trap —
check for it when building one (`blockers.html` is the reference fix).
**Test:** `test_list_page_inline_fields_opt_out_of_browser_restore`
pins the attributes.

## The "lesser pattern" spreads if the docs don't rank the patterns (2026-09-02)

**What happened:** Sustain Call-outs copied `todo_list.html`'s quick-add
notes widget (plain textarea — no heading, no attachments) because it
was the established precedent for list pages; Marina expected the full
notes component she knows from everywhere else ("what you gave me was a
simple text filed"). The 2026-09-01 entry below had even blessed the
deviation as a "named exception" — without saying it is the WORSE of the
two patterns. Meanwhile `delegated_wow` had already proven the full
component works without a detail page.
**What it cost:** a rebuilt feature, plus the shared component needed
multi-instance support (per-entity wrapper id, banner scoping) that
would have been designed in from the start.
**Now:** when two patterns coexist, the component doc RANKS them and
says when the lesser one is acceptable (`components/notes.md`: full
component by default; the quick-add widget only when plain-text-only is
a deliberate choice). An exception that is really a gap gets labeled as
a gap.

## A rule can be true in spirit and wrong in the literal words (2026-09-01)

**What happened:** `components/notes.md` says "never create module-specific
notes... JS." Read literally, two modules break it —
`todo_list.html` (pre-existing) and this session's Sustain Call-outs —
because a list-only entity with no detail page can't use
`_notes_section.html` (built for a full page); both instead call the
SAME generic JSON endpoints from a small page-local script. The doc's
intent (one data layer, one route set) held; its literal words didn't.
**Now:** when a repeated pattern in the code doesn't match a rule's
literal wording, the doc gets the pattern documented as a named
exception (see `components/notes.md`'s "List-only entities" bullet)
instead of either quietly copying the deviation a third time or forcing
a bad fit to satisfy the letter of the rule.

## Audit before freezing a rule into a test (2026-09-01)

**What happened:** two coverage rules that sounded right were WRONG when
run against reality — "every route documented" flagged 179 false
positives (per-row CRUD endpoints that belong in prose), and "a doc lists
all tables of its module" broke on shared schema modules.
**Now:** a rule becomes a test only after an audit run shows what it
actually flags; a test that cries wolf gets deleted, which is worse than
no test. Both rules were reshaped by their own audits (two altitudes; no
orphans) and each carries an explicit exceptions list with reasons.

## A broken settings.json fails SILENTLY (2026-09-01)

**What happened:** while arming a test sentinel, string surgery wrote
unescaped quotes into `.claude/settings.json` — invalid JSON, and a
settings file that does not parse disables EVERYTHING in it (hooks
included) with no error shown.
**Now:** hooks and settings are edited through a JSON parser
(`json.load` / `json.dump`), never by string replacement, and the file is
re-parsed after every write.

## Additive edits create contradicting docs (2026-09-01)

**What happened:** two email docs each said the opposite of themselves —
new prose ("opens with nothing ticked", "groups carry reports + wording")
was bolted on top of old prose ("everything stays ticked", "named
recipient selections") that nobody re-read.
**What it cost:** a full audit-and-repair session across four docs.
**Now:** the wrap-up coherence pass re-reads every *edited section* top to
bottom; facts are frozen by the coverage tests in
`tests/test_docs_structure.py`.

## Hand-typed facts drift; generated facts cannot (2026-09-01)

**What happened:** `email_lists.subject/body` existed in the DB but not on
the schema page; a table card sat in the wrong section; routes were
unlisted. All hand-typed copies of things the code already knew.
**Now:** facts are generated (`docs/docs_map.html` via
`tools/gen_docs_map.py`) or test-enforced (tables, columns, screens,
cards); hand-writing is reserved for meaning. Concept at the top of
`docs/docs_map.html`.

## A workbook's header row is not a fixed address (2026-08-31)

**What happened:** the new GBS Operations checklist dropped one line at
the top, every header moved up a row, and the sustain import would have
failed outright — the importer insisted on row 6.
**Now:** importers *find* the header row by its label ("Task ID"), never
by number; a genuinely changed structure still fails loudly.

## Excel's own summary cells are not truth (2026-08-28/31)

**What happened:** the sustain workbook's summary row is cached formula
results — and the workbook *changed its own formulas* between versions, so
identical data produced different numbers per file version.
**Now:** `db/sustain.py` recomputes ALL statuses from the raw cells and
implements the counting rules itself; the workbook's row 4 is only used to
verify, never trusted.

## Two renderers for "the same" report WILL disagree (2026-08-31)

**What happened:** the emailed Retail report was wrong — the email
attachment was rendered by its own function, which never got the same data
the page got.
**What it cost:** a wrong report reached the outside world.
**Now:** ONE renderer (`emailer.render_retail_html`) serves page download,
email attachment and export snapshot; regression test
`tests/test_retail_report_copies.py`. Rule of thumb: a report that leaves
the app must be rendered by the same code path the screen uses.

## One combined doc for many apps rots (2026-08-30)

**What happened:** `coordination.md` grew to 502 lines covering 20 apps;
nobody could update their slice without scrolling past everyone else's.
**Now:** one file per mini app, one per component, indexed by
`mini-apps.md`, enforced by `tests/test_docs_structure.py`
[USER 2026-08-30: never a combined doc again].

## SQLite convenience syntax is a trap for the Postgres future (2026-08-06)

**What happened:** SQLite is a stepping stone — the plan is a hosted
Postgres (Supabase). `INSERT OR IGNORE/REPLACE`, `COLLATE NOCASE`,
case-insensitive `LIKE` and `datetime('now')` all behave differently or
don't exist there — and `datetime('now')` is UTC while Python writes local
time, so even *within* SQLite two datetime writers disagreed.
**Now:** CLAUDE.md rule 7 (portable SQL, one datetime format,
`isoformat(timespec="seconds")`); the rule nearly got lost once when it
lived only in prompts — which is why it is a numbered rule now.

## PDF export on Windows was a dead end (2026-07)

**What happened:** WeasyPrint needs the GTK stack; it never ran reliably
on this machine.
**What it cost:** repeated setup attempts before the decision.
**Now:** PowerPoint (`python-pptx`) is THE export format; browser
Print → Save as PDF is the manual fallback. Retired for good — do not
suggest reinstating PDF generation.
