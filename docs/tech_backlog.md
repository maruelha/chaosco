# Technical Backlog

Architectural improvements and future work. Items here are known, deliberate deferrals —
not bugs, not forgotten, just not worth blocking today's demo.

---

## Refactors

### Notes module — consolidate into shared components ✅ DONE 2026-07-04 (refactoring step 3)
**Priority:** Do before adding notes to any further module (ECOM, Omni, etc.)

The database layer is already correct — one central `notes` table, all writes through
`database.add_note()` / `database.list_notes()`. But the **web layer is copy-pasted**:

- Each module has its own note routes in `web.py` (defect notes, retail notes, etc.)
- Each detail template repeats the same HTML block (note list + attachment thumbnails + upload button)
- The attachment JS is inlined in `defect_detail.html` and `retail_detail.html` separately

**Target state:**
- `app/templates/_notes_section.html` — shared Jinja2 include/macro for the full notes block
- `app/static/notes.js` — shared JS for attachment upload, delete, and Ctrl+V paste
- Generic note routes in `web.py` (one set for all entity types, `back_url` as a param)
- All detail pages just `{% include '_notes_section.html' %}` with a few variables

Adding notes to ECOM, Omni, or any future module then becomes: two template lines, done.

---

## Current notes coverage

| Module | Notes? | Where | Heading + Text? | Edit/Delete? | Screenshots? |
|---|---|---|---|---|---|
| Defects | ✅ Full | Detail page | Yes | Yes | Yes |
| Retail test cases | ✅ Full | Detail page | Yes | Yes | Yes |
| To Dos | ⚠️ Inline | Expand row in list | No | No | No |
| Follow ups | ⚠️ Inline | Expand row in list | No | No | No |
| Meeting Prep | ⚠️ Inline | Expand row in list | No | No | No |
| CS Follow-up Tracker | ⚠️ Inline | Expand row in list + detail | No | No | No |
| Test Learnings | ⚠️ Inline | Expand row in list + detail | No | No | No |
| Test Limitations | ⚠️ Inline | Expand row in list + detail | No | No | No |
| Core South Spillover | ⚠️ Inline | Detail page (link from list) | Yes | Yes | Yes |
| Known Production Defects | ✅ Full (2026-07-13) | Detail page | Yes | Yes | Yes |

The "inline" modules have a quick-add textarea but no heading, no edit, no delete,
no screenshots. They were built as convenience shortcuts, not as the full notes module.

**After refactor:** all modules can be upgraded to full notes (heading, text, edit,
delete, screenshots) by plugging in the shared include — no per-module work.

---

## Split CLAUDE.md by vertical ✅ DONE 2026-07-04 (docs/claude/*)

When ECOM/Omni are added, CLAUDE.md will become genuinely bloated. At that point split into:

- `CLAUDE.md` — architecture rules, stack, key files, non-negotiables (always loaded, lean)
- `docs/claude/defects.md` — defects importer, tables, screens, DTC O2C / MB logic
- `docs/claude/retail.md` — retail importer, tables, screens, retail report
- `docs/claude/ecom.md` — ECOM vertical
- `docs/claude/omni.md` — Omni vertical
- `docs/claude/coordination.md` — todos, followups, meeting prep, links, test learnings, etc.

At session start, read only the vertical file(s) relevant to the task.

---

## Planned verticals

### ECOM vertical
Same pattern as Retail: new importer, new `ecom` table, `ecom_annotations` table,
Retail UI screens as template. Excel tab name TBD.

### Omni vertical
Same pattern as Retail and ECOM.

---

## Navigation gaps (known, low priority)

1. Dashboard missing links to: Test Learnings, Test Limitations, Prod Defects, Sign-Off Reports
2. Two follow-up trackers (`followups` + `cs_followups`) — purpose overlap, needs clarification
3. ~~No Spillover detail page~~ — **resolved**: `/spillover/<id>` detail page added with read-only fields + full notes module (screenshots, Ctrl+V paste)
4. `defect_id_ref` on Retail rows is not a clickable link to the Defect detail
5. Sign-off reports only reachable by direct URL

---

## Report export → PowerPoint (PDF retired 2026-06-25)

**PDF export via WeasyPrint is retired.** WeasyPrint's native GTK libraries (GObject,
Pango, Cairo) could not load on the target Windows machine, so every PDF route errored;
the output was also poor. WeasyPrint (and a Playwright/Chromium experiment) was uninstalled
and removed from `requirements.txt`.

**Retail Status Report PPT — ✅ DONE (2026-06-26)**
- `GET /retail/report/ppt` is live. Logic in `app/ppt_builder.py` (`build_retail_ppt()`).
- Direct-build approach (no external template): all shapes drawn via `python-pptx`. Slide 1:
  stats strip + 4 overview cards + 5 breakdown cards with emoji icons + comments box.
  Slide 2+: blocked-defects table (12 rows/slide) + 3 summary cards.
- The "Download PDF" button on the Retail report is now "Download PPT".
- `python-pptx>=1.0` is in `requirements.txt`.

**Spillover Status Report PPT — ✅ DONE (2026-06-26)**
- `GET /spillover/report/ppt` is live. Logic in `app/ppt_spillover.py` (`build_spillover_ppt()`).
- Header with stat chips (Open · Critical · Slightly · Non-Critical). Items grouped by
  criticality with coloured section banners. Status badge from `spillover.status` field.
  Order numbers on the right. Paginated with orphan-banner prevention.
- The "Download PDF" button on the Spillover report view is now "Download PPT".

**PPT layer refactored (2026-06-26)**
- `app/ppt_utils.py` — shared palette, fonts, dims, drawing primitives. Each builder
  imports what it needs and can override locally for a different look.
- `app/ppt_retail.py` — retail builder (renamed from `ppt_builder.py`)
- `app/ppt_spillover.py` — spillover builder

**Still non-functional / to do:**
- `app/pdf_utils.py` — `render_pdf()` / `save_pdf()` (kept until cleaned up)
- `GET /spillover/report/pdf` — dead route pointing to WeasyPrint; remove when convenient
- `POST /export-reports` (dashboard "Export Reports" button) — still calls the retired PDF step,
  so the button currently errors. Planned rework: write `.html` + `.pptx` for both reports.

**To complete:**
1. Rework `app/report_exporter.py` to write `.html` + `.pptx` (drop the PDF step).
2. Remove the dead `GET /spillover/report/pdf` route.
3. Browser **Print → Save as PDF** on any report HTML remains the manual PDF fallback.

---

## Inbox: attach screenshot without creating a note first (maybe)

Currently you must save a note before you can attach a file, because the `attachments`
table references `note_id` — a database-generated PK that doesn't exist until the INSERT runs.

The UX friction: to add a quick screenshot you have to type something in the note field first,
even if a heading alone would be enough.

**Best option if this gets built:** silent AJAX create — the Save button fires a `fetch()` to
create the note, gets the `note_id` back, then opens the file picker immediately. From the
user's perspective it's one action. The rest of the form/attachment system stays unchanged.

**Why it's a maybe:** the current two-step flow (save → attach) is fine once you know about it,
and the fix adds meaningful JS complexity. Low priority unless the friction becomes annoying.

---

## Remove the one-time dep-cleanup block from run_web.bat ✅ DONE 2026-07-04

`run_web.bat` has a guarded block that uninstalls the abandoned PDF deps
(`weasyprint`, `playwright`, and their orphans) on launch — it only acts when a package is
present and is a silent no-op afterwards. **Delete this block once every machine that runs
the app has launched at least once** so the startup script stays clean.

---

## Shelf — catch-all note store (in progress 2026-06-25)

DB table `shelf` exists. UI (list `/shelf`, detail `/shelf/<id>`, inbox filing, combine) is being built in steps. See plan in conversation history.

---

## Future integrations

### Jira integration
Pull Jira ticket data via API into its own table(s). View/link alongside Excel-sourced items.
`cs_followups.jira_id` is the first manual link; full integration makes it live.
Design rule: Jira data lives in its own tables, never merged into Excel-sourced tables.
