# Email Reports

**Type:** mini app
**URL:** `/email-report/` (+ `/send`, `/text`, recipients and group routes)
**Storage:** `app/db/email.py` → `report_recipients`, `email_lists`, `email_list_members`, `email_list_reports`
**Routes:** `app/web_email.py`; sending + rendering in `app/emailer.py`
**Templates:** `email_report.html`
**Tests:** `tests/test_emailer.py`, `tests/test_email_lists.py`, `tests/test_email_page_features.py`

## Purpose

Send the status reports as standalone-HTML attachments from chaosco, so the
daily/weekly mail is one click instead of a manual export-and-attach round.

## Architecture

**The page opens with NOTHING ticked** [USER 2026-08-31] — all-ticked meant
unticking eleven boxes for a two-report mail. **All / None** buttons sit above
the list, `?reports=<key>` still pre-ticks one, and a **group** ticks its own
set in one click.

**Groups** (table `email_lists` + `email_list_reports`) are a whole saved send:
recipients **+ reports + the group's own subject and text**. "💾 Save current
send as group" stores all of it under a name (same name = replace); clicking
the group's chip applies all of it. A recipient-only save never drops a group's
report set (`save_email_list` only replaces what it is passed).

**The report list in the mail follows the ticks**: `POST /email-report/text`
rebuilds subject + body via `emailer.default_texts` — automatically while the
text has not been hand-edited, and on demand via **↻ Regenerate text** (which
asks first if you edited it). Typing in subject/body stops the automatic
follow; applying a group with its own wording does too.

**Nothing reloads the page**: add / activate / delete a recipient and save or
delete a group all go through `fetch` and answer with JSON
(`_wants_json` → `X-Requested-With: fetch`), because a reload used to throw
away the typed text and the ticked reports. Without the header the same routes
still redirect, so the page keeps working with JavaScript off.

Checkbox per report (`emailer.REPORT_CHOICES`): Spillover · Retail ·
Requirements Board · ECOM · Manual Retail + ECOM · Known Production Issues
(+ since 2026-08-27 its **Review Copy** — attached AS-IS, scripts kept on
purpose — and its **Management Report**, both separate choices) · Delegated
Testing Report + Management Summary (since 2026-08-26, the pair attaches the
clean `/delegated/*/download` renders; Delegated Testing Overview joined
2026-08-31; the two Teams-paste lists **DTC O2C Blockers** + **Settlement
File Waiting List** joined 2026-09-02 [USER: "email reports only" — they are
deliberately NOT on the Export Reports card]) · Missing Test Cases (Retail)
(since 2026-08-30).

A date field (default today) drives subject and body text (both editable).
Recipients live in `report_recipients` (add / toggle active / delete; active
ones pre-ticked) and go into groups — which since 2026-08-31 carry the reports
and the wording too, see above. Reports rendered
through the app are made standalone by `emailer.standalone_html` (CSS inlined,
scripts stripped, sections opened); the routes that already return clean
standalone HTML are attached as-is.

The Retail attachment is rendered by `emailer.render_retail_html`, which the
Export Reports snapshot uses too — one renderer, so what you see on the page is
what the recipient gets (`tests/test_retail_report_copies.py`).

`?reports=<key>` on the page URL pre-ticks just one report — that is what a
page's own "✉ Send via email" button links to.

After a successful send the bucket numbers are snapshotted into
`[[report-history]]` under the email date; a failed snapshot must never turn a
successful send into an error.

## Rules & gotchas

- Credentials `email_user` / `email_password` belong ONLY in the gitignored
  `settings.local.yaml`. The page shows setup instructions and disables Send
  until they are configured.
- `default_texts(reports=...)` distinguishes **`None` = "not asked"** (list every
  report) from an **empty list = "nothing ticked"** (body says "(no report
  selected yet)"). A plain `or` here would list all thirteen again on a page that
  now opens with none ticked — the exact bug this was written to avoid.
- `save_email_list` replaces a group's **reports only when report keys are
  passed**. Anything that saves a group without them (a recipient-only change)
  must keep the existing set, or a group silently loses its reports.
- The recipient/group routes answer **JSON when `X-Requested-With: fetch` is
  set and redirect otherwise** (`_wants_json`). Keep both branches when touching
  them: the page relies on the JSON one to avoid a reload, and the redirect is
  the no-JavaScript fallback.
- One definition of the wording: subject/body text belongs in
  `emailer.default_texts` only. The page never builds its own copy — otherwise
  ↻ Regenerate and the initial render drift apart.

## Related

`[[report-history]]` · `[[known-production-issues]]` · `[[delegated]]` ·
`[[missing-tests]]` · `[[export-backup]]`
