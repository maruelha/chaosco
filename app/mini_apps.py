"""Mini-app registry (2026-09-03 [USER]) — the apps a Links-card link can
be attached to ("link links to specific mini apps").

First user: link ↔ app references (`link_apps`, db/reference.py) and the
🔗 Links button + dialog on those apps' pages. Two apps to start [USER:
"delegated testing and core south sustain - more I can add later"] —
adding one = an entry here + `ui.app_links_button(slug, count)` in that
app's page header (and the count in its route).

Flask-free on purpose (same rule as note_pages.py): the db layer validates
slugs against it without importing the web layer.
"""
from __future__ import annotations

APPS: dict[str, dict] = {
    "delegated": {
        "title": "Delegated Testing",
        "home_endpoint": "delegated.delegated_list",
    },
    "sustain": {
        "title": "Core South Sustainphase Monitoring",
        "home_endpoint": "sustain.sustain_home",
    },
}


def is_app(slug: str | None) -> bool:
    return bool(slug) and slug in APPS
