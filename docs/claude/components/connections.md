# Entity connections (topic ↔ defect / retail / ecom / spillover)

**Type:** component
**URL:** `/connections/<etype>/<eid>/list.json|add` · `/connections/<id>/delete`
**Storage:** `app/db/entity_connections.py` → `entity_connections`
**Routes:** `app/web_connections.py`
**Templates:** `_connections.html`
**Tests:** `tests/test_connections.py`

## Purpose

[USER 2026-07-18] Many-to-many links BETWEEN entities: a topic that belongs to
a defect, a defect that belongs to a test case. Most items have none — "it
will not always have it" — so the section is collapsed when empty and opens
itself when connections exist.

## Architecture

ONE direction-less row per pair: the two sides are stored in canonical order
with a UNIQUE constraint, so connecting from either side is the same row.
Labels are resolved LIVE from the current tables (re-imports and renames stay
fresh — nothing is copied into the link row). The picker search REUSES
`GET /inbox/targets`.

```
{% with conn_entity_type='topic', conn_entity_id=topic.id %}
  {% include '_connections.html' %}
{% endwith %}
```

Drop-in: AJAX, zero route or context changes in the including page.
`CONNECTABLE_TYPES` = topic / defect / retail / ecom / spillover. Adding a
type = one label branch + one URL entry + a search branch in `/inbox/targets`
if it is missing there.

## Rules & gotchas

- DETAIL pages only, near the notes section — not on list rows.
- Never store the label; resolve it. A renamed test case must not leave a
  stale connection label behind.

## Related

`[[notes]]` · `[[entity-links]]` · `[[topics]]`
