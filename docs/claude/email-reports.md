# Email Reports

**Type:** mini app
**URL:** `/email-report/` (+ `/send`, recipients and mailing-list routes)
**Storage:** `app/db/email.py` → `report_recipients`, `email_lists`, `email_list_members`
**Routes:** `app/web_email.py`; sending + rendering in `app/emailer.py`
**Templates:** `email_report.html`
**Tests:** `tests/test_emailer.py`, `tests/test_email_lists.py`

## Purpose

Send the status reports as standalone-HTML attachments from chaosco, so the
daily/weekly mail is one click instead of a manual export-and-attach round.

## Architecture

Checkbox per report (`emailer.REPORT_CHOICES`): Spillover · Retail ·
Requirements Board · ECOM · Manual Retail + ECOM · Known Production Issues
(+ since 2026-08-27 its **Review Copy** — attached AS-IS, scripts kept on
purpose — and its **Management Report**, both separate choices) · Delegated
Testing Report + Management Summary (since 2026-08-26, the pair attaches the
clean `/delegated/*/download` renders) · Missing Test Cases (Retail) (since
2026-08-30).

A date field (default today) drives subject and body text (both editable).
Recipients live in `report_recipients` (add / toggle active / delete; active
ones pre-ticked) and can be saved as named mailing lists. Reports rendered
through the app are made standalone by `emailer.standalone_html` (CSS inlined,
scripts stripped, sections opened); the routes that already return clean
standalone HTML are attached as-is.

`?reports=<key>` on the page URL pre-ticks just one report — that is what a
page's own "✉ Send via email" button links to.

After a successful send the bucket numbers are snapshotted into
`[[report-history]]` under the email date; a failed snapshot must never turn a
successful send into an error.

## Rules & gotchas

- Credentials `email_user` / `email_password` belong ONLY in the gitignored
  `settings.local.yaml`. The page shows setup instructions and disables Send
  until they are configured.

## Related

`[[report-history]]` · `[[known-production-issues]]` · `[[delegated]]` ·
`[[missing-tests]]` · `[[export-backup]]`
