# Missing Test Cases (`/missing-tests/`) — deep dive

Built 2026-08-30. **Why it exists:** the same gap was written down in two
places and drifted apart —

| where | what it was |
|---|---|
| Retail status report | config `retail_missing_categories` in `settings.yaml` ("Manual test cases", "100% voucher cases", "Event store"), rendered as bullets in the report header |
| Retail Requirements Board | table `tracker_missing_tests` (free text, no detail), the red ⚠ list at the top |

Now there is **one list** (`missing_test_cases`) and both places render it
[USER 2026-08-30]. The mini app is reachable from Retail (`/retail`), the
Retail status report and the Requirements Board.

## Structure of the page

1. **Missing test cases** — the authored list. Per entry a `title` (the
   one-liner both reports show) and optional `details` (the longer note).
   Add form on top, inline Edit row, ✕ delete (AJAX, with a confirm that says
   the entry disappears from the report and the board too).
2. **Retrofits — Retail** — read-only mirror of the Retrofits mini app for
   channel `Retail` (which includes `ECOM & Retail` rows — see
   `db/retrofits.list_retrofits`). A retrofit is the usual reason a test case
   is missing. Status is always shown: **Confirmed**, or **Potential** with
   "not confirmed yet" underneath [USER 2026-08-30]. The **test coverage
   note** per retrofit belongs to THIS module (`missing_test_retrofit_notes`)
   because Retrofits has no note field — it blur-saves like every other
   inline field in the app.

## Outputs

- **HTML report** `/missing-tests/report` (own inline CSS, toolbar) and
  `/missing-tests/report/download` (dated standalone snapshot,
  `missing_test_cases_<date>.html`, toolbar dropped via `download=True`).
- **Email mini app**: report key `missing_tests` → "Missing Test Cases
  (Retail)" in `emailer.REPORT_CHOICES`; the attachment is the download route
  as-is (already clean standalone HTML).
- **✉ Email text** button → dialog with plain text + Copy to clipboard.
  Built by `db_missing.email_text(items, retrofits, day)`: numbered missing
  test cases with their details, then every retrofit as
  `- <title> (confirmed|not confirmed, expected …)` with the coverage note
  underneath. Editing in the dialog is not saved (it is a paste helper).

## Who renders the list

| consumer | what it shows |
|---|---|
| `/retail/report` + `/retail/report/download` | titles only, "Missing test cases (on top of total test cases)"; details are a `title=` tooltip on the page. Rendered when the list is non-empty (used to depend on `not_tracked > 0`). |
| `/retail/report/ppt` | titles only — `build_retail_ppt(missing_categories=[…titles])`, unchanged signature |
| `/retail-tracker/board` | title + details in the ⚠ box; the board's quick-add and ✕ now write to **this** module |

## The one-time seed

`db_missing.seed_once(db_path, cfg['retail_missing_categories'])` runs at
startup from `app/web.py`. It writes the config bullets first, then the
`tracker_missing_tests` rows (case-insensitive de-dup), and records
`missing_test_meta['seeded']`. Guarded by that flag and **not** by "is the
table empty" — an emptied list must stay empty across a restart. On the
second computer the same seed runs on first start, so both machines end up
with the same starting entries (git carries the code, not the DB).

`tracker_missing_tests` is legacy from then on: read once, never written.
`retail_missing_categories` stays in `settings.yaml` as the seed only —
editing it there has no effect afterwards.

## Files

```
app/db/missing_tests.py        schema, CRUD, retrofit mirror + notes, seed, email text
app/web_missing_tests.py       Blueprint /missing-tests/…
app/templates/missing_tests.html          the page
app/templates/missing_tests_report.html   report + download (download=True)
tests/test_missing_tests.py    storage, seed-once, mirror, email text, routes
```

Style: `.mtc-*` classes at the bottom of `static/style.css`.
