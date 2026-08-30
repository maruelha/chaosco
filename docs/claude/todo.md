# To-Do

**Type:** mini app
**URL:** `/todos`
**Storage:** `app/db/core.py` → `todos`
**Routes:** `app/web_planning.py`
**Templates:** `todo_list.html`

## Purpose

The plain task list: priority, due date, kind, owner, notes. Everything that is
work but is not urgent enough for `[[urgent]]` and not a piece of active
research like `[[topics]]`.

## Architecture

One table, one page. Default view hides closed items. Sort order: blocked
first, then in_progress, then open, then by priority and due date. Notes come
from the shared notes module via a list-only registry entry (`todo`) — quick-add
from the list page, no detail page.

## Rules & gotchas

- To-Do, Deadlines & Burning and Topics are deliberately three different
  things: a to-do is work, an urgent item is a nag, a topic is active
  research/coordination with a workpad. Do not consolidate them.

## Related

`[[urgent]]` · `[[topics]]` · `[[meeting-prep]]` · `[[notes]]`
