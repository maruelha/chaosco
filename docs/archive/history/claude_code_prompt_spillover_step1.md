# Spillover — Step 1: Parse the Core South Spillover tab and print

## Context
This extends the existing Test Coordination Tool. The Defects vertical is already built and is
the template. The architecture principles in the project handoff MUST be respected — especially:

- **Each new tab = a new importer + a new table.** Do NOT modify the defects importer or tables.
- **Never modify the source Excel file.** Read-only.
- **Storage layer separation.** All DB access goes through `database.py`. (Not relevant yet in
  Step 1, but keep parsing logic free of SQL.)
- **Imported data vs authored data never mix.** (Relevant in Step 2.)

This step ONLY parses the new tab and prints to screen. No database writes yet.

## What to build

A new importer module `spillover_importer.py` (sibling to the defects importer; do not touch the
defects importer). It parses the **Core South Spillover** tab of the same Excel file the defects
importer already locates (`DTC_UAT_testtracking_ROE.xlsx`). Reuse the existing file-finding logic
that the defects pipeline already has — do not reimplement it. Just point it at a different sheet.

### Config-driven sheet name
The tab name must be configurable, exactly like `defects_sheet_name`. Add a new key
`spillover_sheet_name` (default value: the real tab name — ask if unknown; assume
`Core South Spillover` until told otherwise) to the same config file the defects sheet name lives in.

### Columns to parse (map messy headers → clean field names)
The Core South Spillover tab has these columns. Map each source header to the clean field name:

| Source column (header in Excel) | Clean field name | Notes |
|---|---|---|
| Type            | `type`          | Values: `Defect`, `Testcase Solman`, `Testcase NotSolman` |
| Area            | `area`          | Values: `ECOM`, `RETAIL`, `OMNI` |
| Status          | `status`        | Free status text (see status note below) |
| Assigned to     | `assigned_to`   | |
| ID              | `external_id`   | **Can be zero or blank. NOT a unique key. Plain field only.** |
| Name            | `name`          | Part of the match key (Step 2) |
| Order numbers   | `order_numbers` | Raw text; may hold multiple numbers. Do not normalize. |
| Country         | `country`       | Part of the match key (Step 2) |
| content         | `content`       | |
| Comment         | `comment`       | Raw imported comment. (Authored comment history is separate — Step 2.) |

Confirm the exact header strings against the real file and adapt the mapping if they differ
slightly (whitespace, casing). Print a warning for any expected column you cannot find, and for
any unexpected extra column present in the tab.

### Excel row number
Capture the TRUE Excel row number per row (header = row 1, first data row = row 2), same as the
defects importer does. Store it as `excel_row`. This is for human cross-reference only and is
**never** used as an identity key.

### Row handling rules (mirror defects behavior)
- Fully blank rows: ignore silently.
- A row that has content but is otherwise unusable for the match key (blank `name`): keep it for
  printing in this step, but mark it clearly in the output as "would be skipped — blank name."
  (Actual skip-logging happens in Step 2.)
- Do NOT filter by status in the importer. Status-based hiding (Passed / Passed pending Solman /
  Dropped) is a VIEW concern, handled later in the UI — not in import. The importer brings in
  everything.

### Output for this step
Print to screen, in a readable table or per-row block:
- The resolved sheet name and the file path used.
- Total rows found, rows parsed, rows that would be skipped (with reason).
- Each parsed row's clean fields, including `excel_row`.

## Acceptance
- New module, new sheet config key. Defects importer and tables untouched.
- Running it prints the parsed Spillover rows. No DB changes. Source file not modified.
