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

## All database tables (as of 2026-06-19)

### Imported (written by importers only)
- `defects` — 21 columns incl. defect_id (PK), channel, solman_status, priority, assigned_to, excel_row, first_seen, last_seen
- `spillover` — spillover_id (PK AI), type, name, country, area, status, assigned_to, external_id, order_numbers, content, comment, excel_row, match_key (UNIQUE), first_seen, last_seen
- `retail` — retail_id (PK AI), test_case_id, country, testcase_name, testcase_scenario, status, assigned_to, key_user_responsible, evidence_in_sharepoint, sales_file, execution_started, execution_completed, order_number, old_order_numbers, defect_id_ref, s4_sales_order, s4_billing_documents, s4_journal_invoice_entry, delivery_note, comment, reason_for_pass_with_reservation, excel_row, match_key (UNIQUE), first_seen, last_seen

### User-authored annotations (never written by importers)
- `defect_annotations` — defect_id (PK/FK), description, business_impact, reach, retest_needs, next_step, action_needed, comments, dtco2c (INTEGER 0/1), dtco2c_resp (TEXT), updated_at
- `spillover_annotations` — spillover_id (PK/FK), importance_for_signoff, next_step, comment_history, critical_for_signoff, comment_for_signoff, signoff_group, updated_at
- `retail_annotations` — retail_id (PK/FK), next_step, comment_history, action_needed, updated_at

### Shared
- `notes` — unified log for ALL entity types (entity_type + entity_id). entity_type values: `defect`, `retail`, `todo`, `followup`, `meeting_prep`, `test_learning`, `test_limitation`, `cs_followup`, `spillover`
- `attachments` — image files attached to notes. Columns: id, note_id (FK → notes), filename (disk name), original_name, created_at. Actual files live in `data/uploads/`. Many-per-note.
- `defect_notes` — LEGACY, no longer written to, kept for migration only

### Planning & coordination (manually managed via UI)
- `todos` — area, kind, topic, status (open/in_progress/blocked/closed), priority (High/Medium/Low), due_date, for_whom
- `meeting_prep` — meeting (from fixed list), topic, status (planned/discussed/future), note, `overall_topic` (CS Retail/CS ECOM/CS General/ROE Retail/ROE ECOM/ROE General/Orga/AI/Other — nullable), `source_entity_type` (defect/retail/NULL), `source_entity_id` (TEXT PK of source). When set, list view LEFT JOINs defects/retail to show a linked badge. `overall_topic` controls section order in the agenda export.
- `enhancements` — area, enhancement, priority, status (not_started/in_progress/closed) — shown in a **floating panel** on every page, not a separate screen
- `followups` — with_whom, topic, when_next, status (open/in_progress/done)
- `cs_followups` — area, jira_id, topic, description, next_step, with_whom, status (open/in_progress/done)
- `known_prod_defects` — technical_key, short_description, scenario, description, biz_impact, numbers, refs, next_steps, comments, confluence
- `links` — description, url, area, tool, tags (comma-separated)
- `contacts` — name, email (free text, multiple ok, no validation), area, topic, comments, tags (comma-separated)
- `test_learnings` — channel, topic, learning, scenario, tags
- `test_limitations` — channel, limitation, scenario, comment

### Migrations (ALTER TABLE, safe to re-run)
- `spillover_annotations`: critical_for_signoff, comment_for_signoff, signoff_group
- `known_prod_defects`: comments, confluence
- `retail_annotations`: action_needed
- `todos`: kind
- `notes`: source
- `meeting_prep`: source_entity_type, source_entity_id, overall_topic
- `defect_annotations`: dtco2c, dtco2c_resp

---

## All screens (as of 2026-06-19)

### On the dashboard (linked from home cards)
| Screen | URL | Purpose |
|---|---|---|
| Dashboard | `/` | Home — card grid + Run Import button |
| Import Result | POST `/import` | Post-import summary (counts per tab + archive status) |
| Defects List | `/defects` | Filterable defects table (search, channel, status, DTC O2C). Columns: Defect ID, Solman Name, Blocked TCs (links to Retail list), Channel, Status, Priority, Assigned To, Date Reported, Prod, DTC O2C (inline AJAX checkbox). Sortable by any column. Horizontally scrollable. **DTC O2C** (`dtco2c`) is a per-defect flag meaning "MB needs to follow up"; toggled inline or via detail form. |
| Defect Detail | `/defects/<id>` | Annotations form (incl. DTC O2C checkbox + DTC O2C Responsible field) → Notes log → Add to Meeting Prep → Imported fields (read-only, at bottom) |
| Spillover List | `/spillover` | Frozen-pane table; all edits inline via AJAX. Each row has a **Notes** button (shows count badge) linking to the Spillover Detail page. |
| Retail List | `/retail` | Filterable table; 3 search boxes; next_step inline edit |
| Retail Detail | `/retail/<id>` | Full test case + annotation form + notes log |
| Meeting Prep | `/meeting-prep` | Per-meeting agenda topics. Columns: Overall Topic (inline select), Topic (inline editable), Status, note, notes. Topic column shows coloured badge (purple=defect, green=retail) when added from a detail page. Default filter: planned. Export agenda button opens `/meeting-prep/agenda` (styled HTML report); Copy to clipboard exports plain text — both sorted by overall_topic order. |
| To-Do List | `/todos` | Tasks with priority, kind, due date, owner, status |
| Follow-ups | `/followups` | Lightweight "chase" list per person |
| Links | `/links` | URL bookmark store with area/tool/tag filters |
| Contacts | `/contacts` | Contact directory — name, email, area, topic, comments, tags; filterable |
| CS Follow-Up Tracker | `/cs_followups` | Richer follow-ups for Core South sign-off |

### NOT on the dashboard (URL only / linked from other screens)
| Screen | URL | How to reach |
|---|---|---|
| Retail Status Report | `/retail/report` | Link in Retail list header. Includes: bucket overview, in-progress breakdown, **active Retail defects table** (all non-confirmed/withdrawn, with MB Blocked / Sales Blocked columns split by `dtco2c`), **Attribution Overview** (Back with Sales = Sales defects + other; Blocked Tech Team = MB defects + other/untracked), diagnostics. |
| Retail Spillover Report | `/report/retail` | Link in Retail list header |
| ECOM/Omni Spillover Report | `/report/ecom` | URL only |
| Meeting Agenda | `/meeting-prep/agenda` | "Export agenda" button on Meeting Prep (respects meeting + status filters) |
| Production Defects List | `/prod_defects` | URL only |
| Production Defect Detail | `/prod_defects/<id>` | From prod defects list |
| Test Learnings | `/test_learnings` | URL only |
| Test Learning Detail | `/test_learnings/<id>` | From Test Learnings list — full field display + complete notes module (heading, edit, delete, screenshot attachments, Ctrl+V paste) |
| Test Limitations | `/test_limitations` | URL only |
| Spillover Detail | `/spillover/<id>` | From Notes button on Spillover list — read-only field display + complete notes module (heading, edit, delete, screenshot attachments, Ctrl+V paste) |

### Shared sub-screens (note forms)
- Note add/edit/delete for Defects: `/defects/<id>/notes/...`
- Note add/edit/delete for Retail: `/retail/<id>/notes/...`
- Note add/edit/delete for Test Learnings: `/test_learnings/<id>/notes/...`
- Note add/edit/delete for Spillover: `/spillover/<id>/notes/...`

### Screenshot attachments (Defects, Retail, Test Learnings, Spillover detail pages)
- `GET /uploads/<filename>` — serve a stored image file
- `POST /notes/<note_id>/attachments/add` — upload image (multipart, field: `file`). Saves to `data/uploads/<note_id>_<timestamp>_<name>`. Returns JSON `{ok, attachment}`.
- `POST /notes/<note_id>/attachments/<attachment_id>/delete` — delete DB record + disk file. Returns JSON `{ok}`.
- Allowed: `.png .jpg .jpeg .gif .webp`
- **Ctrl+V paste** supported: hover a note, then Ctrl+V pastes a Snipping Tool image directly into it.

### Global widget (every page)
- **Enhancements floating panel** — bottom-right corner, AJAX-driven, no separate page

---

## Known navigation gaps (vision items for future work)

1. **Dashboard is incomplete** — Test Learnings, Test Limitations, Prod Defects, and the Sign-Off Reports are not reachable from home. Users must know the URL.
2. **Two follow-up trackers** — `followups` (general, lightweight) and `cs_followups` (CS-specific, richer) overlap. The split should be made clearer or consolidated.
3. **No cross-links between related entities** — a Retail row's `defect_id_ref` is not a clickable link to the Defect detail.
4. **Sign-off reports are hard to find** — they should be reachable from the dashboard or a dedicated Reports section.

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
| `app/config_loader.py` | Loads settings.yaml |
| `app/templates/base.html` | Shared layout + Enhancements floating panel |
| `config/settings.yaml` | File paths, sheet names, hidden statuses |
| `config/status_mappings.yaml` | Retail report bucket definitions |
| `data/test_coordination.db` | SQLite database |
| `data/uploads/` | Screenshot/image files attached to notes (served via `/uploads/<filename>`) |
| `output/retail_report_log.xlsx` | Appended by "Save to Excel" on the retail report |
| `docs/database_schema.html` | Visual DB schema documentation |
| `docs/screens_visual.html` | Visual screen reference with real screenshots |
| `docs/tech_backlog.md` | Technical backlog: known deferrals, refactor plans, future work |

---

## Output / reports
- **Retail Status Report** (`/retail/report`) — live bucket counts; "Save to Excel" appends a row to `output/retail_report_log.xlsx`; "Download HTML" gives a dated standalone snapshot
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
