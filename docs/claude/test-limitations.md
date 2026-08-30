# Test Limitations

**Type:** mini app
**URL:** `/test_limitations` · `/test_limitations/new` · `/test_limitations/<id>` (+ `/delete`)
**Storage:** `app/db/reference.py` over `db/core.py` → `test_limitations`
**Routes:** `app/web_reference.py`
**Templates:** `test_limitation_list.html` · `test_limitation_detail.html`

## Purpose

What CANNOT be tested, and why — environment gaps, missing interfaces, data
that does not exist in UAT. The honest counterpart to a green report: it names
the holes instead of letting a passed percentage imply full coverage.

## Architecture

**Columns**: `channel` (NOT NULL, default 'Retail'), `limitation` (NOT NULL),
`scenario`, `comment`, timestamps.

- **List**: multi-select channel filter (`?channel=…`, repeatable), options
  from the values in use (`get_test_limitation_options`).
- **Detail**: the form plus the shared notes section (registry key
  `test_limitation`).
- Reachable from the `[[retail]]` and `[[ecom]]` list pages, channel-filtered.

## Rules & gotchas

- A limitation is about the TEST setup. A defect in the live system is a
  `[[known-production-issues]]` entry; a missing test CASE is a
  `[[missing-tests]]` entry. Three different lists, three different audiences.

## Related

`[[test-learnings]]` · `[[known-production-issues]]` · `[[missing-tests]]` ·
`[[retail]]` · `[[ecom]]`
