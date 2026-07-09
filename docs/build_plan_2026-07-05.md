# Build Plan — 2026-07-05 · ECOM Gatekeeper v2 + ECOM vertical

Say **"do step N"** — each step is built, tested, and verified before the
next. Master backlog: `docs/build_plan.md`. HTML version for review:
`docs/build_plan_2026-07-05.html`.

**Clean-build rules for every step** (same as the whole refactor):
own storage module + Blueprint per card (no growth of existing files),
imported data strictly separated from authored data, UI assembled from the
shared components/macros, tests written with the logic, docs updated per
step, one commit per step — all tests green before it.

---

## Step 1 — Order-details drop-in component  *(prerequisite for step 4)*

Extract the Order-details popup (dialog + JS, currently duplicated WITH
DRIFT in `spillover.html` and `ecom_gatekeeper.html`) into `_order_details.html`,
AJAX-driven like `_entity_links.html`. Backend needs nothing — the
`order_details` table + `/order-details/...` routes are already generic.
Spillover's richer variant is canonical (order type · number · comment ·
docs-in-S4 checkbox + green ✓ badge); the old gatekeeper inherits the S4
checkbox as a free upgrade. Migrate both pages, DELETE the two inline
copies, component roundtrip test.
**You verify:** order-details popup works unchanged on Spillover and old
Gatekeeper (add/edit/delete an order, S4 checkbox + badge).

## Step 2 — Shared Jira store  *(foundation; no UI yet)*

- `app/db/jira.py`: `jira_issues` (jira_key PK, solman_id = summary before
  first "_", summary, epic, markets, jira_status, jira_assignee, type,
  priority, description HTML, link, created/updated, first_seen/last_seen)
  + `jira_comments` (jira_key, created, body HTML; no authors — the XML
  only carries JIRAUSER keys; comments REPLACED per import).
- `app/jira_importer.py`: tolerant XML parser (Jira RSS; pre-pass escapes
  bare `&` — verified against the real export, Jira DC 10.3);
  source [USER 2026-07-06]: two configured FOLDERS (gatekeeper exports
  "assigned to Marina" / ECOM sync exports "open issues") — importer takes
  the NEWEST .xml in each folder, no filename stems. Folder paths TBD with
  Marina (settings.yaml keys, local-overridable).
- Re-import rule [USER]: match by jira id; ONLY comments, jira_status,
  jira_assignee refresh — everything else stays from first import.
- Tests FIRST: fixture modeled on the real file (ampersand quirk, empty
  description, comment thread, re-import refresh rules).
**You verify:** pytest green; a trial import of your real XML shows correct
rows in the tables (I run it read-back for you).

## Step 3 — Gatekeeper v2 card: core  *(side by side with the old card)*

- `gatekeeper_annotations` (jira_key PK, internal_status, next_step,
  dtco2c flag, pushed_at, rfv_pushed_at) — authored data, importer never
  touches it except creating rows with status **OrderCheck** on first import.
- Statuses [USER confirmed]: OrderCheck → Issue DTC | Issue Sales |
  SF requested → **Ready for validation** (= handover, HIDDEN by default
  like defects' Confirmed; show-hidden toggle).
- Import button on the card (runs the gatekeeper-folder XML import).
- List (structure like Retail): jira id, solman id, name, epic, internal
  status (inline select), next step (inline edit), jira status + jira
  assignee (read-only, separate fields), notes count; filters: search,
  epic, internal status.
- Detail: fields + next_step, jira description, READ-ONLY comment thread,
  open-in-Jira link, full notes module (registry entry).
- Old ECOM Gatekeeper card untouched.
**You verify:** import your real file, walk the list/detail, set statuses,
write a note.

## Step 4 — Gatekeeper v2 integrations

- Order-details component on the detail page (from step 1).
- Inbox filing target ("Gatekeeper ticket", search by jira id / name).
- Add-to-Meeting-Prep + **DTC O2C checkbox** → flagged tickets appear on
  the DTC O2C Daily agenda page.
- Teams ping (registry entry, e.g. ping the Jira assignee) + Teams channel
  picker on the card.
**You verify:** each integration once by hand.

## Step 5 — Excel push buttons

- Purpose: staging for copy-paste into the browser-Excel the key users read.
- Mode (RECOMMENDED, confirm): each push writes a fresh DATED file with only
  not-yet-pushed rows (pushed_at / rfv_pushed_at markers); "include already
  pushed" toggle for re-pushes.
- Templates [USER 2026-07-06]: NO separate template files — both formats are
  seeded from info in the newest tracking Excel (`DTC_UAT_testtracking_ROE(24)`);
  column details to be discussed with Marina before building.
- Button 1: all lines, retail-like columns.
- Button 2: only Ready-for-validation lines, own format — pushing is the
  handover act.
**You verify:** push, open the file, paste into the browser Excel once.

## Step 6 — Gatekeeper status report + email

- Spillover-style: select rows → printable standalone HTML view.
  NO PPT, NO copy-for-Teams [USER].
- Becomes the 4th checkbox on /email-report (existing GMX plumbing).
**You verify:** generate + email the report to yourself.

## Step 7 — ECOM vertical: importer  *(source Excel PROVIDED 2026-07-06)*

- Source: `Download/DTC_UAT_testtracking_ROE(24).xlsx` — tab name confirmed
  **ECOM** (workbook also has `ECOM JIRA EPICS`, `ReportECOM`, `Manual Test
  Cases ECOM`, not in scope here).
- Importer like Retail from the ECOM tab; extra columns jira_id and
  description_change (display; feeds the external coverage tool).
- Tables `ecom` + `ecom_annotations`; **match key = jira id** [USER].
- Excel fields vs Jira fields strictly separate (excel status/assignee ≠
  jira_status/jira_assignee).
- Characterization tests like the other importers.
**You verify:** import result counts match the tab.

## Step 8 — ECOM pages

- List + detail like Retail, plus: jira details + READ-ONLY comment thread
  from the shared store (joined by jira id), open-in-Jira link.
- "Upload jira comments" = running the ECOM-folder XML import (step 2 code).
- Handover from gatekeeper = relink (ECOM row's jira id points at the same
  jira_issues record — NO copying) + order_details re-point as planned.
- Optional add-on: auto-flag when a re-import changes the stored
  description (signal for the description_change workflow).
**You verify:** open an ECOM testcase that exists in Jira → details +
comments visible; run the sync; check a gatekeeper→ECOM relink.

## Step 9 — Inbox → To-Do

Filing option "To-Do" in the inbox picker. Proposed (confirm): CREATES a new
todo (topic = inbox heading, quick fields priority + due date in the picker,
like the shelf flow) and re-parents the note onto it — todos already carry
notes. Optionally ALSO allow filing into an existing todo via search (cheap,
same picker mechanics). OPEN: new-only or both?

## Step 10 — Promises (track what I promised to people)

New mini-card "Promises" — the mirror image of Follow-ups (follow-up = they
owe me; promise = I owe them):
- Table `promises`: to_whom (contacts autocomplete like encouragements),
  what, promised_on (default today), due (optional), status open | kept.
- Dashboard badge = open promises. List filterable by person/status.
- Notes module (registry entry) + Teams ping entry (deliver/remind the
  person directly from the promise).
- Inbox: "Promise" filing option — creates a promise (to_whom + what from
  the heading/note) and re-parents the note.
OPEN: is a due date wanted? Anything else on a promise (e.g. context link)?

## Step 11 — Regenerate the visual docs

`docs/architecture.html` and `docs/database_schema.html` still describe the
pre-refactor layout. Regenerate both from the current code (app/db package,
web_* modules, blueprints, components, all new tables incl. topics/jira/
promises when built). Low risk, documentation only.

---

## Before build, Marina provides — RESOLVED 2026-07-06 [USER]

1. ~~Gatekeeper Excel push template~~ — no file needed; format seeded from
   the newest tracking Excel, columns discussed before step 5.
2. ~~Ready-for-validation Excel template~~ — same as 1.
3. ✅ Newest tracking Excel: `DTC_UAT_testtracking_ROE(24).xlsx`, copied to
   the project `Download/` folder; ECOM tab confirmed present.
4. ~~Filenames/stems of the Jira XML exports~~ — replaced by the
   folder-based rule (step 2): importer takes the newest .xml per folder.
   XML format sample already on hand. ✅ Folders created 2026-07-09:
   `Download/jira_gatekeeper/` + `Download/jira_ecom/`, paths in
   `settings.yaml` (`jira_gatekeeper_folder` / `jira_ecom_folder`).

## Open decisions

- Excel push mode: confirm the dated-snapshot recommendation (step 5).
- ECOM status report / buckets like Retail: wanted or not (not requested).
