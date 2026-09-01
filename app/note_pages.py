"""Working-notes pages — the registry (2026-09-01 [USER]).

Singleton notes pages ("Ways of Working"-style): each page is ONE notes
thread in the shared system, pinned to ('note_page', <slug>). Marina asked
for more such pages ("insights while testing") WITHOUT duplicating the
one-off Ways-of-Working build — so the pages share one Blueprint
(app/web_note_pages.py), one template pair, one web_notes.REGISTRY entry
and one inbox target type, and only THIS dict knows the individual pages.

Adding a page [USER: "i would always be coming to you with that
request"] = one entry here + one button in the template where Marina
wants to reach it (`url_for('note_pages.note_page', slug=...)`). No own
table, no per-page routes, no per-page templates.

Kept free of Flask imports on purpose: app/db/notes.py validates inbox
filing targets against PAGES, and the db layer must not import the web
layer.
"""
from __future__ import annotations

PAGES: dict[str, dict] = {
    # the former stand-alone /delegated/wow page (2026-09-01, migrated the
    # same day) — 🤝 button on the Delegated Testing board
    "delegated_wow": {
        "emoji": "🤝",
        "title": "Ways of Working",
        "context": "Delegated Testing",
        "subtitle": "The delegated-testing decision log — whatever is "
                    "agreed in the dailies and should be remembered lands "
                    "here as a note.",
        "home_endpoint": "delegated.delegated_list",
        "home_label": "Delegated Testing",
        "download_stem": "delegated_ways_of_working",
    },
    # [USER 2026-09-01: "another page like the ways of working - for
    # insights while testing"] — 💡 button on the Delegated Testing board
    "testing_insights": {
        "emoji": "💡",
        "title": "Testing Insights",
        "context": "Delegated Testing",
        "subtitle": "Insights collected while testing — anything learned "
                    "along the way that should not get lost lands here as "
                    "a note.",
        "home_endpoint": "delegated.delegated_list",
        "home_label": "Delegated Testing",
        "download_stem": "testing_insights",
    },
}
