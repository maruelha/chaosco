# Next-step archive (↻ / 🕘)

**Type:** component
**URL:** `/next-steps/<entity_type>/<entity_id>/…` (+ `list.json`)
**Storage:** `app/db/next_steps.py` → `next_step_history`
**Routes:** `app/web_next_steps.py` (registry-driven Blueprint)
**Templates:** `_next_step_history.html` (once per page) + `.js-ns-archive` / `.js-ns-history` buttons
**Tests:** `tests/test_next_step_archive.py`, `tests/test_gatekeeper_jira.py`

## Purpose

[USER 2026-07-10] A next-step field must stay ONE line — but the past must not
be lost. "↻ New next step" archives the current stored next step with a
timestamp and clears the live field; the History dialog (🕘) shows what was
there before, entries deletable.

## Architecture

```
{% include '_next_step_history.html' %}   {# once per page #}
<button class="js-ns-archive" data-entity-type="<type>"
        data-entity-id="<id>" data-ns-target="#field-selector">↻</button>
<button class="js-ns-history" data-entity-type=… data-entity-id=…
        data-ns-label="heading">History</button>
```

Registry-driven: one `NSEntity` per type says how to READ and CLEAR its field.
The clears are only-this-field upserts (`set_spillover_next_step`,
`set_retail_next_step`, `set_defect_next_step`, `set_ecom_next_step` — the
ECOM one resolves `ecom_id` → `jira_id`). Clicks are delegated;
`data-ns-target` elements are blanked client-side (no target = page reload);
a CustomEvent `ns-archived` lets a page do extras (the spillover list blanks
the row cell).

## Rules & gotchas

- Archiving must never write another module's fields — hence one narrow
  setter per entity instead of a generic UPDATE.
- Currently on: Spillover details popup, Retail detail, ECOM detail, Defect
  detail, ECOM Gatekeeper list rows (the deprecated manual table AND the
  current Jira tickets table, entity `jira`, ↻/🕘 per row with a per-row
  `data-ns-target`), Gatekeeper ticket detail, Delegated Testing ticket
  detail (entity `delegated`), Blockers (`blocker`, on the blockers table
  itself), Smoke Testing scenarios (`smoke`), Sustainphase Issues
  (`sustain_issue`, keyed by issue_key), Sustain Call-outs (`sustain_callout`,
  2026-09-01 — on the sustain_callouts table itself, blocker pattern).

## Related

`[[notes]]` · `[[order-details]]` · `[[gatekeeper]]`
