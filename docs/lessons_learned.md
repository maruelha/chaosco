# Lessons Learned — technical

**Job:** the STORIES behind the rules — what broke, what it cost, what we
do now. Rules themselves live elsewhere and are pointed at, never
restated: the non-negotiables in `CLAUDE.md`, review rules in
`coding_guidelines.md`. Collaboration lessons live in
`ways_of_working.md`; UAT/testing-domain lessons live in the app itself
(`/test-learnings`). New entries come from the `/wrap-up` skill's
promote-lessons step (story → rule → test). Newest first.

---

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
