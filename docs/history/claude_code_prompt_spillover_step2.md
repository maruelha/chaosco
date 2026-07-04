# Spillover — Step 2: SQLite storage, match-key upsert, and authored annotations table

## Context
Builds on Step 1. Now we persist the parsed Core South Spillover rows and create the authored
working-fields table. Respect all architecture principles, especially:

- **Imported data vs authored data are separate and NEVER mix.** The import writes ONLY to the
  imported `spillover` table. It NEVER writes to `spillover_annotations`.
- **Never delete imported entities.** A spillover row that disappears from the export stays in the
  DB; its `last_seen` just stops advancing.
- **Storage layer separation.** ALL SQL lives in `database.py`. The importer calls storage methods.

## Tables to create

### `spillover` — imported, current-state, upserted each import, never deleted
- `spillover_id` INTEGER PRIMARY KEY AUTOINCREMENT — surrogate key, the clean PK.
- `type` TEXT — Defect / Testcase Solman / Testcase NotSolman.
- `name` TEXT.
- `country` TEXT.
- `area` TEXT — ECOM / RETAIL / OMNI.
- `status` TEXT.
- `assigned_to` TEXT.
- `external_id` TEXT — the source "ID"; **can be zero or blank; plain field; NOT unique.**
- `order_numbers` TEXT — raw.
- `content` TEXT.
- `comment` TEXT — raw imported comment.
- `excel_row` INTEGER — refreshed each import; never an identity key.
- `first_seen` TEXT/DATE — set once on insert.
- `last_seen` TEXT/DATE — advanced on every import.

### Match key (identity across imports) — NOT the primary key
The natural identity is the composite **(type, name, country)**. This is how the upsert decides
"same row as before" vs "new row." The surrogate `spillover_id` is the PK that authored data
points to, so authored data survives even if status/area/content/comment change.

Implementation: add a UNIQUE index on `(type, name, country)` (normalize for matching:
trim whitespace, treat case/spacing consistently — but STORE the original values). Upsert logic:
- If a row matching (type, name, country) exists: UPDATE its mutable fields
  (area, status, assigned_to, external_id, order_numbers, content, comment, excel_row),
  advance `last_seen`. Leave `first_seen` and `spillover_id` untouched.
- If no match: INSERT new, set `first_seen` and `last_seen` to today.
- Never delete.

### Skip-logging (mirror defects)
- Fully blank rows: ignore silently.
- Rows with content but blank `name` (cannot form a match key): SKIP and log to a timestamped
  skip-log CSV (same mechanism/location as the defects skip-log), with the reason and the
  `excel_row`. This is also how renamed rows surface, so make the reason clear.

## `spillover_annotations` — authored, NEVER written by import
ONE row per spillover item. Created on first save (upsert from the UI later). Survives every import.
- `spillover_id` INTEGER PRIMARY KEY — FK → `spillover(spillover_id)`.
- `importance_for_signoff` TEXT — authored field (a).
- `next_step` TEXT — authored field (b).
- `comment_history` TEXT — authored field (c). ONE free text area, user-authored from scratch
  (import does NOT seed it). Stored and shown verbatim as the user saved it.
- `updated_at` TEXT/DATE.

Note: comment history is deliberately NOT seeded from the imported `comment` column — the user
authors it. The raw imported `comment` remains available read-only on the `spillover` row. to add to `database.py`
- `upsert_spillover_rows(rows)` — the match-key upsert above; returns counts (inserted, updated,
  skipped) and writes the skip-log.
- `get_spillover(filters)` — for the list view later (status exclusion is applied at the query/UI
  layer, not here — keep this method capable of returning everything, with optional filters).
- `get_spillover_by_id(spillover_id)`.
- `get_spillover_annotation(spillover_id)` / `upsert_spillover_annotation(...)`.

## Acceptance
- Re-running the import on the same file does NOT duplicate rows and does NOT touch annotations.
- Editing a row's status/comment in the source and re-importing UPDATES the existing row (same
  `spillover_id`), and any attached annotation stays attached.
- Blank-name content rows are skipped and logged. Defects tables/importer untouched.
