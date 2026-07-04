# Coordination modules — planning, reference, notes, inbox, shelf

Read when working on the manually-managed modules (everything that is not an
Excel import vertical or the tracker).

## The notes module — the one rule that must always be followed

There is ONE notes table (`notes`: entity_type, entity_id, created_at,
heading, note, source) and, since the 2026-07-04 refactoring, ONE web layer
for it:

- **Routes**: `app/web_notes.py` Blueprint — generic add/edit/delete at
  `/n/<entity_type>/<entity_id>/...` plus `list.json` / `add.json` for the
  expand-row UIs. New entity types register in its `REGISTRY` (label,
  list/detail endpoints, row getter) — that is ALL a new module needs.
- **Template**: `{% include '_notes_section.html' %}` with
  `entity_type`, `entity_id`, `notes`, `attachments_by_note` in context.
- **JS**: `app/static/notes.js` (loaded globally) — attachment upload,
  delete, Ctrl+V paste via event delegation. Never inline a copy.
- **Data access**: `app.db.notes` (add_note / list_notes / update_note /
  delete_note; inbox helpers; attachments).

Never create a module-specific notes table, route set, or attachment script.

**Inbox special case**: unfiled items are notes with entity_type='input',
entity_id='inbox'. Filing = one UPDATE re-parenting the row (attachments
follow automatically). Inbox keeps its own routes/UI (capture pad + filing).

## Attachments

`attachments` table (note_id FK, filename, original_name); files in
`data/uploads/`; routes `/uploads/<filename>`,
`POST /notes/<note_id>/attachments/add|<id>/delete` (in `app/web_home.py`).
Images render as thumbnails; documents as download links (`is_image` filter).

## Planning entities (app/db/planning.py + app/web_planning.py)

- `meeting_prep` — per-meeting agenda topics; overall_topic ordering; agenda
  export `/meeting-prep/agenda`; DTC O2C Daily agenda
  `/meeting-prep/dtco2c-daily` (planned topics + daily-flagged defects +
  DTC O2C followups); source_entity link badges
- `todos`, `followups` (lightweight per-person chase list + detail page),
  `cs_followups` (richer, CS sign-off), `enhancements` (global floating
  panel on every page + `/enhancements/page`)

## Reference entities (app/db/reference.py + app/web_reference.py)

- `shelf` — catch-all store; list/detail/combine; inbox files into it
- `links`, `contacts`, `encouragements`/`encouragement_people`,
  `test_learnings`, `test_limitations`, `known_prod_defects`
- `ecom_gatekeeper` — inline-editable pre-handoff table; notes + order
  details; future handover re-points order_details to the ECOM vertical
- `order_details` — generic per-entity order log
  (`/order-details/<entity_type>/<entity_id>`), docs_in_s4 checkbox
- `report_comments` — free-text bullets under the Spillover/Retail reports

## Email reports (app/emailer.py + app/web_email.py + app/db/email.py)

`/email-report` — send the status reports as standalone-HTML attachments via
GMX SMTP. Checkbox per report (Spillover / Retail / Requirements Board),
date field (default today) drives subject + body text (both editable),
recipients managed in the `report_recipients` table (add / toggle active /
delete; active ones pre-ticked). Credentials `email_user`/`email_password`
belong ONLY in gitignored settings.local.yaml — the page shows setup
instructions and disables Send until configured. The board attachment is
rendered through the app and made standalone by `emailer.standalone_html`
(CSS inlined, scripts stripped, sections opened). Tests: tests/test_emailer.py
(assembly, snapshot, CRUD, mocked SMTP).

## Teams ping (app/teams_link.py + app/web_teams.py)

REGISTRY-driven like the notes module: `/teams-ping/<entity_type>/<id>` — a
new card gets a ping button by adding ONE PingEntity to `web_teams.REGISTRY`
(get_row, person, topic, back endpoint) and linking to
`url_for('teams_ping.ping', entity_type=..., entity_id=...)`. Registered:
followup, cs_followup, defect (assigned_to). `/teams-ping/followup/<id>` — from a follow-up's "Teams" button: opens a page
with recipient email(s) (pre-filled via `find_contact_email` match against
contacts; datalist of all contacts), editable message (template overridable
via `teams_message_template` config), and an "Open in Teams" deep link
(`https://teams.microsoft.com/l/chat/0/0?users=...&message=...`) that opens
the local Teams client with the chat pre-typed — the user presses Enter.
Comma-separated emails open a group chat (optional topicName). No API, no
credentials, no approvals. Deep links CANNOT target existing named group
chats/meeting chats (needs Graph thread ids) or pre-fill channel posts.
"Save to contacts" on the page stores a typed address under the
follow-up's name (`upsert_contact_email`: updates a name-matched contact
or creates a minimal one) so it pre-fills next time. Tests:
tests/test_teams_link.py.
