# Retail — Step 1: Parse the Retail test-cases tab and print

## Context
Extends the existing Test Coordination Tool. Defects and Spillover verticals are already built and
are the templates. Respect all architecture principles, especially:

- **Each new tab = a new importer + a new table.** Do NOT modify the defects or spillover importers
  or tables.
- **Never modify the source Excel file.** Read-only.
- Keep parsing logic free of SQL (storage comes in Step 2).

This step ONLY parses the Retail test-cases tab and prints to screen. No database writes yet.

This is a SIMPLIFIED, retail-only module. There is NO ECOM union table and NO OMNI handling — just
the retail columns. There is NO status-history snapshot (explicitly out of scope / MVP+).

## What to build

A new importer module `retail_importer.py` (sibling to the defects and spillover importers; do not
touch them). It parses the **Retail test-cases** tab of the same Excel file the pipeline already
locates (`DTC_UAT_testtracking_ROE.xlsx`). Reuse the existing file-finding logic — do not
reimplement it. Point it at the configurable retail sheet.

### Config-driven sheet name
Add a configurable sheet name (e.g. `retail_sheet_name`, default `Retail` — confirm the real tab
name against the file) in the same config file the other sheet names live in.

### Columns to parse (map messy headers → clean field names)
Map each source header to the clean field name. Confirm exact header strings against the real file
and adapt for whitespace/casing; warn on any expected column not found and any unexpected extra
column.

| Source column (Excel header)                 | Clean field name        | Notes |
|-----------------------------------------------|-------------------------|-------|
| Test Case                                     | `test_case_id`          | Part of match key (Step 2). NOT unique alone. |
| Country                                       | `country`               | Part of match key (Step 2). |
| (test case name column)                       | `testcase_name`         | |
| (scenario column)                             | `testcase_scenario`     | Used as a filter in the UI. |
| Status                                        | `status`                | |
| Assigned to                                   | `assigned_to`           | |
| Key user responsible                          | `key_user_responsible`  | |
| Evidence in SharePoint                        | `evidence_in_sharepoint`| |
| Sales file                                    | `sales_file`            | |
| Execution started                             | `execution_started`     | |
| Execution completed                           | `execution_completed`   | |
| Order number                                  | `order_number`          | nullable; current order number (searched in UI) |
| OLD Order numbers/Transaction numbers         | `old_order_numbers`     | raw text, nullable |
| Defect ID if applicable                       | `defect_id_ref`         | raw text, nullable (searched in UI) |
| S4 Sales Order                                | `s4_sales_order`        | |
| S4 Billing Documents                          | `s4_billing_documents`  | (searched in UI) |
| S4 Journal/Invoice entry                      | `s4_journal_invoice_entry` | |
| Delivery note                                 | `delivery_note`         | |
| Comment                                       | `comment`               | raw imported comment (authored comment history is separate, Step 2) |
| Reason for pass with reservation              | `reason_for_pass_with_reservation` | |

(The MD also references a "Concatenate unique ID calculated" column — do NOT use it as a key; the
component parts test_case_id + country are the match key. Ignore or store as raw only if present.)

### Excel row number
Capture the TRUE Excel row number per row (header = row 1, first data row = row 2). Store as
`excel_row`. Human cross-reference only — never an identity key.

### Row handling rules
- Fully blank rows: ignore silently.
- A row with content but missing match-key fields (blank `test_case_id` or blank `country`): keep
  for printing, mark clearly as "would be skipped — incomplete key." (Real skip-logging in Step 2.)
- Do NOT filter by status. Retail shows everything; there is no status hiding in this module.

### Output for this step
Print to screen: resolved sheet name + file path; total rows found / parsed / would-skip (with
reason); each parsed row's clean fields including `excel_row`.

## Acceptance
- New module + new sheet config key. Defects and spillover importers/tables untouched.
- Running it prints the parsed Retail rows. No DB changes. Source file not modified.
- Verify the column mapping on screen against the real tab BEFORE moving to Step 2.
