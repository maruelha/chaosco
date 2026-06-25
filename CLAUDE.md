# chaosco — Project Context for Claude

## What this is

A personal UAT coordination toolkit for a **retail system migration** (SAP S/4 go-live).
Marina is the chaos coordinator tracking defects, test-case execution, and sign-off readiness
across **four workstreams**: Retail, Core South, ECOM, and Omni.

The tool reads a shared Excel workbook (`DTC_UAT_testtracking_ROE.xlsx`) and serves a
local Flask browser UI at `http://127.0.0.1:5000`.

**Start the app:** double-click `run_web.bat` (kills any existing process on port 5000 first).

---

## Architecture — non-negotiable rules

1. **Each Excel tab = its own importer + its own SQLite table.** Never touch other importers or tables.
2. **Never modify the source Excel file.** Read-only always.
3. **Imported data vs authored data never mix.**
   - Importers write only to `defects`, `spillover`, `retail`.
   - Annotation tables (`defect_annotations`, `spillover_annotations`, `retail_annotations`) are NEVER written by importers.
4. **All SQL lives in `app/database.py`.** The web layer (`app/web.py`) never writes SQL directly.
5. **Config-driven:** `config/settings.yaml` (file paths, sheet names, hidden statuses), `config/status_mappings.yaml` (retail bucket definitions).
6. **When adding new features, follow the Retail vertical as the template** (most recently built).

---

## Stack

| Layer | Tech |
|---|---|
| Web framework | Flask (Jinja2 server-rendered HTML) |
| Database | SQLite (`data/test_coordination.db`) |
| Import | pandas + openpyxl |
| Config | PyYAML |
| Run | `python -m app.web` or `run_web.bat` |

---

## Import verticals — current and planned

| Vertical | Excel tab | DB table | Annotations table | Match key | Status |
|---|---|---|---|---|---|
| Defects | "Defects" | `defects` | `defect_annotations` | `defect_id` (TEXT PK) | ✅ Built |
| Core South Spillover | "Core South Spillover" | `spillover` | `spillover_annotations` | `excel_row` (integer, stable) | ✅ Built |
| Retail | "Retail" | `retail` | `retail_annotations` | lower(test_case_id) \|\| "\|\|" \|\| lower(country) | ✅ Built |
| ECOM | TBD Excel tab | `ecom` (planned) | `ecom_annotations` (planned) | TBD | 🔜 Planned |
| Omni | TBD Excel tab | `omni` (planned) | `omni_annotations` (planned) | TBD | 🔜 Planned |

**ECOM and Omni will follow the exact same pattern as Retail** — new importer module, new table,
new annotations table, new UI vertical. They come from the same Excel file.
When building them: use `retail_importer.py`, `retail_annotations`, and the Retail UI screens as the template.

Import is idempotent (upsert, never delete). `first_seen` is set once; `last_seen` updates every run.

---

## All database tables (as of 2026-06-21)

### Imported (written by importers only)
- `defects` — 21 columns incl. defect_id (PK), channel, solman_status, priority, assigned_to, excel_row, first_seen, last_seen
- `spillover` — spillover_id (PK AI), type, name, country, area, status, assigned_to, external_id, order_numbers, content, comment, excel_row, match_key (UNIQUE), first_seen, last_seen
- `retail` — retail_id (PK AI), test_case_id, country, testcase_name, testcase_scenario, status, assigned_to, key_user_responsible, evidence_in_sharepoint, sales_file, execution_started, execution_completed, order_number, old_order_numbers, defect_id_ref, s4_sales_order, s4_billing_documents, s4_journal_invoice_entry, delivery_note, comment, reason_for_pass_with_reservation, excel_row, match_key (UNIQUE), first_seen, last_seen

### User-authored annotations (never written by importers)
- `defect_annotations` — defect_id (PK/FK), description, business_impact, reach, retest_needs, next_step, action_needed, comments, dtco2c (INTEGER 0/1), dtco2c_resp (TEXT), daily (INTEGER 0/1), updated_at
- `spillover_annotations` — spillover_id (PK/FK), importance_for_signoff, next_step, comment_history, critical_for_signoff, comment_for_signoff, signoff_group, updated_at
- `retail_annotations` — retail_id (PK/FK), next_step, comment_history, action_needed, updated_at

### Shared
- `notes` — unified log for ALL entity types (entity_type + entity_id). entity_type values: `defect`, `retail`, `todo`, `followup`, `meeting_prep`, `test_learning`, `test_limitation`, `cs_followup`, `spillover`, `ecom_gatekeeper`, `shelf`, `input` (Inbox — unfiled items use entity_id `'inbox'`)
- `attachments` — files (images and documents) attached to notes. Columns: id, note_id (FK → notes), filename (disk name), original_name, created_at. Actual files live in `data/uploads/`. Many-per-note.
- `order_details` — generic order-number log (mirrors notes pattern). Columns: id, entity_type, entity_id, order_type TEXT, order_number TEXT, comment TEXT, docs_in_s4 INTEGER DEFAULT 0, created_at. Any module can use it: routes `GET/POST /order-details/<entity_type>/<entity_id>[/add]` and `POST /order-details/<detail_id>/update|delete`. Currently used by spillover (entity_type=`'spillover'`). `docs_in_s4` = "docs confirmed in S4" checkbox; green ✓ badge appears on the Order details button in the list when any linked row has it set.
- `defect_notes` — LEGACY, no longer written to, kept for migration only

### ECOM Gatekeeper (manually authored, no importer)
- `ecom_gatekeeper` — id (PK AI), jira_id, solman_id, testcase_name, status (open/inprogress/sf_requested/back_to_sales/tech_check/passed), next_step, created_at. Notes via `notes` (entity_type=`'ecom_gatekeeper'`). Order details via `order_details` (entity_type=`'ecom_gatekeeper'`). Future handover: UPDATE order_details SET entity_type='ecom', entity_id=<ecom_id> to re-point orders to an ECOM test case — no data copy needed.

### Shelf (catch-all store — UI in progress)
- `shelf` — id (PK AI), heading, area (free text), category (free text), created_at. Catch-all for inbox items that don't belong to any specific entity. Notes and attachments link via `notes` (entity_type=`'shelf'`). Filing from inbox creates a new shelf row then re-parents the note. UI (list, detail, combine) is being built — DB table exists as of 2026-06-25.

### Planning & coordination (manually managed via UI)
- `todos` — area, kind, topic, status (open/in_progress/blocked/closed), priority (High/Medium/Low), due_date, for_whom
- `meeting_prep` — meeting (from fixed list), topic, status (planned/discussed/future), note, `overall_topic` (CS Retail/CS ECOM/CS General/ROE Retail/ROE ECOM/ROE General/Orga/AI/Other — nullable), `source_entity_type` (defect/retail/NULL), `source_entity_id` (TEXT PK of source). When set, list view LEFT JOINs defects/retail to show a linked badge. `overall_topic` controls section order in the agenda export.
- `enhancements` — area, enhancement, priority, status (not_started/in_progress/closed) — quick-add via **floating panel** on every page; full sortable list at `/enhancements/page`
- `followups` — with_whom, topic, when_next, status (open/in_progress/done)
- `cs_followups` — area, jira_id, topic, description, next_step, with_whom, status (open/in_progress/done)
- `known_prod_defects` — technical_key, short_description, scenario, description, biz_impact, numbers, refs, next_steps, comments, confluence
- `links` — description, url, area, tool, tags (comma-separated)
- `contacts` — name, email (free text, multiple ok, no validation), area, topic, comments, tags (comma-separated)
- `test_learnings` — channel, topic, learning, scenario, tags
- `test_limitations` — channel, limitation, scenario, comment
- `encouragement_people` — id (PK AI), name (UNIQUE), created_at. One row per person; created automatically on first encouragement.
- `encouragements` — id (PK AI), person_id (FK → encouragement_people), text, date, delivered (INTEGER 0/1 DEFAULT 0), created_at
- `report_comments` — id (PK AI), report (TEXT: `'spillover'`|`'retail'`), comment TEXT, created_at. Free-text bullet points that appear in the **Additional** section at the bottom of the Spillover and Retail status reports. Edited inline at the bottom of `/spillover` and `/retail` list pages. Routes: `POST /report-comments/<report>/add`, `POST /report-comments/<id>/update`, `POST /report-comments/<id>/delete`.

### Migrations (ALTER TABLE, safe to re-run)
- `spillover_annotations`: critical_for_signoff, comment_for_signoff, signoff_group
- `known_prod_defects`: comments, confluence
- `retail_annotations`: action_needed
- `todos`: kind
- `notes`: source
- `meeting_prep`: source_entity_type, source_entity_id, overall_topic
- `defect_annotations`: dtco2c, dtco2c_resp, daily
- `order_details`: order_type, docs_in_s4

---

## All screens (as of 2026-06-23, report_comments added)

### On the dashboard (linked from home cards)
| Screen | URL | Purpose |
|---|---|---|
| Dashboard | `/` | Home — card grid + Run Import button |
| **Inbox** | `/inbox` | Daily capture pad. Paste notes + screenshots during the day; file each item to its target (Defect/Retail/Spillover/Test Learning/Follow-up) when ready. Dashboard card shows pending count. |
| Import Result | POST `/import` | Post-import summary (counts per tab + archive status) |
| Defects List | `/defects` | Filterable defects table (search, channel, status, DTC O2C, **Daily**). Columns: Defect ID, Solman Name, Blocked TCs (links to Retail list), Channel, Status, Priority, Assigned To, Date Reported, Prod, DTC O2C (inline AJAX checkbox), **Daily** (inline AJAX checkbox). Sortable by any column. Horizontally scrollable. **DTC O2C** (`dtco2c`) is a per-defect flag meaning "MB needs to follow up"; **Daily** (`daily`) flags the defect for discussion on the DTC O2C Daily call. Both toggled inline or via detail form. |
| Defect Detail | `/defects/<id>` | Annotations form (incl. DTC O2C checkbox + DTC O2C Responsible field + **To discuss on daily** checkbox) → Notes log → Add to Meeting Prep → Imported fields (read-only, at bottom) |
| **ECOM Gatekeeper** | `/ecom-gatekeeper` | Pre-handoff sense check for ECOM test cases. Fully inline-editable table — all 5 fields (Jira ID, Solman ID, Test case name, Status, Next step) always visible as plain inputs; blur-to-save. Status is a color-coded select (6 values: open → inprogress → sf_requested → back_to_sales → tech_check → passed). Per-row: **Notes** (count badge → detail page), **Orders** (generic order_details popup), **✕** (delete row + notes + orders). **+ Add row** creates a blank row instantly via AJAX. |
| Spillover List | `/spillover` | Horizontally-scrollable frozen-pane table. Frozen: # + Name. Scrollable: Buttons → Status → Next Step (≤3 lines) → Area → Order Numbers (≤3 lines) → Country → Assigned To → Ext. ID → Critical. Per-row buttons: **Details** (Importance, Comment for Sign-Off, Report Group, Next Step), **Order details** (Type · Order Number · Comment · S4 docs checkbox; green ✓ badge on button when any row has `docs_in_s4=1`), **Comments**, **Notes** (count badge). Header: **Status Report** button → `/spillover/report`. |
| Retail List | `/retail` | Filterable table; 3 search boxes; next_step inline edit |
| Retail Detail | `/retail/<id>` | Full test case + annotation form + notes log |
| Meeting Prep | `/meeting-prep` | Per-meeting agenda topics. Columns: Overall Topic (inline select), Topic (inline editable), Status, note, notes. Topic column shows coloured badge (purple=defect, green=retail) when added from a detail page. Default filter: planned. Export agenda button opens `/meeting-prep/agenda` (styled HTML report); Copy to clipboard exports plain text — both sorted by overall_topic order. |
| To-Do List | `/todos` | Tasks with priority, kind, due date, owner, status |
| Follow-ups | `/followups` | Lightweight "chase" list per person; Notes button links to Follow-up Detail page |
| Links | `/links` | URL bookmark store with area/tool/tag filters |
| Contacts | `/contacts` | Contact directory — name, email, area, topic, comments, tags; filterable |
| CS Follow-Up Tracker | `/cs_followups` | Richer follow-ups for Core South sign-off |
| **Encouragements** | `/encouragements` | Record positive observations about people. Person autocomplete (`<datalist>` from `encouragement_people`); entries have date, text, delivered flag (AJAX toggle), copy-to-clipboard, delete. Dashboard card shows undelivered count. |
| **Enhancements** | `/enhancements/page` | Full sortable list of all enhancement ideas. Sortable by priority/status/area. Inline edit and delete per row. Dashboard card (bottom-right) shows open count. |

### NOT on the dashboard (linked from other screens)
| Screen | URL | How to reach |
|---|---|---|
| Retail Status Report | `/retail/report` | Link in Retail list header. Includes: bucket overview, in-progress breakdown, **active Retail defects table** (all non-confirmed/withdrawn, with MB Blocked / Sales Blocked columns split by `dtco2c`), **Attribution Overview** (Back with Sales = Sales defects + other; Blocked Tech Team = MB defects + other/untracked), diagnostics. |
| Spillover Status Report (select) | `/spillover/report` | "Status Report" button in Spillover list header. Select rows to include; rows persist in `spillover_report_selection`; batch select-page / clear-all. |
| Spillover Status Report (view) | `/spillover/report/view` | "View Report" button on the select screen (opens new tab). Title: **Spillover Status Report — from DTC Perspective**. Standalone printable HTML. Items sorted critical-first (Yes → Slightly → No → unset). Per-item card: dark header (green for Passed/Passed-pending-solman items with 🎉 icon), metadata strip (Area · Status · Critical), next step, order details table with S4 docs ✓. Summary stats in header. **"Closed this round" wins section** at the bottom lists all passed items. Download PDF + Download HTML + Print + **Copy for Teams** (Teams-formatted markdown). |
| Retail Spillover Report | `/report/retail` | Link in Spillover list header |
| ECOM/Omni Spillover Report | `/report/ecom` | Link in Spillover list header |
| Meeting Agenda | `/meeting-prep/agenda` | "Export agenda" button on Meeting Prep (respects meeting + status filters) |
| Production Defects List | `/prod_defects` | Link in Spillover list header |
| Production Defect Detail | `/prod_defects/<id>` | From prod defects list |
| Test Learnings | `/test_learnings` | Link in Retail list header |
| Test Learning Detail | `/test_learnings/<id>` | From Test Learnings list — full field display + complete notes module (heading, edit, delete, file attachments, Ctrl+V paste) |
| Test Limitations | `/test_limitations` | Link in Retail list header |
| ECOM Gatekeeper Detail | `/ecom-gatekeeper/<id>` | From Notes button on Gatekeeper list — shows Jira ID, Solman ID, Status, Next step (read-only) + full notes module (heading, edit, delete, file attachments, Ctrl+V paste). Note routes: `/ecom-gatekeeper/<id>/notes/add\|edit\|delete`. |
| Spillover Detail | `/spillover/<id>` | From Notes button on Spillover list — read-only field display + complete notes module (heading, edit, delete, file attachments, Ctrl+V paste) |
| Follow-up Detail | `/followups/<id>` | From Notes button on Follow-ups list — field display + inline status dropdown + complete notes module (heading, edit, delete, file attachments, Ctrl+V paste) |
| DTC O2C Daily Agenda | `/meeting-prep/dtco2c-daily` | "DTC O2C Daily Agenda" button in Meeting Prep header. Three sections: (1) planned topics for the DTC O2C Daily meeting grouped by overall_topic, (2) all defects with `daily=1` (Defect ID, Solman Name, Channel, Next Steps), (3) open follow-ups where `with_whom = 'DTC O2C'`. Standalone HTML page; Download HTML + Print. |

### Shared sub-screens (note forms)
- Note add/edit/delete for Defects: `/defects/<id>/notes/...`
- Note add/edit/delete for Retail: `/retail/<id>/notes/...`
- Note add/edit/delete for Test Learnings: `/test_learnings/<id>/notes/...`
- Note add/edit/delete for Spillover: `/spillover/<id>/notes/...`
- Note add/edit/delete for Follow-ups: `/followups/<id>/notes/...`

### File attachments (Defects, Retail, Test Learnings, Spillover, Follow-up, ECOM Gatekeeper, Inbox)
- `GET /uploads/<filename>` — serve a stored file
- `POST /notes/<note_id>/attachments/add` — upload a file (multipart, field: `file`). Saves to `data/uploads/<note_id>_<timestamp>_<name>`. Returns JSON `{ok, attachment}`.
- `POST /notes/<note_id>/attachments/<attachment_id>/delete` — delete DB record + disk file. Returns JSON `{ok}`.
- Allowed images (shown as thumbnails): `.png .jpg .jpeg .gif .webp`
- Allowed documents (shown as download links): `.pdf .doc .docx .xls .xlsx .ppt .pptx .txt .csv .msg .eml .zip`
- Both types share the same `attachments` table and `data/uploads/` folder.
- **📷 Add screenshot** button — image picker (image/* filter). **📎 Attach file** button — document picker (above extensions). Both use the same AJAX upload route.
- **Ctrl+V paste** supported: hover a note, then Ctrl+V pastes a Snipping Tool image directly into it (images only).

### Global widget (every page)
- **Enhancements floating panel** — bottom-right corner, AJAX-driven quick-add; full list and edit at `/enhancements/page`

---

## Known navigation gaps (vision items for future work)

1. **Two follow-up trackers** — `followups` (general, lightweight) and `cs_followups` (CS-specific, richer) overlap. The split should be made clearer or consolidated.
2. **No cross-links between related entities** — a Retail row's `defect_id_ref` is not a clickable link to the Defect detail.

*Resolved gaps (no longer open):*
- ~~Enhancements had no full-page view~~ — `/enhancements/page` now exists, linked from dashboard card.
- ~~Test Learnings, Test Limitations, Prod Defects, Sign-Off Reports not reachable~~ — all are linked from the Retail or Spillover list headers; nothing is URL-only.

---

## Key files

| File | Purpose |
|---|---|
| `app/web.py` | All Flask routes — the only place HTML responses are assembled |
| `app/database.py` | All SQL — the ONLY module that writes to the DB |
| `app/importer.py` | Orchestrates all three importers in sequence |
| `app/read_defects.py` | Defects importer |
| `app/spillover_importer.py` | Spillover importer |
| `app/retail_importer.py` | Retail importer |
| `app/reporter.py` | Computes retail bucket counts from status_mappings.yaml |
| `app/pdf_utils.py` | Reusable PDF helper — `render_pdf(html, filename) → Response`. Used by all report PDF routes; lazily imports WeasyPrint so app starts without it installed |
| `app/config_loader.py` | Loads settings.yaml |
| `app/templates/base.html` | Shared layout + Enhancements floating panel |
| `config/settings.yaml` | File paths, sheet names, hidden statuses |
| `config/status_mappings.yaml` | Retail report bucket definitions |
| `data/test_coordination.db` | SQLite database |
| `data/uploads/` | Files (images and documents) attached to notes (served via `/uploads/<filename>`) |
| `output/retail_report_log.xlsx` | Appended by "Save to Excel" on the retail report |
| `docs/database_schema.html` | Visual DB schema documentation |
| `docs/screens_visual.html` | Visual screen reference with real screenshots |
| `docs/tech_backlog.md` | Technical backlog: known deferrals, refactor plans, future work |

---

## Output / reports
- **Retail Status Report** (`/retail/report`) — live bucket counts; "Save to Excel" appends a row to `output/retail_report_log.xlsx`; "Download HTML" gives a dated standalone snapshot; **"Download PDF"** generates an A4 PDF via WeasyPrint (`/retail/report/pdf`)
- **Spillover Status Report** (`/spillover/report/view`) — **"Download PDF"** generates an A4 PDF via WeasyPrint (`/spillover/report/pdf`); passed items celebrated with green header + 🎉 icon + "Closed this round" wins summary
- **Retail Spillover Sign-Off Report** (`/report/retail`) — spillover items grouped by critical_for_signoff, Retail areas only
- **ECOM/Omni Sign-Off Report** (`/report/ecom`) — same format, ECOM/Omni areas + Known Production Defects section

---

## Central notes module — the one rule that must always be followed

There is **one and only one notes table** in the entire application: `notes`.

Every module that needs a notes log — defects, retail, todos, follow-ups, meeting prep,
test learnings, test limitations, cs_followups, and any future module — MUST write to this
single table. Never create a module-specific notes table.

**Schema:**
```
notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,   -- e.g. 'defect', 'retail', 'todo', 'cs_followup', ...
    entity_id   TEXT NOT NULL,   -- TEXT representation of the parent row's PK
    created_at  TEXT NOT NULL,   -- ISO datetime
    heading     TEXT,
    note        TEXT,
    source      TEXT             -- optional: who/what added it
)
```

**Special case — Inbox (`entity_type='input'`, `entity_id='inbox'`):**
Unfiled inbox items live in the notes table with these sentinel values. Filing is one `UPDATE notes SET entity_type=?, entity_id=?` — the row ID never changes so attachments follow automatically. Use `database.add_inbox_item`, `database.list_inbox_items`, `database.file_inbox_item`, `database.delete_inbox_item`.

**When implementing notes for any new module:**
- Use `database.add_note(conn, entity_type, entity_id, heading, note_text)`
- Use `database.list_notes(conn, entity_type, entity_id)` to fetch
- The `entity_type` string should match the module name (e.g. `'ecom'`, `'omni'`)
- Never create a new table. Never bypass `database.py` for note writes.

This has been implemented inconsistently in the past — some modules got it right, some did not.
Always check that new note functionality routes through the shared `notes` table.

---

## Planned future integrations

### Jira integration (future)
The goal is to pull Jira ticket data into the same tool so that Excel-tracked items and
Jira tickets can be viewed side by side — one unified view of all UAT work items.

**Design intent:**
- A new Jira importer (similar in pattern to the Excel importers) will fetch data via the Jira API
- Jira data will live in its own table(s), never merged directly into Excel-sourced tables
- The UI should allow viewing/linking both sources for the same work item
- The `cs_followups.jira_id` field is the first step — a manual link; the full integration will make it live

---

## Context: why this exists

Marina is a chaos coordinator for a retail system (SAP S/4) UAT. The project involves multiple
countries and workstreams (Retail, Core South, ECOM, Omni). The tool tracks:
- Defect status from SolMan (via Excel export)
- Spillover items needing sign-off decision
- Retail / ECOM / Omni test-case execution progress (ECOM and Omni verticals coming)
- Personal coordination: meetings, tasks, follow-ups, links, learnings
- Future: Jira ticket data merged into the same view

The Excel file is managed by the whole team; this tool is Marina's personal read layer on top of it.
