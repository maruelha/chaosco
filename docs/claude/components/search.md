# Global search (🔍)

**Type:** component
**URL:** `/search/orders.json` (the floating widget in `base.html` calls it)
**Storage:** no tables — a source REGISTRY in `app/db/search.py` reading the existing ones
**Routes:** `app/web_search.py`
**Templates:** the widget lives in `base.html` (stacked with the 💬 and enhancements widgets)
**Tests:** `tests/test_search.py`, `tests/test_search_new_sources.py`

## Purpose

[USER 2026-07-10] Find the thing you have in your hand — today an ORDER NUMBER
— from any page, board included, without knowing which module it belongs to.

## Architecture

The widget sits in `base.html`, so it hovers over every page. Each searchable
source is one block in `db/search.py`: where to look, how to label a hit,
which entity a hit belongs to. The module returns plain dicts grouped by
source; the web layer maps `(type, id)` → URL. Hits show a plain-text snippet
around the match (`_snippet`, HTML stripped). Minimum query length is 3.

Adding a source = one block in `db/search.py` + one URL mapping in
`web_search.py`. The widget UI never changes.

## Rules & gotchas

- Jira-addressed order rows resolve to the GATEKEEPER ticket page, not to a
  raw order row — see `[[order-details]]` (shared jira address).
- Topics via SQLite FTS5 is the planned next source — deliberately NOT
  embeddings until FTS proves insufficient [discussion 2026-07-10].

## Related

`[[order-details]]` · `[[gatekeeper]]` · `[[topics]]`
