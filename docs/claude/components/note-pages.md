# Working-notes pages

**Type:** component
**URL:** `/notes-page/<slug>` · `/notes-page/<slug>/download`
**Storage:** none of its own — the shared `notes`/`attachments` tables, entity `('note_page', <slug>)`
**Routes:** `app/web_note_pages.py` (Blueprint `note_pages`); registry `app/note_pages.py`
**Templates:** `note_page.html` · `note_page_download.html` (generic pair, serves every page)
**Tests:** `tests/test_note_pages.py`

## Purpose

Singleton notes pages ("Ways of Working"-style): one page = one running
notes thread with the full shared notes component (headings, text,
screenshot/file attachments, Ctrl+V). Built 2026-09-01 when Marina asked
for a second such page ("insights while testing") — [USER: "can we build
so we dont duplicate but can add These Kind of pages with 'new headings'
whenever?"]. For the user they stay SEPARATE pages, each reached by its
own button in the place it belongs; only the implementation is shared.

## Design decisions (planning chat 2026-09-01)

- **Registry, not a table** — [USER: "i dont need to have to
  automatically in the programm create this new page - i would always be
  coming to you with that request"]. Pages are code-defined in
  `app/note_pages.PAGES` (slug → emoji, title, context, subtitle,
  home endpoint/label, download stem). **Adding a page = one registry
  entry + one button** (`url_for('note_pages.note_page', slug=...)`)
  wherever Marina wants it. No dashboard card, no index page — both
  offered and declined.
- **`app/note_pages.py` is deliberately Flask-free** so
  `app/db/notes.py` can validate inbox filing targets against it without
  the db layer importing the web layer.
- **One `web_notes.REGISTRY` entry** (`note_page`, entity_id = slug,
  detail endpoint = the page itself): the generic note add/edit/delete,
  attachments and Ctrl+V all just work; unknown slugs 404 via the
  registry lookup. The slug is stable, so a page TITLE can change
  without orphaning notes.
- **One inbox target type** `note_page`: the picker's search lists every
  page on the empty query (`db/notes.search_targets`); filing validates
  the slug against the registry. This REPLACED the `delegated_wow`
  singleton special case in `inbox.html`'s `onTypeChange` — the JS
  special case is gone, pages use the normal search flow.
- **Ways of Working migrated in** the day it was built ([USER: "certainly
  migrate it"]): its one-off routes/templates removed, notes moved by a
  guarded UPDATE in `db/core.py` (`('delegated_wow','main')` →
  `('note_page','delegated_wow')`, idempotent), the old URLs
  `/delegated/wow` and `/delegated/wow/download` redirect to the generic
  routes. The 🤝 board button kept working throughout.

## Date-heading pages (`heading_mode='date'`, 2026-09-01 [USER])

Added for **📝 Meeting Summaries** (daily AI meeting summaries, "for
future reference") — [USER: "in the title I can pick a date (today is
prefilled)"]. A registry entry can carry `"heading_mode": "date"`; the
option flows through the SHARED add/edit form, not a per-page copy:

- `web_notes.note_add`/`note_edit` read `heading_mode` off the entity's
  row (`row.get("heading_mode", "text")` — works for ANY registered
  entity, not just note pages) and pass it to `note_form.html`. On
  `heading_mode='date'` the heading field is a native date picker
  (`<input type="date">`), no free text — [USER: "only the date
  picker"], prefilled with today on a fresh GET only (a failed
  re-submit or an edit keeps the posted/stored value).
- **Sort order flips for date pages**: `web_note_pages._load_notes`
  sorts by the heading (the meeting date) descending instead of
  `created_at` — pasting yesterday's summary today must still land
  under yesterday's date, not today's. Same date twice is fine [USER] —
  ties keep `list_notes`' created_at-desc order (stable sort).
- Every other page (WoW, Testing Insights) keeps the plain free-text
  heading — the option is opt-in per registry entry, nothing shared
  changed for them.

## Keyword filter (2026-09-01 [USER: "search for certain Topics ...
WITHOUT ai"])

A plain-text search box above the notes list on `note_page.html`
(client-side substring match over the already-rendered notes — heading
+ text, case-insensitive; shows "N of M matches"). Deliberately **not**
in `_notes_section.html` — it only applies to these working-notes pages,
not every entity's notes elsewhere. No server round trip, **no AI
anywhere** — a topic search finds the word you typed, not its meaning
(searching "invoice problem" will not find a summary saying "billing
issue"); if that becomes limiting later, SQLite full-text search is the
non-AI upgrade path, not attempted yet. Hidden entirely when a page has
no notes.

## The pages (buttons in brackets)

| Slug | Page | Button lives |
|---|---|---|
| `delegated_wow` | 🤝 Ways of Working | Delegated Testing board header |
| `testing_insights` | 💡 Testing Insights | Delegated Testing board header |
| `sustain_meeting_summaries` | 📝 Meeting Summaries (`heading_mode='date'`) | Core South Sustainphase Monitoring card header |

## Parked

- **TXT export** [USER 2026-09-01: "let us park this option - we can
  revisit later when I know how i want to use it"] — asked for on the
  Meeting Summaries page, deliberately not built. Only the existing
  HTML download exists for all pages today.

## Related

`[[notes]]` · `[[delegated]]` · `[[sustain]]`
