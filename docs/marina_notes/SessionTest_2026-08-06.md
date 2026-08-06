# Session Test — 2026-08-06 — Known Production Issues

Click-through checklist. Filled in as each build step lands; check items
off in the running app at `http://127.0.0.1:8010`.

> **Before clicking through:** restart the app once (`run_web.bat`) so the
> new columns/tables exist. No data migration is destructive — existing
> Known Prod Defects rows survive as-is, just with the new fields empty.

## ① Schema + detail form new fields

- [ ] Open an existing entry → **Channel** (ECOM/Retail), **Type** (Defect/
      Limitation/Risk/Accepted Defect), **Scenario** dropdown, **Sub-case**,
      **How to detect** all appear and save correctly.
- [ ] An entry with an old free-text scenario value not in the fixed list
      still shows that value (as a "(current)" option) — nothing lost.

## ② List page

- [ ] Page title/heading now say **Known Production Issues**.
- [ ] Columns, in order: Channel · Scenario · Short Description · Biz
      Impact · How to handle · Confluence.
- [ ] Channel filter and Scenario filter both work.
- [ ] Confluence link at the top of the page opens the TRAN space page.
- [ ] An entry with notes shows "Edit (N)" with the right count.

## ③ Inbox routing

- [ ] Inbox → filing picker → "Known Prod Issue" is a Type option.
- [ ] Searching finds an existing entry by scenario / short description /
      technical key.
- [ ] Filing moves the note; it appears in that entry's notes section.

## ④ Download + email

- [ ] "⬇ Download HTML" on the list page produces a clean, self-contained
      snapshot (no buttons/forms, filters hidden).
- [ ] "✉ Send via email" reaches the Email Reports page with "Known
      Production Issues" pre-ticked; sending includes it as an attachment.

## No clicking needed

- Full test suite green after every step (confirmed in-session; final
  339 tests, 10 new in `tests/test_prod_defects.py`).
- Every item above was also verified programmatically against a fresh
  temp DB during the build (new fields round-trip, legacy scenario
  preserved, filters, note count, inbox search+file+refuse, download
  snapshot, email pre-tick, attachment content) — the boxes above are for
  YOUR visual/UX check in the real running app, not a "does it work at
  all" check.
- Docs updated: `screens.html`, `database_schema.html`,
  `docs/claude/coordination.md`.
