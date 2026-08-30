# Spillover — Step 4: List view with inline annotation editing via popups

## Context
Builds on Steps 1–3. Adds the web UI for Spillover (FastAPI, server-rendered HTML, local browser).
Reuse existing layout/styles. Respect storage separation: the web layer calls `database.py`
methods, never writes SQL directly.

There is **no separate detail page** for spillover (unlike defects). The list view IS the whole
interface: dashboard button → list of all items → edit authored fields via popups on each row.

## Dashboard
Add a "Core South Spillover" button to the existing dashboard action grid (alongside "Defects").

## List view (`/spillover`)
A single list of all spillover items. This is the entire spillover UI.

### Columns shown (imported, read-only)
Type, Area, Status, Name, Country, Assigned to, Order numbers, a short `content` preview, and
`external_id` (the "ID") as a plain column — it can be zero/blank, so do NOT present it as a key
or make it look like an identity link.

### Authored fields shown inline (editable)
Two authored fields appear as columns in the same table row:
- **Importance for sign-off**
- **Next step**
Show their current saved values inline. Clicking opens the annotation popup (below) to edit.

### Comment history (NOT a column)
Comment history is NOT shown in the table. Each row has its own button (e.g. "Comment history")
that opens the comment-history popup (below).

### Default status exclusion
By default, HIDE rows whose `status` is one of: **Passed**, **Passed pending Solman**, **Dropped**.
These stay in the DB — only hidden from the default view. Keep this excluded-status list in the
config file so it can change without code edits.

### Filters (four) + toggle
- Filter by **Area** (ECOM / RETAIL / OMNI).
- Filter by **Type** (Defect / Testcase Solman / Testcase NotSolman).
- Filter by **Status** — the dropdown lists ALL known statuses (including the normally-hidden
  Passed / Passed pending Solman / Dropped). Selecting one of the hidden statuses AUTO-REVEALS it
  (the filter implicitly overrides the hide-by-default for that selection).
- Filter by **Assignee** (`assigned_to`).
- A **"Show passed & dropped"** toggle that reveals the excluded-status rows across the whole list
  (independent of the Status filter selection).

## Popups (both edit + save in place)

### Annotation popup (Importance + Next step together)
Opened by clicking the inline Importance or Next step cell on a row. ONE popup containing BOTH
fields together:
- **Importance for sign-off** — text area.
- **Next step** — text area.
Explicit Save → `upsert_spillover_annotation(spillover_id, ...)`. On save, close the popup and
reflect the new values in the row. Both fields are saved together.

### Comment history popup
Opened by the row's "Comment history" button. A single editable text area bound to
`comment_history`:
- Shows the current saved comment history (verbatim).
- Editable in the popup; explicit Save → `upsert_spillover_annotation(...)` persists
  `comment_history`. This is the user's hand-maintained, cleaned-up version.
- User-authored only — never seeded from or overwritten by the imported `comment`.

All authored fields live in `spillover_annotations` and survive every import (principle 1).
The raw imported `comment` is part of the spillover row and is not edited here.

## Acceptance
- "Core South Spillover" button on dashboard → list view (the entire UI; no detail page).
- Passed / Passed pending Solman / Dropped hidden by default; Status filter lists all and
  auto-reveals a hidden selection; toggle reveals them wholesale; Area / Type / Assignee filters work.
- Importance + Next step show inline and edit together in one popup, saving to the annotation row.
- Comment history opens in its own popup, edits and saves independently, shown verbatim.
- No SQL in the web layer; defects UI untouched.
