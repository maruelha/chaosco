# Sustainphase Issues (`/sustain-issues/`)

Defect list for the sustain phase, imported from the **Defects tab** of
`DTC_Sustainphase_Tracking….xlsx` (planning chat 2026-08-28; built the
same day). Sits next to Sustainphase Monitoring and Smoke Testing on the
dashboard but is deliberately NOT linked to them [USER].

## Source workbook

Tabs: `SMOKETEST_KT` (ignored — KT tracking lives on the Smoke scenarios
instead), `SPOT_CHECKS` (**parked**: its own similar upload-and-view mini
app, another session), `Defects` (imported), `Datasheet` (dropdown
values, ignored). Upload: file picker, filename must contain
`DTC_Sustainphase_Tracking` (prefix/suffix vary, browser " (1)" copies
work), dated copy `data/uploads/sustain_issues_*.xlsx`.

Defects tab: headers in row 1 (they contain newlines/explanatory text →
the importer maps columns by NORMALIZED HEADER NAME PREFIX, never by
position). Columns → fields: Channel, Sales or DTC → sales_dtc,
ASPEN STATUS → aspen_status, Defect ID → defect_id, Short description,
more Defect description → description, Comment, raised by, order number,
Date Reported/Closed (dates → ISO), Priority, Assigned to, Tech Team,
Country, Scenario, affected testcases, Retest Dependency, Does it block
execution → blocks_execution, Defect reason. **"Exists in production" is
ignored entirely [USER].** The tab started as an empty template — an
empty import is ok (0 rows), the list fills as the team logs defects.

## The key model (USER design 2026-08-28)

Issues can exist before they are in ASPEN. `issue_key` (UNIQUE) is the
ASPEN Defect ID when known, else an auto-assigned **`SUS-nnn`
placeholder** (numbers never reused). Upsert per upload:

- row has a Defect ID → update the issue with that defect_id, or
  **promote** a placeholder issue matched by normalized short
  description: key switches to the Defect ID, annotations follow, the
  old key is kept in `former_placeholder` — no longer visible (tooltip
  "formerly SUS-nnn" on the key), but **still searchable**.
- row has no Defect ID → match an existing placeholder issue by
  normalized short description, else insert with the next placeholder.
- rows with neither id nor description are skipped; issues absent from
  an upload are KEPT (`last_seen` shows staleness).

Caveat (flagged in MarinaCheckSoon): renaming a placeholder issue's
short description in the Excel before its ASPEN id arrives makes it a
NEW issue — the description is the only identity a placeholder has.

## Storage — `app/db/sustain_issues.py`

`sustain_issues` (imported, upserted as above) +
`sustain_issue_annotations` (USER-AUTHORED: `callouts` — Marina's
call-outs/comment — and `next_step`; only-field upserts; keyed by
issue_key, migrated on promotion). Next-step archive entity
`sustain_issue` in `web_next_steps.REGISTRY`.

## Web — `app/web_sustain_issues.py` (Blueprint `/sustain-issues/`)

Card page = upload + the list: **expandable rows** (kpd pattern,
`details.si-row` in the shared expandable-row CSS — deliberately no wide
table). Summary: key (former placeholder as tooltip), short description,
ASPEN-status chip, priority, red **blocks execution** chip
(blocks_execution yes/y), 📣 call-outs marker, blue → next-step preview,
channel · country · dates. Body: description, Excel comment, meta line,
call-outs textarea + next-step input (saved onblur via
`POST /sustain-issues/issue/<key>/callouts|next-step`) with ↻/🕘.
Client-side filters: Channel / ASPEN status / Country / Priority
(distinct values). Sections: Open (no Date Closed) / Closed (collapsed).

## Search

Global 🔍 block "Sustainphase Issues": order number, issue key AND
former placeholder (`LOWER(...) LIKE LOWER(?)` — portable SQL). Added at
the same time [USER]: "Smoke scenarios" (name + step ASPEN ticket, ws
picks /smoke/ecom vs /smoke/retail) and a dedicated "Delegated Testing"
group (delegated-tagged tickets → delegated ticket detail).

## Pieces

- `app/db/sustain_issues.py` — schema + all SQL (incl. upsert/promotion)
- `app/sustain_issues_importer.py` — Defects tab → upsert
- `app/web_sustain_issues.py` — Blueprint (home/list, upload, callouts,
  next-step)
- `app/templates/sustain_issues.html` — list page (macro `issue_row`)
- Tests: `tests/test_sustain_issues_storage.py`,
  `test_sustain_issues_importer.py`, `test_sustain_issues_web.py`,
  `test_search_new_sources.py`

Build steps: `docs/build_plan.md` → "Sustainphase Issues".
