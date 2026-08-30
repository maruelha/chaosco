# Deadlines & Burning

**Type:** mini app
**URL:** `/urgent/`
**Storage:** `app/db/urgent.py` → `urgent_items`
**Routes:** `app/web_urgent.py`
**Templates:** `urgent.html` · `_urgent_popup.html` (included from `dashboard.html`)
**Tests:** `tests/test_urgent.py`

## Purpose

[USER 2026-08-11] The short list that must not slip — and the point of the
module is that it is PUSHED IN YOUR FACE, not that it is stored. Anything that
does not deserve a daily popup belongs in `[[todo]]` or `[[topics]]`.

## Architecture

Three categories, because they nag differently:

| key | label | meaning |
|---|---|---|
| `deadline` | Deadline | must be done before a specific date |
| `burning` | Burning | urgent regardless of a date |
| `uncomfortable` | Uncomfortable | promises she'd be ashamed not to keep |

Second axis `area`: **Sales ECOM | MB | NULL** [USER 2026-08-11] — own column
and chip on the list and in the popup, filter dropdown with counts (including
"not assigned"). Unset is a valid state on purpose: being forced to choose
would stop things being written down.

Optional due date + note, done/reopen. RED dashboard card, listed FIRST.

**The dashboard popup** (`_urgent_popup.html`) opens whenever something is
open, lists the entries most-urgent first, lets her tick them off inline, and
remembers its dismissal PER DAY in localStorage (`urgent-popup-seen`) — back
tomorrow, but not on every dashboard visit.

## Rules & gotchas

- The overdue banner stays GLOBAL when a filter is on (labelled "across all
  areas") — hiding overdue work behind a filter would defeat a nag module.
- "Overdue" is computed in PYTHON against today: no SQL date functions
  (Postgres portability), a done item never counts as overdue, and an
  unparseable date is dropped rather than stored.

## Related

`[[todo]]` · `[[topics]]` · `[[meeting-prep]]`
