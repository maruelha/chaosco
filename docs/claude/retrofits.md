# Retrofits

**Type:** mini app
**URL:** `/retrofits/` (+ `/add`, `/<id>/update`, `/<id>/note`, `/<id>/delete`)
**Storage:** `app/db/retrofits.py` → `retrofits`
**Routes:** `app/web_retrofits.py`
**Templates:** `retrofits.html`; report section via the `retrofits()` macro in `_report_blocks.html` (+ an inline copy in `retail_report_download.html`)
**Tests:** `tests/test_retrofits.py`

## Purpose

[USER 2026-08-10] Changes that are still COMING to the live system, per
channel — so a sign-off reader never assumes the tested scope is final. A
retrofit may invalidate what was already tested, or may still be announced
late.

## Architecture

- **Channel**: `ECOM` | `Retail` | **`ECOM & Retail`** — the shared channel
  renders on BOTH reports [USER 2026-08-14]. `list_retrofits(channel=…)` for a
  single channel therefore also returns the shared rows, and `retrofit_counts`
  counts them into both single-channel numbers but only once into the total.
- **Status**: `Confirmed` (known and agreed) | `Potential` (might still come).
  Two statuses on purpose — "don't forget what could still land" stays visible
  instead of only what is already certain. Confirmed sorts before Potential.
- `description` holds the **Confluence link** (labelled so in the UI since
  2026-08-14, rendered as a link when it starts with http); `expected` is free
  text ("CW34", "after go-live"); `topic_id` optionally links a `[[topics]]`
  entry for the background — resolved in a SEPARATE query, never a JOIN, so
  retrofits stay readable without the topics table.
- **`test_coverage_note`** [USER 2026-08-30] — "is there a test case for it?".
  Authored HERE: a field in the add form and an inline blur-save column
  (`POST /retrofits/<id>/note`). `[[missing-tests]]` and the Retail
  Requirements board only DISPLAY it.

## Rules & gotchas

- `update_retrofit` deliberately does NOT write `test_coverage_note`, and the
  Edit row does not carry the field — so saving an edit can never wipe a note.
- The report section shows **only Status + Title** [USER 2026-08-14];
  Confluence link, Expected and Topic stay on this page.
- The section renders **even when the list is EMPTY**, because its standing
  caveat is the point: "further retrofits may still be announced, and anything
  already tested may need a re-test once they land."

## Outputs

The "Retrofits — ECOM/Retail" section at the bottom of the ECOM and Retail
status reports (page, HTML download and email attachment), plus the read-only
mirror on `[[missing-tests]]` and the Retail Requirements board.

**"Test cases are needed for these as well"** [USER 2026-08-30] is rendered
over the retrofit list on the RETAIL report (macro parameter
`test_case_note=True`, plus the inline copy in `retail_report_download.html`),
the Retail Requirements board, the Missing Test Cases page and its report, and
in the copy & paste email text. It is deliberately NOT on the ECOM report —
the missing-test-case list it points at is Retail-only for now.

## Related

`[[missing-tests]]` · `[[retail-tracker]]` · `[[topics]]` · `[[retail]]` · `[[ecom]]`
