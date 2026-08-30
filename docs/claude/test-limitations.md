# Test Limitations

**Type:** mini app
**URL:** `/test_limitations?channel=…` (+ detail page)
**Storage:** `app/db/core.py` → `test_limitations`
**Routes:** `app/web_reference.py`
**Templates:** `test_limitation_list.html` · `test_limitation_detail.html`

## Purpose

What CANNOT be tested, and why — environment gaps, missing interfaces, data
that does not exist in UAT. The honest counterpart to a green report: it
explains the holes instead of hiding them.

## Architecture

List (channel filter) + detail page with the shared notes section. Reachable
from the Retail and ECOM list pages.

## Rules & gotchas

- A limitation is not a defect and not a `[[known-production-issues]]` entry:
  it is about the TEST setup, not about the live system.

## Related

`[[test-learnings]]` · `[[known-production-issues]]` · `[[retail]]` · `[[ecom]]`
