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
  `('note_page','delegated_wow')`, idempotent), old URLs
  `/delegated/wow[/download]` redirect to the generic routes. The 🤝
  board button kept working throughout.

## The pages (buttons in brackets)

| Slug | Page | Button lives |
|---|---|---|
| `delegated_wow` | 🤝 Ways of Working | Delegated Testing board header |
| `testing_insights` | 💡 Testing Insights | Delegated Testing board header |

## Related

`[[notes]]` · `[[delegated]]`
