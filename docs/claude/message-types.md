# Message Types

**Type:** mini app
**URL:** `/message-types` (+ `/add`, `/<id>/update`, `/<id>/delete`)
**Storage:** `app/db/message_types.py` → `message_types`
**Routes:** `app/web_issue_msg.py`
**Templates:** `message_types.html`
**Tests:** `tests/test_issue_messages.py`

## Purpose

The reference table behind the ✉️ issue-message builder: which message type
travels over which TIBCO / IIB API, plus a comment. Editable, because the
interface names change more often than the message wording.

## Architecture

`message_types` (name, tibco_api, iib_api, comment) with its own card and
page. Seeded with the 8 defaults when the table is EMPTY — deleting all of
them brings them back, an accepted edge case. The builder reads the APIs from
here; the message wording itself is fixed in code (see `[[issue-message]]`).

## Related

`[[issue-message]]` · `[[teams-chats]]`
