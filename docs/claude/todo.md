# To-Do

**Type:** mini app
**URL:** `/todos` (+ `/todos/add`, `/<id>/status`, `/<id>/update`, `/<id>/delete`)
**Storage:** `app/db/planning.py` over `db/core.py` → `todos`
**Routes:** `app/web_planning.py`
**Templates:** `todo_list.html`

## Purpose

The plain task list: what has to be done, by when, by whom. Everything that is
work but does not deserve the daily popup of `[[urgent]]` and is not the active
research/coordination of a `[[topics]]` entry.

## Architecture

**Columns**: `area`, `kind`, `topic` (the task, NOT NULL), `status`,
`priority`, `due_date`, `for_whom`, timestamps.

- `TODO_STATUSES` = `open` · `in_progress` · `blocked` · `closed`
- `TODO_PRIORITIES` = `High` · `Medium` · `Low` (default Medium)

**Sort order is fixed in SQL and deliberate** — blocked first, then
in_progress, then open, then closed; inside that by priority (High → Low), then
by `due_date` with NULLs last. The list therefore always opens on what is stuck.

`get_todos` LEFT JOINs the shared `notes` table (`entity_type='todo'`) so every
row carries a `note_count` without a second query. Filters: area · status ·
priority · for_whom · due_date, plus `?closed=1` to include closed items
(hidden by default). The area and for-whom dropdowns are built from the DISTINCT
values actually present (`get_todo_filter_options`) — no maintained option list.

Notes come from the shared module through a **list-only registry entry**
(`todo`): quick-add from the list page, no detail page.

## Rules & gotchas

- To-Do, `[[urgent]]` and `[[topics]]` are three different things on purpose: a
  to-do is work, an urgent item is a nag that gets pushed in your face daily, a
  topic is active work with a workpad. Do not consolidate them.
- `kind` is free text, not a fixed list — it classifies loosely and is not
  filtered on.

## Related

`[[urgent]]` · `[[topics]]` · `[[meeting-prep]]` · `[[notes]]` · `[[inbox]]`
