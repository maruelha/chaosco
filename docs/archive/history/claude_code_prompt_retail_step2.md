# Retail — Step 2: SQLite storage, match-key upsert, annotations, and config-gated integration

## Context
Builds on Step 1. Persist the parsed Retail rows, create the authored annotations table, and wire
the importer into the existing config-gated import run. Respect all principles, especially:

- **Imported data vs authored data NEVER mix.** Import writes ONLY to `retail`. NEVER to
  `retail_annotations`.
- **Never delete imported entities.** A row that disappears from the export stays; `last_seen`
  stops advancing.
- **Storage layer separation.** ALL SQL lives in `database.py`. The importer calls storage methods.

No status-history snapshot — out of scope.

## Tables to create

### `retail` — imported, current-state, upserted each import, never deleted
- `retail_id` INTEGER PRIMARY KEY AUTOINCREMENT — surrogate technical PK; authored data points here.
- Match-key columns: `test_case_id` TEXT, `country` TEXT.
- Other imported fields (from Step 1 mapping): `testcase_name`, `testcase_scenario`, `status`,
  `assigned_to`, `key_user_responsible`, `evidence_in_sharepoint`, `sales_file`,
  `execution_started`, `execution_completed`, `order_number` (nullable), `old_order_numbers`
  (nullable), `defect_id_ref` (nullable), `s4_sales_order`, `s4_billing_documents`,
  `s4_journal_invoice_entry`, `delivery_note`, `comment`, `reason_for_pass_with_reservation`.
- `excel_row` INTEGER — refreshed each import; never an identity key.
- `first_seen`, `last_seen`.

### Match key (identity across imports) — NOT the primary key
Natural identity is composite **(test_case_id, country)**. Add a UNIQUE index on
(test_case_id, country) (normalize for matching: trim/whitespace/casing consistently, but STORE
originals). Upsert:
- Match exists → UPDATE mutable fields + advance `last_seen`; leave `first_seen` and `retail_id`.
- No match → INSERT, set `first_seen` and `last_seen` to today.
- Never delete.

Using a surrogate PK (not the composite directly) keeps authored data attached even if a
test_case_id or country is corrected in the source over time.

### Skip-logging (mirror defects/spillover)
- Fully blank rows: ignore silently.
- Rows with content but blank `test_case_id` or blank `country` (no valid match key): SKIP and log
  to the timestamped skip-log CSV (same mechanism as the other importers), with reason + `excel_row`.

### `retail_annotations` — authored, NEVER written by import
ONE row per retail item. Created on first save (upsert from UI). Survives every import.
- `retail_id` INTEGER PRIMARY KEY — FK → `retail(retail_id)`.
- `next_step` TEXT — authored.
- `comment_history` TEXT — authored, ONE free text area, user-authored from scratch (NOT seeded
  from the imported `comment`). Shown/saved verbatim.
- `updated_at`.

(Note: NO importance-for-sign-off field for retail — deliberately different from spillover.)

## Storage methods to add to `database.py`
- `upsert_retail_rows(rows)` — match-key upsert; returns (inserted, updated, skipped); writes skip-log.
- `get_retail(filters, search)` — supports the UI filters and search (see Step 3): filter by
  status / assigned_to / country / testcase_scenario; substring search on `defect_id_ref`,
  `order_number`, `s4_billing_documents`. No status hiding.
- `get_retail_by_id(retail_id)`.
- `get_retail_annotation(retail_id)` / `upsert_retail_annotation(retail_id, next_step, comment_history)`.

## Config-gated integration into the import run
Add retail to the existing `imports:` config section (from the spillover Step 3 work) so it runs in
the same import click and can be independently enabled/disabled:

```yaml
imports:
  defects:   { enabled: true, sheet_name: "Defects" }
  spillover: { enabled: true, sheet_name: "Core South Spillover" }
  retail:    { enabled: true, sheet_name: "Retail" }
```

The run iterates enabled importers; the inline result summary now also reports retail counts
(new / updated / skipped, or "disabled"). File is located + archived ONCE (existing logic); all
enabled importers read the same archived copy.

## Acceptance
- Re-running import on the same file does NOT duplicate retail rows and does NOT touch annotations.
- Editing a row's status/comment in the source and re-importing UPDATES the existing row (same
  `retail_id`); attached annotation stays attached.
- Incomplete-key rows skipped + logged. `retail.enabled: false` removes it from the run with no
  code change, leaving data intact. Defects/spillover untouched.
