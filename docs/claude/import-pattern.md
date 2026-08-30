# The import pattern (shared by every Excel vertical)

**Type:** pattern
**Storage:** one table per tab — see each vertical's own file
**Code:** `app/importer.py` (orchestrator) · `app/archiver.py` · one `*_importer.py` per tab
**Tests:** `tests/test_importers.py`, `tests/test_import_data_checks.py`

## Purpose

The workbook is a shared file that other people edit. chaosco must be able to
re-read it any number of times without ever losing what MARINA wrote, and
without touching the file itself. That is what this pattern guarantees.

## Architecture

**Architecture rule 1: each Excel tab = its own importer + its own SQLite
table.** Import is idempotent (upsert, never delete): `first_seen` is set once,
`last_seen` is updated every run. Importers write ONLY to the imported tables
— NEVER to the `*_annotations` tables, which are user-authored. All parsing is
header-map driven (`_HEADER_MAP` at the top of each importer,
case/whitespace-insensitive).

`app/importer.py` orchestrates: parse → archive (SHA-256 dedup via
`app/archiver.py`) → upsert → skip-log CSV.

| Vertical | Excel tab | Importer | DB module | Table | Annotations | Match key |
|---|---|---|---|---|---|---|
| Defects | "Defects" | `read_defects.py` | `db/defects.py` | `defects` | `defect_annotations` | `defect_id` (TEXT PK) |
| Spillover | "Core South Spillover" | `spillover_importer.py` | `db/spillover.py` | `spillover` | `spillover_annotations` | `excel_row` (stable) |
| Retail | "Retail" | `retail_importer.py` | `db/retail.py` | `retail` | `retail_annotations` | lower(test_case_id) + lower(country) |
| ECOM | "ECOM" | `ecom_importer.py` | `db/ecom.py` | `ecom` | `ecom_annotations` | jira id |
| Manual Retail | "Manual Test Cases \| Retail" | `manual_importer.py` | `db/manual_tests.py` | `manual_retail` | — | test case + country |
| Manual ECOM | "Manual Test Cases \| ECOM" | `manual_importer.py` | `db/manual_tests.py` | `manual_ecom` | — | testcase_scenario ALONE [USER 2026-08-06] |

## Rules & gotchas

- **Header aliases.** A header may appear under more than one spelling across
  workbook versions — map both to the same field (Retail's `testcase_name`
  accepts `Testcase Name` and `Test Case Description` [USER 2026-07-29]). Two
  rules keep aliases safe: `_OUTPUT_FIELDS` is de-duplicated
  (`dict.fromkeys`), and a field already claimed by an earlier header makes
  later aliases count as unmapped — otherwise a workbook carrying BOTH
  spellings renames two columns to the same name and the row loop reads a
  pandas Series instead of a value. **Symptom of a silently dropped name
  column:** every Retail Requirements Board row shows the amber "⏳ expected"
  pill (`[[retail-tracker]]`).
- Blank Excel header cells (pandas "Unnamed: N") are ignored, not counted as
  "unmapped".
- `imports.<vertical>` in `settings.yaml` enables a tab. **The config merge is
  per top-level key** — a local `imports:` block REPLACES the base one, so a
  new tab has to be added in BOTH files.
- Never modify the source Excel. The archiver keeps a dated copy with SHA-256
  dedup; identical files are not stored twice.
- Rows that cannot be keyed go to the skip-log CSV (`output/skiplog/`) and are
  counted on the import screen — never silently dropped.
- The `[[row-validations]]` registry also runs at IMPORT time
  (`importer.data_check_rows`): findings show as a red "⚠ Data checks" block
  per section on the import report. Rows are imported anyway — the block just
  names them.

## Related

`[[defects]]` · `[[spillover]]` · `[[retail]]` · `[[ecom]]` ·
`[[manual-tests]]` · `[[row-validations]]` · `[[report-blocks]]`
