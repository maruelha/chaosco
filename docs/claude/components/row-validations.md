# Row validations (⚠)

**Type:** component
**URL:** no page — a ⚠ button on the boards + `_row_validation_dialog.html`
**Storage:** none — pure logic in `app/row_validations.py`
**Tests:** `tests/test_row_validations.py`, `tests/test_reporter_filters.py`, `tests/test_import_data_checks.py`

## Purpose

[USER 2026-07-18] Data-quality checks over the IMPORTED fields: the workbook
says "conditionally passed" but nobody wrote the reason, a ticket has a
reporter nobody expects. The findings are shown, never enforced — the row is
still imported.

## Architecture

A registry of per-row checks (pure logic, no SQL and no Flask — mirrors
`issue_messages.py`). A flagged row gets a small red ⚠ button on the board;
clicking opens the shared `_row_validation_dialog.html` with the finding texts.

**Adding a validation = one check function (row dict → problem text or None) +
one `Rule(key, verticals, check)` in `RULES`.** The web layer
(`validate_rows(vertical, rows, id_field)` passed into the template as
`validations`) and the dialog are generic — nothing else to touch. To put the
button on a NEW board: pass `validations` from its list route, copy the 6-line
button `{% if %}`, and include the dialog once.

Current rules:

- status "conditionally passed" (case-insensitive) requires
  `reason_for_pass_with_reservation` — retail + ecom, and since 2026-08-05 also
  manual_retail / manual_ecom.
- `unexpected_reporter` — ecom: the ticket's reporter is outside the config
  `ecom_reporters`. The route INJECTS `reporter` / `expected_reporters` into
  the row dicts; caller-injected keys are the pattern for data beyond the
  imported row.

Since 2026-08-05 the same registry also runs at **import time**
(`importer.data_check_rows` over the parsed rows of the retail / ecom / manual
verticals): findings render as a red "⚠ Data checks" block per section on the
import report, naming the rows (excel row + tc/country or jira id). Skiplogged
rows are excluded — they have their own report line.

## Rules & gotchas

- Validations only READ. They never block an import and never write.

## Related

`[[import-pattern]]` · `[[retail]]` · `[[ecom]]` · `[[manual-tests]]` ·
`[[gatekeeper]]`
