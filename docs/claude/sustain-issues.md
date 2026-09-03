# Sustainphase Issues (`/sustain-issues/`)

**Type:** mini app
**URL:** `/sustain-issues/` · `/sustain-issues/solutions` · `/sustain-issues/totals` (+ `/download`) · `/sustain-issues/report` (+ `/download`)
**Storage:** `app/db/sustain_issues.py` → `sustain_incidents`, `sustain_incident_comments`, `sustain_incident_annotations`, `sustain_issue_solutions`, `sustain_interfaces`; notes in the shared `notes` table, entity `('sustain_incident', <incident number>)`
**Routes:** `app/web_sustain_issues.py`; importer `app/sustain_issues_importer.py`
**Templates:** `sustain_issues.html` · `sustain_solutions.html` · `sustain_totals.html` · `sustain_incidents_report.html` · `_sustain_report.css.html` (shared inline CSS of the two reports)
**Tests:** `tests/test_sustain_issues_importer.py`, `tests/test_sustain_issues_storage.py`, `tests/test_sustain_issues_web.py`, `tests/test_search_new_sources.py`

## Purpose

The go-live incident list for the sustain phase, imported from the
**Go-Live defect tracker** workbook (rewritten 2026-09-03 [USER] — the
2026-08-28 version read the Defects tab of `DTC_Sustainphase_Tracking`,
see "History" below). Sits next to Sustainphase Monitoring and Smoke
Testing on the dashboard but is deliberately NOT linked to them [USER].

## Source workbook — `Go-Live defect tracker[ (n)].xlsx`

Upload: file picker on the card, filename must **contain** `Go-Live
defect tracker` (case-insensitive; browser " (1)" copies work), dated
copy `data/uploads/sustain_issues_*.xlsx`. **One tab = one importer + one
table** (import pattern); columns are mapped by NORMALIZED HEADER NAME
PREFIX, never by position. Empty tabs import fine (the template starts
empty). A sample without data lives in `Download/`.

| Tab | Headers (row 1 unless noted) | Table | Rule |
|---|---|---|---|
| `ASPEN Incidents` | Incident Number · Date · Requestor · Title · Status · Assigned To · Latest comment/action | `sustain_incidents` (+ `sustain_incident_comments`) | **upsert by Incident Number**; rows without one are SKIPPED and counted in the flash message [USER] |
| `Issue Solution tracker` | Owner · Interface · Msg · Text · External Reference · INC reference, if any · Reason · Solution · Status (+ an unnamed 10th column, ignored) | `sustain_issue_solutions` | **replaced wholesale** per upload — rows have no identity, the page is read-only |
| `Total` | group titles on row 2, the list header (Namespace · Interface · Version · Name · Variant in /aif/err · Index tables) on **row 3** — located by its "Namespace" cell, not assumed | `sustain_interfaces` | replaced per upload; the sheet's own "Total Issue #" column is IGNORED — totals are computed (below) |

## Column G is a HISTORY (2026-09-03 [USER])

[USER: "check if there is a new text - and then add on top instead of
overwriting every time (but of course if it is the same text it should
remain the same)"]. `upsert_incidents` compares the row's "Latest
comment/action" (whitespace-collapsed) with the NEWEST stored entry for
that incident: different → a new `sustain_incident_comments` row with
`first_seen` = upload time; same → nothing. Going back to an older text
counts as a change (it is a new latest text). The board shows the newest
entry highlighted, the older ones below it, each with its first-seen
date. The flash message counts "n new comments".

## Board — `/sustain-issues/`

Expandable rows (kpd pattern), every ASPEN column: summary = incident
number · title · status chip · notes badge · next-step preview · date /
requestor / assignee; body = the meta line (incl. first/last seen), the
comment history, the **next step** (inline save `POST
/sustain-issues/incident/<no>/next-step`, ↻ archive / 🕘 history via
the generic component, registry entity `sustain_incident`), and the
**shared notes component** (headings, text, 📷/📎 attachments, Ctrl+V;
`web_notes.REGISTRY['sustain_incident']`, list-only, `notes_return_to=
'list'`, 404 guard = the incident must exist). Filters (client-side):
a text box over incident number + title, dropdowns Requestor / Status /
Assigned to from the values in use, Clear. Buttons in the header: 🧩
Issue solutions, Σ Totals, the upload.

## Issue Solution tracker — `/sustain-issues/solutions`

[USER: "on another page just a simple table not any edit possibility"]:
one `rt-table`, all nine columns. Filters: dropdowns for every heading
EXCEPT Text / Reason / Solution, which share ONE text search [USER];
client-side, rows carry `data-*` + a lowercased `data-search`.

## Totals — `/sustain-issues/totals`

[USER: "the total number should be calculated - the number of rows where
value in Interface on Issue Solution tracker match"; "two totals - one
with match of all lines - one only with the open ones"; "n/a … should be
a separate row … just so the totals add up"; "also a total report on the
reason"]. `db_sustain_issues.interface_totals` / `reason_totals` (pure
over the two tables, tested):

- per listed interface: **Total (all)** = tracker rows whose Interface
  equals it (Interface column ONLY, case-insensitive, whitespace-trimmed)
  and **Total (open)** = the same over rows whose Status is not in
  `SOLUTION_CLOSED_STATUSES` (closed / done / resolved / solved /
  completed / fixed — adjust there if the team's wording differs);
- tracker interfaces on NO listed row ("n/a", a new one) → extra rows
  "(not on the Total tab)" at the bottom, so the grand total equals the
  tracker's row count;
- a grand-total row, and the same two numbers per **Reason** ("(blank)"
  for empty reasons), most frequent first.

**Click a line → its rows + copy; the page IS a report (2026-09-03, second
round [USER: "click on a line and get the rows shown that applies to -
and to be able to copy it somewhere"; "the totals would love to have a
report"])**: `sustain_totals.html` is a standalone template in the
delegated-report pattern — but WITHOUT the button toolbar [USER 2026-09-03:
"the buttons on the top of the report make NO sense at all"]: the only
control is a text "⬇ Download HTML" link in the header line (screen only).
Every interface / extra / reason line is a plain `<details>`; open it and
the tracker rows behind the number appear as a table (open rows first —
`_solutions_with_open_flag`, attached as `solutions` on every totals
row). **⎘ Copy rows** per block (screen only) writes two clipboard
flavors — the table as HTML (Teams / Outlook / Word keep it a table) and
tab-separated text (Excel pastes into cells). The download keeps the
click-to-open (no script needed) and drops the download link + copy
buttons; a browser print shows only the opened lines. `GET /sustain-issues/totals/download`,
Email Reports choice `sustain_totals`.

## ASPEN incidents report — `/sustain-issues/report` (2026-09-03 [USER])

[USER: "the board is good for checking - but not so good for scanning"]:
a table-style standalone report (`sustain_incidents_report.html`,
`incidents_report_context`), one row per incident — Incident · Date ·
Requestor · Title · Assigned to · Latest comment/action — **grouped by
Status** (`db_sustain_issues.incidents_by_status`: groups in order of
first appearance over the date-desc list, "(no status)" last), **newest
comment only**, **no next step** [USER: "leave next step out for now"].
No button toolbar (same [USER] call as on Totals) — a text "⬇ Download
HTML" link in the header line and a plain screen-only filter row
(incident/title text, Requestor, Assigned to, Clear).
`/report/download` = dated standalone file (link + filters dropped),
Email Reports choice `sustain_incidents`. Button 📄 Incidents report in
the board header; the board keeps the full history + notes.

## Search + dashboard

Global 🔍 block "Sustainphase Issues": incident number + title
(`LOWER(...) LIKE LOWER(?)`), hits open the board. Dashboard card badge
= `incident_count`.

## History

- **2026-08-28 → 2026-09-03: the Defects-tab model.** The first build
  imported the Defects tab of `DTC_Sustainphase_Tracking….xlsx` into
  `sustain_issues` with SUS-nnn placeholders promoted to ASPEN ids, plus
  a call-outs textarea. Replaced on 2026-09-03 [USER: "replace"] when the
  real tracker turned out to be the Go-Live defect tracker; the old
  tables may still exist in DB files created before that — unused,
  untouched, droppable (MarinaCheckSoon). The next-step archive entity
  `sustain_issue` became `sustain_incident`; old archived next steps
  under the former entity are not migrated (the old keys were ASPEN
  defect ids, not incident numbers).

## Related

`[[sustain]]` · `[[smoke]]` · `[[notes]]` · `[[next-steps]]` · `[[search]]`
