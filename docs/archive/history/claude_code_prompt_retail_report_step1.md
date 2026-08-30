# Retail Report — Step 1: On-screen bucket report (foundation for later steps)

## Context
Extends the existing Test Coordination Tool. The simplified Retail module (importer, `retail` table,
`retail_annotations`, list view) is already built. This step adds the FIRST piece of the Retail
daily status report: a button on the Retail page that computes and DISPLAYS today's report on
screen — bucket headings with counts, sanity checks, and a leftover/diagnostics section.

This is deliberately step one of several. It must NOT make later steps hard. Later steps will add:
storing raw per-status counts per date in SQLite (durable source of truth), history/trends,
appending dated rows to `DailyReport.xlsx`, and a Copy Report button. Build this step so those slot
in cleanly.

Respect architecture principles, especially:
- **Reporting is a separate layer from import** (handoff principle 4). The importer knows nothing
  about buckets. The report layer only QUERIES the database.
- **Storage layer separation.** Any DB reads go through `database.py`.
- **Config-driven buckets, never hardcoded.** Bucket definitions live in a config file.

## This step: compute live, no storage yet
Compute the report fresh each time the button is clicked, directly from the current `retail` table.
Do NOT store report rows or snapshots yet — but structure the code as:
  raw per-status counts (from the table)  →  apply config bucket rules  →  display.
This is the exact pipeline later steps reuse; only the "store the raw counts" stage gets added
later. Keep the raw-count computation as its own function returning a dict of {status: count} so a
future step can persist it unchanged.

## Config file: `config/status_mappings.yaml`
Create this now — it is the foundation. It must express, as INCLUSION lists:
- The master list of known statuses (the 16 from the handoff).
- Each bucket and the exact status values that count toward it.
- The 5 known-unmapped statuses (informational exclusions).

Bucket definitions (from the handoff; transcribe exactly). Use inclusion lists; a status counts
toward a bucket ONLY if explicitly listed:

- **Back with Sales:** `Blocked - returned to sales`
- **With DTC** (everything not back with sales): `Ready for Validation`, `In Progress`,
  `Blocked DTC`, `Passed`, `conditionally passed`, `Waiting for SF creation`, `Clarification needed`,
  `Gatekeeper Check`, `Passed pending solman`, `Ready for Validation Prio`
- **In Progress with DTC** (With DTC minus Passed): `Ready for Validation`, `In Progress`,
  `Blocked DTC`, `Waiting for SF creation`, `Clarification needed`, `Gatekeeper Check`,
  `Ready for Validation Prio`
- **Passed with DTC:** `Passed`, `conditionally passed`, `Passed pending solman`
- **Incoming (Gatekeeper)** — owner Jose: `Gatekeeper Check`
- **Ready for validation** — Key users: `Ready for Validation`, `Ready for Validation Prio`
- **In Progress** — Key users: `In Progress`
- **In Clarification** — Key users: `Clarification needed`
- **Blocked** — Tech team: `Blocked DTC`

Known-unmapped statuses (counted, shown in diagnostics, NOT in any bucket — these are expected,
not errors): `Failed`, `Not Ready`, `Yet to Upload`, `Dropped`, `Sales In Progress`.

Derived buckets may be expressed as formulas referencing other buckets where natural
(In Progress with DTC = With DTC − Passed with DTC), but the explicit inclusion lists above are
authoritative — implement from the lists and use the identity only as the sanity check below.

NOTE: There is intentionally NO "Total number of test cases coming from Sales" column. Do not add it.

## Report layout (on screen)
Show a single report for the current data with these columns/sections:

Top-level buckets:
- Back with Sales
- With DTC
- In Progress with DTC
- Passed with DTC

In-Progress breakdown (informational; owners shown as labels):
- Incoming (Gatekeeper) — Jose
- Ready for validation — Key users
- In Progress — Key users
- In Clarification — Key users
- Blocked — Tech team

Each shows its count. Present clearly (a table or labelled grid), readable, consistent with the
existing UI styling.

## Sanity checks (implement and SHOW the result)
1. **Identity check:** `In Progress with DTC` + `Passed with DTC` must equal `With DTC`.
   Compute both sides, display a clear PASS/FAIL indicator with the two totals. If it fails, show
   the discrepancy — do not hide it.
2. Note that the In-Progress breakdown (Incoming / Ready / In Progress / In Clarification / Blocked)
   is informational and does NOT have to sum to "In Progress with DTC" (Waiting for SF creation is
   in the total but has no breakdown column). Do NOT assert that sum; label the breakdown as
   informational so no one mistakes it for a closed reconciliation.

## Leftover / diagnostics section (below the report)
List every status present in the data that did NOT count toward the bucket columns, split into two
groups, each showing the status NAME and its count:
- **Unmapped (known, informational):** statuses in the master list but in no bucket — the 5 listed
  above. Show quietly as expected exclusions.
- **Unknown (warning):** any status value NOT in the master 16-status list at all (typo or a newly
  invented status). Flag visibly as a warning — something unexpected appeared.
Also show a single **leftover count** = total rows not included in any bucket, and list which
statuses make it up (so the user sees exactly what's being left out and why).

## UI
- Add a **"Report"** button on the Retail page.
- Clicking it shows the report (on screen — a section/panel or a `/retail/report` view, your choice,
  consistent with existing patterns). No file output, no clipboard button yet (later steps).

## Acceptance
- `config/status_mappings.yaml` exists with master list, buckets as inclusion lists, and the 5
  known-unmapped statuses. No bucket logic hardcoded in Python.
- Report button on Retail page shows bucket counts computed live from the `retail` table.
- Raw per-status counts are produced by a standalone function (dict of status→count) so a later
  step can persist them without refactoring.
- Identity sanity check (In Progress with DTC + Passed with DTC = With DTC) is computed and shown
  with a PASS/FAIL indicator.
- Leftover/diagnostics shows unmapped vs unknown statuses with names and counts, plus a total
  leftover count.
- Reporting code is separate from the importer; DB reads go through `database.py`. No storage of
  report rows yet. Defects/spillover/retail-list behavior untouched.
