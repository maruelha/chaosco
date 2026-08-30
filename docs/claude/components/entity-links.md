# Entity links (per-entity URL list)

**Type:** component
**URL:** `/elinks/<etype>/<eid>/list.json|add` · `/elinks/<id>/delete`
**Storage:** `app/db/entity_links.py` → `entity_links`
**Routes:** `app/web_entity_links.py`
**Templates:** `_entity_links.html`

## Purpose

A generic list of URLs hanging off any entity — same idea as notes and order
details, for the links that belong to one topic or ticket rather than to the
global Links directory.

## Architecture

```
{% with el_entity_type='topic', el_entity_id=topic.id %}
  {% include '_entity_links.html' %}
{% endwith %}
```

AJAX drop-in, zero route/context changes. `http(s)` URLs only; the label
defaults from the URL when none is typed.

## Rules & gotchas

- Currently on Topic detail only — it is a component, not a page.
- Do not confuse with `[[links]]` (the global bookmark directory, its own
  mini app) or with `teams_chats` links.

## Related

`[[links]]` · `[[topics]]` · `[[connections]]`
