# Test Learnings

**Type:** mini app
**URL:** `/test_learnings?channel=…` (+ detail page)
**Storage:** `app/db/core.py` → `test_learnings`
**Routes:** `app/web_reference.py`
**Templates:** `test_learning_list.html` · `test_learning_detail.html`

## Purpose

What was learned while testing and must not be re-learned: the behaviour of a
scenario, the trick that makes a case work, the thing that always confuses a
new tester. Filtered per channel and linked from the Retail and ECOM pages.

## Architecture

List (channel filter) + detail page with the shared notes section (registry
key `test_learning`, also an inbox filing target).

## Related

`[[test-limitations]]` · `[[retail]]` · `[[ecom]]` · `[[notes]]`
