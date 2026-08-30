# Known Production Issues

**Type:** mini app
**URL:** `/prod_defects` · `/prod_defects/archive` · `/prod_defects/report` (+ `/download`, `/download-review`)
**Storage:** `app/db/core.py` → `known_prod_defects`, `prod_defect_review_comments`
**Routes:** `app/web_defects.py`
**Templates:** `prod_defects.html` · `prod_defect_detail.html` · `prod_defects_report.html` · `prod_defects_review.html` · `prod_defects_review_comments.html`
**Tests:** `tests/test_prod_defects.py`

## Purpose

The manually curated register of defects, limitations, risks and accepted
defects known to exist in PRODUCTION. It outlives the spillover work: when UAT
is over, this is the list Ops keeps. It also feeds the Known Production Issues
section of the ECOM Spillover Report.

## Architecture

- **Fields** (2026-08-06): `channel` (ECOM/Retail), `type` (Defect / Limitation
  / Risk / Accepted Defect), `sub_case` (which sub-case of the scenario),
  `how_to_detect` (how Ops finds it), `how_to_handle`. `scenario` is a fixed
  dropdown (`prod_defect_scenarios` in settings.yaml; legacy values stay
  visible as "(current)").
- **Unique ids**: `display_id` `ECOM-NNN` / `RETAIL-NNN`, assigned once at
  creation from the channel (`_next_display_id`, partial unique index), NEVER
  regenerated. Legacy rows were backfilled at startup oldest-first — but only
  rows that HAVE a channel.
- **Mark Fixed / Archive**: `status` ('open'/'fixed') + `fixed_at`;
  `list_known_prod_defects` defaults to open-only, so a fixed item drops out of
  the list, the downloads, the email and the Spillover Report section WITHOUT
  being deleted. `/prod_defects/archive` lists them with ↺ Reopen.
- **Splits**: Limitations and Risks live in their own lists below the main one
  (`web_defects._split_by_type`); their rows carry only Edit + Delete (no Mark
  Fixed, no audience checkboxes).
- **Audience flags**: `relevant_core_south` / `relevant_gbs_ops` — checkboxes
  on the form and the expanded row, tri-state filters on the list.
- **Expandable rows** replaced the wide table (kpd-row accordion, shares the
  smoke-scenario CSS). Channel and Type are no longer columns of the main
  table (Channel = the id prefix and still filterable; Type = which list you
  are in). Lists are presorted by Scenario (portable `LOWER()` sort, blanks
  last).
- **Type filter/column** [USER 2026-08-24]: `type` (fixed list
  `_PROD_DEFECT_TYPES`) is a dropdown filter AND a visible column on BOTH
  `/prod_defects` and the standalone review download (client-side `data-type`
  show/hide there). Business Impact / How to handle are no longer truncated to
  200px with an ellipsis (`.kpd-truncate` removed) — the full text wraps. The
  scenario list gained "Marketplace" (`prod_defect_scenarios` in
  settings.yaml).
- **Detail page** carries the shared notes section (since 2026-07-13); registry
  key `prod_defect`, also an inbox filing target since 2026-08-06. The list
  shows the note count on Edit and a Confluence link at the top
  (`prod_defects_confluence_url`).

## Rules & gotchas

- Fixed rows are kept, never deleted — the register is a history as much as a
  status.
- The **review copy** is attached to email AS-IS, deliberately NOT run through
  `emailer.standalone_html`: its Detail dialogs and comment widget are the
  point of that artefact.
- The dashboard badge counts only ACTIVE (non-fixed) rows.

## Outputs

Three separate artefacts, all three selectable in `[[email-reports]]`:

1. **List snapshot** — `⬇ Download HTML` of the page.
2. **Review copy** — `/prod_defects/download-review` [USER 2026-08-24], a
   SECOND, additive button ("📝 Download for review") next to the plain
   snapshot. A standalone, fully self-contained HTML file with its OWN inline
   CSS/JS (unlike the plain download, which runs through
   `emailer.standalone_html` and strips every `<script>`). The list is
   read-only — a Detail button opens an in-page `<dialog>` per row with all
   fields, no Edit/Delete. A client-side "add feedback" widget sits on every
   row AND inside the Detail dialog: comments live only in the browser's
   `localStorage` (`kpd_review_comments_v1`), each with a client-generated
   UUID, the reviewer's name (asked once via `prompt()`, remembered under
   `kpd_review_author`), the text and a timestamp; a "Your comments so far"
   section lists them with per-comment remove. "⬇ Download my comments (JSON)"
   exports `{export_id, exported_at, report_date, author, comments: [...]}`
   for the reviewer to send back. Template `prod_defects_review.html`
   (standalone, no base.html — same convention as
   `retail_report_download.html`).

   **Reading them back**: `/prod_defects/review-comments`
   [USER 2026-08-24, "upload the comments to my page"] — a plain multipart
   upload form parses the file and upserts each comment into
   `prod_defect_review_comments` keyed by its client-generated id
   (`database.import_review_comments`, `ON CONFLICT(comment_id) DO NOTHING`,
   so re-uploading the same file is a no-op), reporting
   imported / duplicate / malformed counts. Below the form: every uploaded
   comment with the defect it is about (linked, or flagged "no longer in the
   list" if deleted), text, author, timestamp and Delete. The list-page toolbar
   carries a "📥 Reviewer feedback (N)" badge.
3. **Management report** — `/prod_defects/report` (+ `/download`): ECOM only;
   Defects and Limitations need BOTH audience flags, Risks = all ECOM;
   per-section and per-scenario counts; columns ID · Sub-case · Short
   Description · Business Impact. Context builder
   `prod_defects_report_context` is shared by screen, download and email.

Also feeds the ECOM Spillover Report's known-issues section.

## Related

`[[spillover]]` · `[[test-limitations]]` · `[[email-reports]]` · `[[inbox]]`
