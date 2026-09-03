# The map — where to look when you change something

**One file per mini app** in `docs/claude/`, **one file per shared component**
in `docs/claude/components/`. This file is the index: one line each, plus the
system-level wiring that no single app file can own. Skeleton for new files:
`_template.md`.

Rule: when a mini app or component is added, renamed or removed, update its
file, this map, and `docs/dashboard_cards.html` (the visual card list).
**`tests/test_docs_structure.py` enforces it** — a new file that is missing
from this map, a header block naming a table or module that does not exist, or
a dangling `[[link]]` fails the test suite.

> Split into one-file-per-app on 2026-08-30 [USER]: `coordination.md` (502
> lines / 20 apps) and `verticals.md` (413 lines / 8 apps + 3 components) are
> gone. Every app and every component now has exactly one file.

---

## Mini apps

### Test execution & status (the imported data)

| Mini app | URL | Storage | File |
|---|---|---|---|
| Import DTC ROE Tracking | `POST /import` | `importer.py` + `archiver.py` | `import-pattern.md` |
| MB ROE Defects | `/defects` | `db/defects.py` → `defects`, `defect_annotations` | `defects.md` |
| Core South Spillover | `/spillover` | `db/spillover.py` → `spillover`, `spillover_annotations` | `spillover.md` |
| Retail | `/retail` | `db/retail.py` → `retail`, `retail_annotations` | `retail.md` |
| ECOM | `/ecom/` | `db/ecom.py` → `ecom`, `ecom_annotations` | `ecom.md` |
| ECOM Gatekeeper | `/ecom-gatekeeper` | `db/gatekeeper.py` → `gatekeeper_annotations` (+ the Jira store) | `gatekeeper.md` |
| Manual Test Cases Retail / ECOM | `/manual/retail`, `/manual/ecom` | `db/manual_tests.py` → `manual_retail`, `manual_ecom` | `manual-tests.md` |
| Report history | `/report-history/` | `db/report_history.py` → `report_history` | `report-history.md` |

### Coordination of other people's testing

| Mini app | URL | Storage | File |
|---|---|---|---|
| Delegated Testing | `/delegated/` (+ `/report`, `/numbers`, `/overview`, `/dtc-o2c-blockers`, `/settlement`) | `db/delegated.py` → `delegated_annotations`, `delegated_goal`, `delegated_sales_xls_check` | `delegated.md` |
| Blockers | `/blockers/` | `db/blockers.py` → `blockers`, `blocker_links` | `delegated.md` |
| CORE SOUTH Smoke Testing | `/smoke/`, `/smoke/ecom`, `/smoke/retail` | `db/smoke.py` → `smoke_scenarios`, `smoke_steps`, `smoke_annotations` | `smoke.md` |
| Core South Sustainphase Monitoring | `/sustain/`, `/sustain/summary` | `db/sustain.py` → `sustain_tasks`, `sustain_task_details`; `db/sustain_callouts.py` → `sustain_callouts` | `sustain.md` |
| Sustainphase Issues | `/sustain-issues/` | `db/sustain_issues.py` → `sustain_issues`, `sustain_issue_annotations` | `sustain-issues.md` |

### Retail requirements & gaps

| Mini app | URL | Storage | File |
|---|---|---|---|
| Retail Requirements Tracker | `/retail-tracker/board`, `/payment-methods` | `db_retail_tracker.py` → 9 tracker tables | `retail-tracker.md` |
| Missing Test Cases — **Retail only** | `/missing-tests/` | `db/missing_tests.py` → `missing_test_cases`, `missing_test_meta` | `missing-tests.md` |
| Retrofits | `/retrofits/` | `db/retrofits.py` → `retrofits` | `retrofits.md` |
| Known Production Issues | `/prod_defects` (+ `/archive`, `/report`) | `db/core.py` → `known_prod_defects`, `prod_defect_review_comments` | `known-production-issues.md` |
| Test Learnings | `/test_learnings` | `db/core.py` → `test_learnings` | `test-learnings.md` |
| Test Limitations | `/test_limitations` | `db/core.py` → `test_limitations` | `test-limitations.md` |

### The working day

| Mini app | URL | Storage | File |
|---|---|---|---|
| Inbox | `/inbox` | `db/notes.py` → `notes` (`entity_type='input'`) | `inbox.md` |
| Deadlines & Burning | `/urgent/` | `db/urgent.py` → `urgent_items` | `urgent.md` |
| Topics | `/topics/` | `db/topics.py` → `topics`, `topic_steps` | `topics.md` |
| Shelf | `/shelf` | `db/core.py` → `shelf` | `shelf.md` |
| To-Do | `/todos` | `db/core.py` → `todos` | `todo.md` |
| Meeting Prep | `/meeting-prep` | `db/core.py` → `meeting_prep`; `db/planning.py` → `meeting_types` | `meeting-prep.md` |
| Follow-ups | `/followups` | `db/core.py` → `followups`, `followup_options` | `follow-ups.md` |
| CS Follow-Up Tracker | `/cs_followups` | `db/core.py` → `cs_followups` | `cs-follow-ups.md` |
| Encouragements | `/encouragements` | `db/core.py` → `encouragements`, `encouragement_people` | `encouragements.md` |
| Links | `/links` | `db/core.py` → `links` | `links.md` |
| Contacts | `/contacts` | `db/core.py` → `contacts` | `contacts.md` |
| Teams Chats & channels | `/teams-chats/` | `db/teams_chats.py` → `teams_chats`, `teams_chat_refs` | `teams-chats.md` |
| Message Types | `/message-types` | `db/message_types.py` → `message_types` | `message-types.md` |
| Enhancements (chaosco itself) | `/enhancements/page` | `db/core.py` → `enhancements` | `enhancements.md` |
| Email Reports | `/email-report/` | `db/email.py` → `report_recipients`, `email_lists`, `email_list_members`, `email_list_reports` | `email-reports.md` |
| Export & Backup | `POST /export-reports`, `POST /backup` | none (files on disk) | `export-backup.md` |

## Components (`docs/claude/components/`)

Shared machinery used by many apps — a change here hits every including page.

| Component | URL | Storage | File |
|---|---|---|---|
| Notes (+ attachments) — **architecture rule 3** | `/n/<etype>/<eid>/…` | `db/notes.py` → `notes`, `attachments` | `components/notes.md` |
| Next-step archive (↻ / 🕘) | `/next-steps/…` | `db/next_steps.py` → `next_step_history` | `components/next-steps.md` |
| Entity connections | `/connections/…` | `db/entity_connections.py` → `entity_connections` | `components/connections.md` |
| Entity links | `/elinks/…` | `db/entity_links.py` → `entity_links` | `components/entity-links.md` |
| Order details (+ archive, Jira takeover) | `/order-details/…` | `db/reference.py` → `order_details`; `db/order_archive.py` → `order_details_history` | `components/order-details.md` |
| Issue-message builder (✉️) | `/issue-msg/…` | `issue_messages.py` + `message_types` | `components/issue-message.md` |
| Teams ping + channel picker | `/teams-ping/…` | none (contacts + `teams_chats`) | `components/teams-ping.md` |
| Global search (🔍) | `/search/orders.json` | none — registry in `db/search.py` | `components/search.md` |
| Shared Jira store | no page — read by 3 apps | `db/jira.py` → `jira_issues`, `jira_comments`, `jira_labels` | `components/jira-store.md` |
| Shared report blocks (macros, Excel log, 📣 call-outs) | inline on the reports | `db/core.py` → `report_comments` | `components/report-blocks.md` |
| Row validations (⚠) | button on the boards | none — `row_validations.py` | `components/row-validations.md` |
| Working-notes pages (🤝 WoW, 💡 Insights, …) | `/notes-page/<slug>` | none — registry `note_pages.py`; notes at `('note_page', slug)` | `components/note-pages.md` |

## Patterns

| Pattern | What it covers | File |
|---|---|---|
| The import pattern | one tab = one importer + one table, idempotent upsert, header maps and aliases, archiver + SHA-256 dedup, skip-log, the import-time data checks | `import-pattern.md` |

---

## How the apps connect

The wiring no single app file owns. **Check this list before changing a
module: someone else is probably reading its data.**

- **The shared Jira store** (`db/jira.py` → `jira_issues`, `jira_comments`,
  `jira_labels`) is imported ONCE from the Jira XML and read by three apps:
  ECOM Gatekeeper, ECOM, and Delegated Testing (its own upload tags rows
  `seen_in_delegated`). Notes and next steps on a ticket are addressed
  `('jira', key)` and are therefore SHARED between gatekeeper and ECOM —
  Delegated deliberately keeps its own thread (`delegated`).
- **Order details** are addressed `('jira', key)` for gatekeeper/ECOM rows —
  the same rows, connected, never copied.
- **Missing Test Cases is the single source** for "no test case exists":
  the Retail status report (page, HTML download, PPT) and the Retail
  Requirements board both render its list; the board's quick-add writes into
  it. The old `tracker_missing_tests` table was copied over once and dropped.
- **Missing Test Cases is Retail-only** [USER 2026-08-30] — the title says so
  everywhere (page, report, card, email text, download filename). ECOM gets its
  own list or is integrated later.
- **Retrofits owns `test_coverage_note`**; Missing Test Cases and the Retail
  Requirements board display it read-only. Retrofit sections render at the
  bottom of the ECOM and Retail status reports.
- **The Retail Requirements Tracker derives everything LIVE** from the `retail`
  table — a reopened test un-counts itself. Nothing is stored as a yes-mark.
- **Known Production Issues feeds** the ECOM Spillover Report's known-issues
  section, and ships three separate artefacts through Email Reports.
- **Email Reports renders other apps' pages** through the app itself
  (`emailer.gather_attachments` + `standalone_html`), so a changed report route
  changes the mail; a successful send snapshots the bucket numbers into Report
  history.
- **The Inbox files INTO** defects, retail, spillover, ecom, jira tickets,
  test learnings, follow-ups, shelf, topics, contacts, links, known
  production issues, the working-notes pages (2026-09-01 — ONE type
  `note_page`, the search lists every page; see
  `components/note-pages.md`) and Sustain call-outs (2026-09-02 —
  existing one by name/ticket, or a NEW one created from the note, see
  `sustain.md`) — adding a target means touching `_INBOX_TARGET_TYPES`,
  the picker and a search/exists branch.
- **Status report buckets** for Retail and ECOM come from ONE config
  (`config/status_mappings.yaml`) via `reporter.py`.
- **`db/core.py` still holds the older shared tables** (defects, spillover,
  retail, notes, and most small coordination apps). New modules get their own
  file in `app/db/` — see architecture rule 2.

## Where the other docs are

| Doc | What it is |
|---|---|
| `CLAUDE.md` | The rules + the terse file map (loaded into every session) |
| `docs/architecture.html` | The readable architecture: layers, data flow, what each layer may and may not do |
| `docs/screens.html` | Screen-by-screen reference |
| `docs/database_schema.html` | Every table and column |
| `docs/dashboard_cards.html` | The dashboard cards |
| `docs/build_plan.md` | The to-do document |
| `docs/ways_of_working.md` | How we work together |
| `docs/archive/` | Finished plans, reviews, session write-ups — never a source of truth |
