# Meeting Prep

**Type:** mini app
**URL:** `/meeting-prep` (+ `/dtco2c-daily`, `/agenda?meeting=…`, `/worksheet?meeting=…`)
**Storage:** `app/db/core.py` → `meeting_prep`; the meeting list in `app/db/planning.py` → `meeting_types`
**Routes:** `app/web_planning.py`
**Templates:** `meeting_prep.html` · `meeting_agenda.html` · `meeting_worksheet.html` · `dtco2c_daily_report.html`
**Tests:** `tests/test_meeting_reports.py`

## Purpose

The topics you want to raise per meeting, so nothing is forgotten in the
meeting itself — with a report to walk through and a worksheet to type into
while it runs.

## Architecture

Per-meeting agenda topics with `overall_topic` ordering and source-entity link
badges. Three reports:

- `/meeting-prep/dtco2c-daily` — the full DTC O2C version: planned topics +
  daily-flagged defects + DTC O2C follow-ups. Button in the page header.
- `/meeting-prep/agenda?meeting=…` — a plain sorted topic list, NO defects and
  NO follow-ups; button next to the filters, for whatever meeting is filtered.
- `/meeting-prep/worksheet?meeting=…` — the same list plus a comment box per
  topic, also following the current filter. Self-contained on purpose (no
  external fonts or fetches): saves the comments to JSON, loads them back
  (match by topic id, fall back to topic text) and downloads the page WITH the
  typed comments — textarea values are copied into the clone's text content
  first, otherwise they are lost.

**Meeting types** [USER 2026-08-11] — the dropdown is user-editable: the
"Meetings in the dropdown" panel adds (`POST /meeting-prep/meetings/add`,
duplicates refused case-insensitively) and removes (`…/meetings/delete`,
refused while topics still use the meeting). `planning.MEETING_OPTIONS` is
only the SEED list + fallback; read the live list with
`planning.get_meeting_options(conn)` — that is what the meeting-prep form and
filter and the "Add to Meeting Prep" dropdowns on Defect and Retail detail all
use. Seeding runs only while the table is empty, so a removed meeting stays
removed across restarts.

## Rules & gotchas

- **Exactly two agenda buttons** [USER 2026-08-11: "just two buttons, one for
  DTC O2C, one for any"] — an earlier per-meeting-type launcher block was built
  and removed the same week. Do not reintroduce it, and no "All meetings"
  button.
- All reports and the clipboard copy use **bullets, never numbering**
  [USER 2026-08-10].

## Outputs

Agenda report · DTC O2C daily report · offline worksheet (JSON save/load +
download with comments) · clipboard copy.

## Related

`[[todo]]` · `[[follow-ups]]` · `[[defects]]` · `[[retail]]`
