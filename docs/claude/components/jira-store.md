# The shared Jira store

**Type:** component (shared data store)
**URL:** no page of its own — read by `[[gatekeeper]]`, `[[ecom]]` and `[[delegated]]`
**Storage:** `app/db/jira.py` → `jira_issues`, `jira_comments`, `jira_labels`
**Importer:** `app/jira_importer.py` (`run_jira_import`)
**Tests:** `tests/test_jira_importer.py`, `tests/test_orders_shared_jira.py`, `tests/test_jira_order_takeover.py`

## Purpose

ONE copy of the Jira tickets in chaosco, imported from an exported XML search,
so the gatekeeper board, the ECOM board and Delegated Testing all read the same
ticket — no per-module copies that drift. Trial-verified 2026-07-11 against the
real export (8 tickets, 27 comments; the parser worked first try).

## Architecture

- **`jira_issues`** — `jira_key` PK; `solman_id` = the summary before the first
  `_`; epic / markets from the custom fields BY NAME (the instance's field
  names are "Epic Link" / "Markets"); description HTML.
  **`jira_comments`** — HTML bodies, NO authors (the export only carries
  JIRAUSER keys).
- **`app/jira_importer.py`** — a Jira RSS parser (DC 10.3; a pre-pass escapes
  bare `&`; parses reporter + markets [USER 2026-07-12: needed later]).
  `run_jira_import(cfg)` is ONE unified import [USER 2026-07-12]: newest `.xml`
  in `jira_folder` (fallback `jira_gatekeeper_folder`); both boards' buttons
  run the same import.
- **Per ticket**: already in the store → REFRESH (tracked forever — that keeps
  "Back with Sales" current even after reassignment); new + assigned to me
  (`jira_gatekeeper_assignee`) → enter; new + on the ECOM board
  (`ecom.jira_id`) → enter; else ignored (but counted). Source tags
  `seen_in_gatekeeper` / `seen_in_ecom` (and `seen_in_delegated`) reflect
  current membership — set, never cleared.
- **Re-import rule** [USER 2026-07-05]: match by jira key; ONLY `jira_status`,
  `jira_assignee`, the comments (REPLACED wholesale) and — since 2026-07-11 —
  `acceptance_criteria` are refreshed (living test data: testers fill order
  numbers into the AC checklist over time). Every other field keeps its
  first-import value.
- **Acceptance criteria** = the okapya checklist custom field, parsed as
  whitespace-normalized text lines.
- **HTML stripping** [USER 2026-07-18]: depending on the export the checklist
  plugin's markup arrives as TEXT/CDATA — then `itertext()` returned raw
  `<div>/<span>/<svg>` noise into `acceptance_criteria`. `_checklist_to_text`
  (HTMLParser-based) keeps only visible text (svg/style/script dropped, block
  tags → line breaks; the "0/2" checklist progress survives); plain text passes
  through unchanged. AC is a living field, so ONE "↻ Update from Jira" heals
  already-noisy stored values.
- **Order-number extraction** (`extract_order_numbers`, [USER 2026-07-11]):
  1. ALL labeled orders from the AC ("… Order[ Number] : value", `XXXX`
  placeholders skipped) → 2. otherwise the LATEST comment carrying a labeled
  order or an order token. Since 2026-08-26 comment bodies (stored HTML) are
  flattened to plain text before matching, and the token shapes are
  `AA_BB_XXXXXX`, 3–4 capitals + 6+ digits (ASK0342321 / ASKR0342321) and bare
  `6000…` SAP numbers.

## Rules & gotchas

- Jira has NO order-number field — order numbers live in comment texts and in
  the AC checklist. That is why extraction exists at all.
- The Jira search may be broad or lazy (e.g. `assignee WAS currentUser()` plus
  the board epics) — the import decides what to keep, not the search.
- **Never merged into the Excel-sourced tables.** Excel fields and Jira fields
  stay separate everywhere.
- Delegated Testing uses its OWN comments-ONLY extraction
  (`extract_latest_comment_orders`) — see `[[delegated]]`.

## Related

`[[gatekeeper]]` · `[[ecom]]` · `[[delegated]]` · `[[order-details]]` ·
`[[notes]]`
