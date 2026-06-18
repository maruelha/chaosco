# Technical Backlog

Architectural improvements and future work. Items here are known, deliberate deferrals —
not bugs, not forgotten, just not worth blocking today's demo.

---

## Refactors

### Notes module — consolidate into shared components
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
| Core South Spillover | ❌ Missing | — | — | — | — |
| Known Production Defects | ❌ Missing | — | — | — | — |

The "inline" modules have a quick-add textarea but no heading, no edit, no delete,
no screenshots. They were built as convenience shortcuts, not as the full notes module.

**After refactor:** all modules can be upgraded to full notes (heading, text, edit,
delete, screenshots) by plugging in the shared include — no per-module work.

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

## Future integrations

### Jira integration
Pull Jira ticket data via API into its own table(s). View/link alongside Excel-sourced items.
`cs_followups.jira_id` is the first manual link; full integration makes it live.
Design rule: Jira data lives in its own tables, never merged into Excel-sourced tables.
