# Export & Backup

**Type:** mini app (dashboard card, no page of its own)
**URL:** `POST /export-reports` · `POST /backup`
**Storage:** none — files on disk (`report_export_folder`, `backup_folder`)
**Routes:** `app/web_home.py`; logic in `app/report_exporter.py` and `app/backup.py`
**Tests:** `tests/test_backup.py`, `tests/test_report_exporter.py`

## Purpose

Two jobs on one card: dated report snapshots for automation pickup, and a
backup of the database + the uploaded files to an external drive.

## Architecture

- **Export Reports** — six files into `report_export/`:
  `retail_report_<date>.html/.pptx`, `spillover_report_<date>.html/.pptx`,
  `delegated_report_<date>.html`, `delegated_numbers_<date>.html`. Must run
  inside a REQUEST context (the spillover template calls `url_for`), which the
  route provides. The Retail HTML goes through `emailer.render_retail_html` —
  the same renderer as the email attachment and the page's download button
  [2026-08-31], after the snapshot had drifted (no defect table, no retrofits,
  and no missing-test-cases block).
- **DB backup** [USER 2026-07-18] — one click copies the SQLite DB to
  `backup_folder` (machine-specific, `settings.local.yaml`, e.g. the external
  drive) AND mirrors `data/uploads` incrementally to `<backup_folder>/uploads`.
  Modes: **overwrite** (`chaosco_backup.db`, replaced) or **dated**
  (`chaosco_backup_<ts>.db`, a new copy). Uses the sqlite3 backup API, NOT a
  raw file copy, so a mid-write database stays consistent. A "Last backup: …
  (N days ago)" line reminds (amber after 7 days).

## Rules & gotchas

- The backup section lives INSIDE the Export & Backup card — an own card was
  rejected ("a button somewhere"), folded in after discussion.
- Upload files are immutable per name, so ONE shared mirror serves every DB
  snapshot; files deleted in the app linger in the mirror — this is a backup,
  not a sync.
- A browser page CANNOT open a native pick-any-folder dialog; the configured
  folder was chosen deliberately over a download button.
- NOT covered, deliberately (small or recreatable): the Excel archive folder,
  `report_export` snapshots, the Jira XMLs, and `settings.local.yaml` — the
  credentials stay off the external drive.
- A scheduled backup may be wanted later.

## Related

`[[email-reports]]` · `[[report-history]]`
