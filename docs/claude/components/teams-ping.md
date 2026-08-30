# Teams ping + channel picker

**Type:** component
**URL:** `/teams-ping/<entity_type>/<entity_id>` · `/teams-ping/chat/0` · `/teams-ping/channels.json|add|<id>/delete`
**Storage:** no own table — contacts for the email lookup, `teams_chats` (kind='channel') for the picker
**Routes:** `app/web_teams.py`; link building in `app/teams_link.py`
**Templates:** `teams_ping.html` · `_teams_channels.html`
**Tests:** `tests/test_teams_link.py`

## Purpose

Write a Teams message to the person behind a row without leaving chaosco — no
API, no credentials, no approvals. The page opens the local Teams client with
the chat pre-typed; the user presses Enter.

## Architecture

REGISTRY-driven like the notes module: a new card gets a ping button by adding
ONE `PingEntity` to `web_teams.REGISTRY` (get_row, person, topic, back
endpoint) and linking to
`url_for('teams_ping.ping', entity_type=…, entity_id=…)`. Registered today:
`followup`, `cs_followup`, `defect` (assigned_to).

The page shows recipient email(s) — pre-filled via `find_contact_email`
matched against contacts, with a datalist of all contacts — an editable
message (template overridable via the `teams_message_template` config) and an
"Open in Teams" deep link
(`https://teams.microsoft.com/l/chat/0/0?users=…&message=…`).
Comma-separated emails open a group chat (optional topicName).
"Save to contacts" stores a typed address under the row's name
(`upsert_contact_email`: updates a name-matched contact or creates a minimal
one) so it pre-fills next time.

### Channel picker

`{% include '_teams_channels.html' %}` in any card header renders a "Teams
channels" button + dialog: saved channels open in the Teams client; add (name
+ "Get link to channel" URL, validated to teams.microsoft.com) and remove
inline. Fully AJAX, so the including page needs NO route or context changes.
Since 2026-07-16 the channels are STORED in the `teams_chats` registry
(kind='channel'; the old "Teams Channel" rows were migrated out of `links` at
startup) — the picker's routes and shapes are unchanged. Currently included at
the bottom of the Defects and Spillover lists, next to a generic "Teams chat"
button (`/teams-ping/chat/0` — the ping page without entity context: empty
message, recipient from the contacts autocomplete).

## Rules & gotchas

- Deep links CANNOT target existing named group chats or meeting chats (that
  needs Graph thread ids) and cannot pre-fill channel posts. This is a Teams
  limitation, not a missing feature — hence the copy-then-paste flow in the
  ✉️ builder.

## Related

`[[teams-chats]]` (the registry + 💬 widget) · `[[contacts]]` ·
`[[follow-ups]]` · `[[issue-message]]`
