# Retail — Step 3: List view with filters, search, and annotation popups

## Context
Builds on Steps 1–2. Adds the web UI for the Retail module (FastAPI, server-rendered HTML, local
browser). Reuse existing layout/styles and the spillover UI patterns. Web layer calls `database.py`
methods, never writes SQL directly.

There is **no separate detail page** — the list view IS the whole interface, like spillover.

## Dashboard
Add a "Retail" button to the existing dashboard action grid (alongside Defects and Core South
Spillover).

## List view (`/retail`)
A single list of all retail test-case items. This is the entire retail UI.

### No status hiding
Show ALL rows regardless of status. There is NO passed/dropped hiding and NO show-passed toggle.
(This is the key difference from spillover.)

### Columns shown (imported, read-only)
A sensible selection of: test_case_id, country, testcase_name, testcase_scenario, status,
assigned_to, key_user_responsible, order_number, defect_id_ref, s4_billing_documents. Keep the
table readable — long fields (comment, evidence) can be previews or omitted from the table and seen
on demand; use judgment consistent with the spillover list.

### Authored field shown inline (editable)
- **Next step** appears as a column showing its current saved value. Clicking opens the annotation
  popup to edit.
(There is NO importance-for-sign-off field for retail.)

### Comment history (NOT a column)
Not shown in the table. Each row has its own button ("Comment history") that opens the
comment-history popup.

### Filters (dropdowns)
- **Status**
- **Assigned to**
- **Country**
- **Testcase Scenario**
Populate options from the data. Filters just filter — no hiding behavior.

### Search boxes (substring / contains match)
Three text inputs, each a case-insensitive "contains" search:
- **Defect ID** → searches `defect_id_ref`
- **Order number / Transaction number** → searches the current `order_number` field only
  (NOT `old_order_numbers`)
- **S4 Billing Document** → searches `s4_billing_documents`

Filters and search combine (AND).

## Popups (edit + save in place)

### Annotation popup (Next step)
Opened by clicking the inline Next step cell. Contains the **Next step** text area. Explicit Save →
`upsert_retail_annotation(retail_id, ...)`. On save, close and reflect the new value in the row.

### Comment history popup
Opened by the row's "Comment history" button. A single editable text area bound to
`comment_history`: shows the current saved value verbatim, editable, explicit Save persists it.
User-authored only — never seeded from or overwritten by the imported `comment`.

All authored fields live in `retail_annotations` and survive every import (principle 1). The raw
imported `comment` is part of the retail row and is not edited here.

## Acceptance
- "Retail" button on dashboard → list view (the entire UI; no detail page).
- All rows shown, no status hiding, no toggle.
- Status / Assigned to / Country / Testcase Scenario filters work; the three substring searches
  work and combine with filters.
- Next step shows inline and edits via popup, saving to the annotation row.
- Comment history opens in its own popup, edits and saves independently, shown verbatim.
- No SQL in the web layer; defects/spillover UI untouched.
