# Spillover — Fix: list view columns + Excel-style frozen panes

## Context
UI-only change to the existing Core South Spillover list view. Do NOT change the schema, the
importer, or any storage method. All data referenced below already exists on the `spillover` row
and in `spillover_annotations`.

## Changes

### 1. Columns shown
- ADD the **Order numbers** column (`order_numbers`) — it is missing from the current view but
  exists on the row. Place it among the scrollable columns (not the frozen set).
- REMOVE **Content** and **Ext. ID** from the table view. They stay in the table data and the DB —
  just not displayed as columns. (Ext. ID / `external_id` and `content` are still available; if
  needed later they can surface in a popup.)

### 2. Frozen panes (Excel-style) — the core fix
Replace the current single-block scrolling with a self-contained scroll region that freezes both
the header row and the identity columns.

Requirements:
- Wrap the table in a scroll container with a CAPPED height (e.g. fits ~15 rows; use a viewport-
  relative max-height like `max-height: 70vh`) and `overflow: auto`. The table scrolls INSIDE this
  container in both directions; the page chrome (title, filters, the "Show passed & dropped"
  toggle, the item count) stays fixed above it and does not scroll with the table.
- **Freeze the header row** at the top: header cells use `position: sticky; top: 0` with a solid
  (non-transparent) background and a higher `z-index` so rows scroll underneath it.
- **Freeze these columns on the left**, in this order, while the rest scroll horizontally:
  **Excel row, Type, Area, Status, Name.**
  - Each frozen column uses `position: sticky` with an explicit `left` offset equal to the summed
    widths of the frozen columns to its left. This REQUIRES fixed widths on these five columns —
    set explicit, sensible widths (Excel row narrow; Type/Area/Status short ~one word each; Name
    wider). Use `table-layout: fixed` so widths are honored.
  - Frozen cells need a solid background and a `z-index` above the scrolling cells. The top-left
    intersection cells (frozen column AND header row) need the highest `z-index` so they stay on
    top of both.
- The horizontal and vertical scrollbars belong to this container, so they remain within the
  visible area at all times — no scrolling the page down to reach a bottom scrollbar.

### 3. Scrolling columns (after the frozen set)
Country, Assigned to, Order numbers (new), Importance for sign-off, Next step, and the Comments
button. These scroll horizontally under the frozen columns.

## Notes / gotchas
- Sticky positioning fails silently if an ancestor has `overflow: hidden` — make sure the scroll
  container is the intended sticky context and no wrapping element clips it.
- Keep the inline-edit behavior (Importance + Next step popup) and the per-row Comments popup
  exactly as they are; this change is layout only.
- If the five frozen columns end up too tight in practice, the easiest later relief is rendering
  Status as a short colored badge rather than full text — leave a note but do not implement now.

## Acceptance
- Order numbers column visible; Content and Ext. ID no longer shown (still in DB).
- Scrolling right keeps Excel row / Type / Area / Status / Name visible; scrolling down keeps the
  header row visible; both scrollbars stay on screen without scrolling the page first.
- No schema, importer, or storage changes. Filters, toggle, and popups behave as before.
