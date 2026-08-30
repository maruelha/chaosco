# Order details (per-entity order log)

**Type:** component
**URL:** `/order-details/<entity_type>/<entity_id>` (+ `/history`, `/archive`, jira suggestions)
**Storage:** `app/db/reference.py` → `order_details` · `app/db/order_archive.py` → `order_details_history`
**Routes:** the generic `/order-details/...` routes live in `app/web_spillover.py`; the jira-takeover ones in `app/web_reference.py`
**Templates:** `_order_details.html`
**Tests:** `tests/test_order_details_component.py`, `tests/test_orders_shared_jira.py`, `tests/test_jira_order_takeover.py`, `tests/test_order_archive.py`

## Purpose

The order numbers behind an item — sales, return, exchange — with a comment
and a "documents in S4" tick, reachable from any row without leaving the page.

## Architecture

```
{% include '_order_details.html' %}   {# once per page #}
<button class="btn btn-sm js-open-orders"
        data-entity-type="<type>" data-entity-id="<id>">Order details</button>
```

Popup rows: order type · number · comment · docs-in-S4 checkbox. A green ✓
(`s4-tick`) stays on the opening button while any row has S4 docs. Click
handling is DELEGATED on document, so JS-added buttons work without wiring.
Dialog-header name: button `data-od-name` → row `data-name` → row
`[data-field="testcase_name"]` input. `get_docs_s4_entity_ids(type)` gives the
initial badges.

### Shared jira address [USER 2026-07-16]

Gatekeeper and ECOM order rows are addressed `('jira', jira_key)` — the
Gatekeeper Check and the ECOM board read the SAME rows: connected, never
copied (like gatekeeper notes and next steps).
`db/ecom.migrate_order_details_to_jira` re-points legacy `ecom` /
`ecom_gatekeeper` rows (live AND archived batches) where a jira id is known;
it runs idempotently from `ecom.init_schema` on every startup.
`get_docs_s4_entity_ids` returns str for non-numeric ids (jira keys), and the
global search resolves jira-addressed order rows to the gatekeeper ticket page.

### Jira AC takeover [USER 2026-07-16]

Jira-addressed dialogs compare the ACCEPTANCE CRITERIA's labeled orders
(`extract_ac_order_pairs` in `jira_importer.py` — AC only, comments
deliberately excluded; `XXXX` skipped; deduped) against ALL order numbers of
the ticket, live AND archived (`db/order_archive.all_order_numbers` — archived
counts as present). Missing pairs appear in an amber "From Jira acceptance
criteria" box with "⤵ Take over from Jira": inserts them as rows (type = the
Jira label verbatim), never modifies existing rows, idempotent. The missing
list is recomputed server-side on takeover and refreshed after a row delete.
Routes: `GET /order-details/jira/<key>/jira-suggestions`,
`POST /order-details/jira/<key>/take-over-jira`.

### Order archive [USER 2026-07-16]

Rows that belong together (the sales + return + exchange order of one chain)
are ticked via the select column; "📦 Archive selected as group" moves them
into `order_details_history` as ONE batch (shared `batch_id`, `archived_at`,
optional label via prompt; ids of other entities are ignored server-side).
The dialog's collapsible "Archived groups (N)" section lists batches
newest-first, read-only, with per-batch delete. Pending inline edits are
awaited before archiving.

## Rules & gotchas

- The backend was generic from the start; the component only replaced the
  inline copies (extracted 2026-07-09) — do not re-inline it.
- "Take over orders from Gatekeeper" is GONE; `relink_gatekeeper_orders` and
  `/ecom/<id>/pull-orders` are kept only as inert legacy.
- Currently on: Spillover list, the deprecated gatekeeper manual table,
  Gatekeeper Check jira rows + ticket detail, ECOM board + detail.

## Related

`[[gatekeeper]]` · `[[ecom]]` · `[[spillover]]` · `[[notes]]`
