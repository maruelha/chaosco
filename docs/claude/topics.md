# Topics

**Type:** mini app
**URL:** `/topics/` · `/topics/<id>`
**Storage:** `app/db/topics.py` → `topics`, `topic_steps`
**Routes:** `app/web_topics.py`
**Templates:** `topics_list.html` · `topic_detail.html`
**Tests:** `tests/test_topics.py`

## Purpose

What you are ACTIVELY working on — the counterpart to `[[shelf]]` (Shelf =
archive, Topic = being worked on). A topic is where the thinking lives: the
background, the next steps, the connected defects and test cases.

## Architecture

- `/topics` list: quick-add, filters (title search, category, priority; done
  hidden by default). The dashboard card (green) shows the active count.
- `/topics/<id>` is the working page: editable meta (title / category /
  priority / status), NEXT STEPS (AJAX checkboxes; done steps archive into a
  collapsed section and can be reopened), a screen-filling WORKPAD, and the
  shared notes module.
- **Workpad**: contenteditable rich text — bold / italic / underline / strike,
  H2/H3, lists, quote, highlight — stored as HTML in `topics.workpad`;
  autosave on blur, every 30s, and on Ctrl+S.
- Inbox files into topics via the standard picker (search by title/category,
  active only).

## Rules & gotchas

- **Detail-page order** [USER 2026-07-18]: meta → WORKPAD FIRST (it is the
  actual content) → next steps → links → notes. Do not push the workpad down.
- A topic can be linked FROM a retrofit (`retrofits.topic_id`) and connected to
  defects / test cases via `[[connections]]` — those links are resolved live,
  never copied.

## Related

`[[shelf]]` · `[[connections]]` · `[[entity-links]]` · `[[retrofits]]` ·
`[[notes]]`
