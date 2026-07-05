# Build Plan — 2026-07-05

Day plan, to be refined. Master backlog: `docs/build_plan.md`.

## 1. Order-details drop-in component

Extract the Order-details popup (dialog + JS, currently duplicated with
drift in `spillover.html` and `ecom_gatekeeper.html`) into a drop-in
component `_order_details.html`, AJAX-driven like `_entity_links.html` /
`_teams_channels.html`:

```
{% with od_entity_type='topic', od_entity_id=topic.id %}
  {% include '_order_details.html' %}
{% endwith %}
```

- Backend needs NOTHING: `order_details` table + `/order-details/...` routes
  are already generic (entity_type + entity_id).
- The spillover variant is canonical (order type · number · comment ·
  "docs in S4" checkbox with green ✓ badge); gatekeeper inherits the S4
  checkbox as a free upgrade.
- Migrate spillover + ecom_gatekeeper onto the component, DELETING their two
  inline copies; tests for the component roundtrip.
- Then place the button on further cards as desired (one include each) —
  candidates to decide: Topics? Defects?

## 2. (to be refined)

- …
