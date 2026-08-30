# Test Learnings

**Type:** mini app
**URL:** `/test_learnings` · `/test_learnings/new` · `/test_learnings/<id>` (+ `/delete`)
**Storage:** `app/db/reference.py` over `db/core.py` → `test_learnings`
**Routes:** `app/web_reference.py`
**Templates:** `test_learning_list.html` · `test_learning_detail.html`

## Purpose

What was learned while testing and must not be re-learned: how a scenario
really behaves, the trick that makes a case work, the thing that confuses every
new tester. Written down once, found again later — including by whoever takes
over.

## Architecture

**Columns**: `channel` (NOT NULL, default 'Retail'), `topic`, `learning` (the
text, NOT NULL), `scenario`, `tags`, timestamps.

- **List**: multi-select filters for channel AND tags
  (`?channel=…&tag=…`, repeatable), options from the values in use
  (`get_test_learning_options`).
- **Detail**: the form plus the shared notes section (registry key
  `test_learning`) — it is also an inbox filing target, so a captured note can
  become a learning.
- Reachable from the `[[retail]]` and `[[ecom]]` list pages via a channel-filtered
  button (`?channel=Retail` / `?channel=ECOM`).

## Rules & gotchas

- `tags` is a free-text field used as a multi-value filter — keep the spelling
  consistent or the filter list grows spurious entries.
- A learning is about HOW to test. What cannot be tested at all belongs in
  `[[test-limitations]]`; a live-system problem belongs in
  `[[known-production-issues]]`.

## Related

`[[test-limitations]]` · `[[retail]]` · `[[ecom]]` · `[[notes]]` · `[[inbox]]`
