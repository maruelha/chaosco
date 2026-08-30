# Issue-message builder (✉️)

**Type:** component
**URL:** `/issue-msg/meta.json` · `/issue-msg/context/<etype>/<eid>` · `/issue-msg/<etype>/<eid>/save-note`
**Storage:** fixed texts in `app/issue_messages.py`; API columns in `message_types` (see `[[message-types]]`)
**Routes:** `app/web_issue_msg.py`
**Templates:** `_issue_message.html` (delegated `.js-open-msg`, `data-msg-name` = subtitle)
**Tests:** `tests/test_issue_messages.py`

## Purpose

[USER 2026-07-16] Standardized order-issue texts from the ✉️ button on the
rows AND detail pages of Retail / Spillover / ECOM / Gatekeeper — so the same
issue is always reported in the same words, with the right order numbers and
the right interface names in it.

## Architecture

Message = context header (`"<identifier> — orders: <all order numbers>"`) + a
SPECIAL TEXT with `{message}` (type name) and `{orders}` (highlighted numbers;
none ticked = all) resolved + a `"TIBCO: … · IIB: …"` line when the type has
APIs (deletable — the preview textarea is editable and the controls rebuild
it).

- **Special texts are FIXED in code** (`issue_messages.SPECIAL_TEXTS`, 8
  entries) — [USER]: making them editable "might be a bit brittle". Changing
  wording = edit that list.
- `build_message()` is the assembly contract; the JS in `_issue_message.html`
  MIRRORS it — keep both in sync.
- Placeholders: `{message}`, `{orders}`, and `{tibco_api}` [USER 2026-07-18] —
  resolves to `" (<tibco api>)"` when the chosen type has one, else `""` (the
  space and brackets live in the replacement), so `check_tibco` ends
  "…has reached tibco (API)".
- **Context per screen**: jira → SolMan ID (fallback key) + order_details;
  retail → "tc / country" + imported order/S4 fields (labeled); spillover →
  name (+ external id) + order_details + the imported order_numbers cell.
- **Actions**: 📋 copy · copy-and-open a Teams chat (attached first, then
  pinned — Teams cannot prefill an existing chat, so copy-then-paste) ·
  💾 save as note on the entity (`source='issue-msg'`, heading = template
  label; save targets jira / retail / spillover).

## Rules & gotchas

- Two implementations of the same assembly exist on purpose (Python for save,
  JS for the live preview) — a change in one without the other silently
  produces two different messages.

## Related

`[[message-types]]` (the editable API table) · `[[teams-chats]]` ·
`[[order-details]]` · `[[notes]]`
