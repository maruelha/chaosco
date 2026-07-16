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

Notes-capable entities now include **contacts** and **links** (registry
entries + detail-page includes), so inbox items can be filed to them.

**Inbox special case**: unfiled items are notes with entity_type='input',
entity_id='inbox'. Filing = one UPDATE re-parenting the row (attachments
follow automatically). Inbox keeps its own routes/UI (capture pad + filing).
Filing targets (`_INBOX_TARGET_TYPES` in db/notes.py + picker options in
inbox.html + a search/exists branch each): defect, retail, spillover,
ecom (added 2026-07-10, search by jira id / test case / name),
ecom_gatekeeper (2026-07-11, legacy — no picker option anymore),
jira = "Gatekeeper ticket" (2026-07-11, the current gatekeeper; search by
jira key / solman id / summary), test_learning, followup, shelf, topic,
contact, link.

**Inbox text search** [USER 2026-07-16]: search box in the Pending card
header, live CLIENT-side filter (no route, no SQL) over heading + note text
+ attachment names — deliberately not whole-card textContent, so button
labels ("Edit") don't match everything. Count badge shows "shown / total"
while filtering; ✕ / Escape clears; box only renders when items exist.
Markup contract pinned by tests/test_inbox_search.py.

## Attachments

`attachments` table (note_id FK, filename, original_name); files in
`data/uploads/`; routes `/uploads/<filename>`,
`POST /notes/<note_id>/attachments/add|<id>/delete` (in `app/web_home.py`).
Images render as thumbnails; documents as download links (`is_image` filter).

## Planning entities (app/db/planning.py + app/web_planning.py)

**Card definitions [USER 2026-07-05]** — three deliberately distinct trackers:
`cs_followups` = TOPICS needing attention before go-live;
`followups` = what others promised MARINA (chase list);
`promises` (planned) = what Marina promised OTHERS. Do not consolidate.


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
  `test_learnings`, `test_limitations`, `known_prod_defects` (detail page
  carries the shared notes section since 2026-07-13; registry key
  `prod_defect`)
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

## Teams channel picker (component)

`{% include '_teams_channels.html' %}` in any card's header renders a
"Teams channels" button + dialog: saved channels open in the Teams client,
add (name + "Get link to channel" URL, validated to teams.microsoft.com) and
remove inline. Fully AJAX (`/teams-ping/channels.json|add|<id>/delete`), so
the including page needs NO route/context changes. Channels are stored as
Links with tool = "Teams Channel" (no parallel table; also manageable on
/links). Currently included at the BOTTOM of the Defects and Spillover lists,
next to a generic "Teams chat" button (/teams-ping/chat/0 — the ping
page without entity context: empty message, recipient from contacts
autocomplete).

## Topics (app/db/topics.py + app/web_topics.py)

Active-work counterpart to Shelf (Shelf = archive, Topic = being worked on).
`/topics` list: quick-add, filters (title search, category, priority; done
hidden by default). `/topics/<id>` = the working page: editable meta
(title/category/priority/status), NEXT STEPS (AJAX checkboxes; done steps
archive into a collapsed section, reopenable), a screen-filling WORKPAD
(contenteditable rich text — bold/italic/underline/strike, H2/H3, lists,
quote, highlight; stored as HTML in topics.workpad; autosave on blur +
every 30s + Ctrl+S), and the shared notes module. Inbox files into topics
via the standard picker (search by title/category, active only). Dashboard
card (green accent) shows active count. Tables: topics, topic_steps.
Tests: tests/test_topics.py.

## Entity links (component)

Generic per-entity URL list (table `entity_links`), same idea as notes/
order_details. Drop-in include (AJAX, zero route/context changes):

    {% with el_entity_type='topic', el_entity_id=topic.id %}
      {% include '_entity_links.html' %}
    {% endwith %}

Routes: /elinks/<etype>/<eid>/list.json|add, /elinks/<id>/delete (http(s)
URLs only; label defaults from the URL). Storage app/db/entity_links.py,
routes app/web_entity_links.py. Currently on: Topic detail.

## Next-step archive (component)

"↻ New next step" [USER 2026-07-10]: archives the CURRENT stored next step
(table `next_step_history`, generic entity_type/entity_id address) with a
timestamp and clears the live field — the field stays one line, the past
stays visible via the History dialog (entries deletable).

    {% include '_next_step_history.html' %}   (once per page)
    <button class="js-ns-archive" data-entity-type="<type>"
            data-entity-id="<id>" data-ns-target="#field-selector">…</button>
    <button class="js-ns-history" data-entity-type=... data-entity-id=...
            data-ns-label="heading">History</button>

Registry-driven Blueprint `app/web_next_steps.py` (`/next-steps/...`): one
NSEntity per type says how to READ and CLEAR its field (only-this-field
upserts: set_spillover_next_step / set_retail_next_step /
set_defect_next_step / set_ecom_next_step — ecom resolves ecom_id→jira_id).
Storage `app/db/next_steps.py`. Delegated clicks; `data-ns-target` elements
are blanked client-side (no target = page reload); CustomEvent
'ns-archived' for page extras (spillover list blanks the row cell).
Currently on: Spillover Details popup, Retail detail, ECOM detail, Defect
detail, ECOM Gatekeeper list rows (deprecated manual table AND the current
Jira tickets table — entity `jira`, ↻/🕘 per row, per-row `data-ns-target`
selector blanks the inline input), Gatekeeper ticket detail. Tests:
tests/test_next_step_archive.py, tests/test_gatekeeper_jira.py.

## Order details (component)

`{% include '_order_details.html' %}` once per page + open buttons
anywhere:

    <button class="btn btn-sm js-open-orders"
            data-entity-type="<type>" data-entity-id="<id>">Order details</button>

Popup rows: order type · number · comment · docs-in-S4 checkbox; a green ✓
(`s4-tick`) is kept on the opening button while any row has S4 docs. Click
handling is DELEGATED on document — JS-added buttons work without wiring.
Dialog-header name: button `data-od-name` → row `data-name` → row
`[data-field="testcase_name"]` input. Backend was already generic:
`order_details` table (db/reference.py, `get_docs_s4_entity_ids(type)` for
the initial badge) + `/order-details/...` routes (web_spillover.py).
Currently on: Spillover list, ECOM Gatekeeper deprecated manual table
(extracted from their inline copies 2026-07-09), Gatekeeper Check jira
rows + ticket detail, ECOM board + detail. Tests:
tests/test_order_details_component.py.

**Shared jira address** [USER 2026-07-16]: gatekeeper/ECOM order rows are
addressed ('jira', jira_key) — the Gatekeeper Check and the ECOM board read
the SAME rows, connected, never copied (like gatekeeper notes/next steps).
`db/ecom.migrate_order_details_to_jira` re-points legacy 'ecom' /
'ecom_gatekeeper' rows (live + archived batches) where a jira id is known;
runs idempotently from ecom.init_schema on every startup. The "Take over
orders from Gatekeeper" button is gone (relink_gatekeeper_orders +
/ecom/<id>/pull-orders kept as inert legacy). get_docs_s4_entity_ids now
returns str for non-numeric ids (jira keys). Global search resolves
'jira'-addressed order rows to the gatekeeper ticket page. Tests:
tests/test_orders_shared_jira.py.

**Jira AC takeover** [USER 2026-07-16]: jira-addressed dialogs compare the
ACCEPTANCE CRITERIA's labeled orders (extract_ac_order_pairs in
jira_importer.py — AC only, comments deliberately excluded; XXXX skipped;
deduped) against ALL order numbers of the ticket — live AND archived
(db/order_archive.all_order_numbers; archived counts as present). Missing
pairs show in an amber "From Jira acceptance criteria" box with "⤵ Take
over from Jira": inserts them as rows (type = the Jira label verbatim,
add_order_detail_full), never modifies existing rows, idempotent. Missing
list recomputed server-side on takeover; refreshed in the dialog after row
delete. Routes in web_reference.py:
`GET /order-details/jira/<key>/jira-suggestions`,
`POST /order-details/jira/<key>/take-over-jira`. Tests:
tests/test_jira_order_takeover.py.

**Order archive** [USER 2026-07-16]: rows that belong together (sales +
return + exchange order of one chain) are ticked via the select column and
"📦 Archive selected as group" moves them into `order_details_history` as
ONE batch (shared batch_id + archived_at + optional label via prompt; ids
of other entities are ignored server-side). The dialog's collapsible
"Archived groups (N)" section lists batches newest-first, read-only, with
per-batch delete (confirm). Pending inline edits are awaited before
archiving. Storage `app/db/order_archive.py` (schema init in web.py);
routes with the other generic order routes in web_spillover.py:
`POST /order-details/<etype>/<eid>/archive` (form: ids CSV, label),
`GET .../history`, `POST /order-details/history/batch/<id>/delete`.
Tests: tests/test_order_archive.py.
