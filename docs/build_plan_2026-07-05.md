# Build Plan — 2026-07-05

Day plan, to be refined. Master backlog: `docs/build_plan.md`.

## 1. Order-details drop-in component

Extract the Order-details popup (dialog + JS, currently duplicated with
drift in `spillover.html` and `ecom_gatekeeper.html`) into a drop-in
component `_order_details.html`, AJAX-driven like `_entity_links.html` /
`_teams_channels.html`:

```
{% with od_entity_type='topic', od_entity_id=topic.id %}
  {% include '_order_details.html' %}
{% endwith %}
```

- Backend needs NOTHING: `order_details` table + `/order-details/...` routes
  are already generic (entity_type + entity_id).
- The spillover variant is canonical (order type · number · comment ·
  "docs in S4" checkbox with green ✓ badge); gatekeeper inherits the S4
  checkbox as a free upgrade.
- Migrate spillover + ecom_gatekeeper onto the component, DELETING their two
  inline copies; tests for the component roundtrip.
- Then place the button on further cards as desired (one include each) —
  candidates to decide: Topics? Defects?

## 2. Shared Jira store (foundation for items 3-6)

- `app/db/jira.py`: `jira_issues` (jira_key PK, solman_id = summary before
  first "_", summary, epic, markets, jira_status, jira_assignee, type,
  priority, description HTML, link, created, updated, first_seen/last_seen)
  + `jira_comments` (jira_key, created, body HTML — authors not needed,
  XML only has JIRAUSER keys anyway; comments REPLACED per import).
- `app/jira_importer.py`: tolerant XML parser (Jira RSS format; pre-pass
  escapes bare `&` — verified against Download/jira.txt, Jira DC 10.3).
  Newest-file-by-stem pattern like the Excel importers; separate stems for
  the gatekeeper file ("assigned to Marina" filter) and the ECOM sync file
  (open-issues filter).
- Re-import rule [USER]: match by jira id; only comments, jira_status (and
  jira_assignee) refresh — everything else stays from first import.
- Tests first: fixture modeled on the real file (incl. the ampersand quirk,
  empty description, comment thread).

## 3. ECOM Gatekeeper v2 (Jira-based) — SIDE BY SIDE with the old card

- Membership + authored data in `gatekeeper_annotations` (jira_key PK,
  internal_status, next_step, dtco2c/daily flag, pushed_at, rfv_pushed_at)
  — imported vs authored separation as everywhere.
- Internal status [USER confirmed]: OrderCheck (initial on import) →
  Issue DTC | Issue Sales | SF requested → Ready for validation
  (= handover; HIDDEN by default like defects' Confirmed).
- List page (structure like Retail): jira id, solman id, name, epic,
  internal status (inline), next step (inline), jira status + jira assignee
  (read-only, separate from any Excel fields), notes count, orders; filters
  (search, epic, internal status, show-hidden toggle).
- Detail page: meta + next_step, jira description, READ-ONLY comment thread,
  open-in-Jira link, full notes module, order-details component (item 1!),
  add-to-meeting-prep + DTC O2C flag (appears on the DTC O2C Daily agenda),
  Teams ping + channel picker, inbox filing target.
- Old ECOM Gatekeeper card stays untouched until Marina retires it.

## 4. Excel push buttons (gatekeeper)

- Purpose: staging for copy-paste into the browser-Excel that key users read.
- RECOMMENDED MODE (advised, to confirm): each push writes a fresh DATED file
  containing only rows not pushed before (pushed_at / rfv_pushed_at markers);
  open → select all → paste → done. No growing append-file to hunt through.
  A "include already pushed" toggle covers re-pushes.
- Button 1: all lines, columns like Retail (TEMPLATE FILE FROM MARINA).
- Button 2: only "Ready for validation" lines, its own format (TEMPLATE FILE
  FROM MARINA); pushing = the handover act.

## 5. Gatekeeper status report

- Spillover-style: select rows → printable standalone HTML view.
  NO PPT, NO copy-for-Teams [USER].
- Email: the report becomes a 4th checkbox on the existing /email-report
  page (same GMX plumbing, zero new infrastructure).

## 6. ECOM vertical (tab exists in the newest tracking Excel)

- Importer like Retail from the ECOM tab + two extra columns: jira_id and
  description_change (display; feeds Marina's external coverage tool —
  if the description changed, the test tested something different).
- Tables `ecom` + `ecom_annotations`; match key = JIRA ID [USER].
- Excel fields and Jira fields strictly separate: excel status/assignee vs
  jira_status/jira_assignee (from the shared store, joined by jira id).
- Detail page shows Jira details + comment thread from the shared store;
  "upload jira comments" = running the ECOM-filter XML import (item 2).
- Handover from gatekeeper = the ECOM row's jira id pointing at the SAME
  jira_issues record (relink, no copy) + order_details re-point as planned.
- Optional (nice, cheap): auto-flag when a re-import changes the stored
  description — candidate signal for the description_change workflow.

## Before build, Marina provides

1. Gatekeeper Excel push template (retail-like columns).
2. Ready-for-validation Excel template.
3. Newest tracking Excel containing the ECOM tab.
4. Names/stems of the two Jira XML files (gatekeeper filter + ECOM filter).

## Open

- Excel push mode: confirm the dated-snapshot recommendation (item 4).
- ECOM status report / buckets like Retail: wanted or not (not requested yet).
