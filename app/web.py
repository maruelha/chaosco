"""Local web UI — run with:  python -m app.web

Assembles the app: feature route modules (shared `app` from web_core, flat
endpoint names) + the Blueprint verticals (tracker, notes). The old
3,000-line monolith now lives in app/web_*.py, one module per area.
"""
from app.web_core import app, _db_path  # noqa: F401

# Feature route modules — importing them registers their routes.
from app import web_home       # noqa: F401,E402  dashboard, import, uploads
from app import web_defects    # noqa: F401,E402
from app import web_spillover  # noqa: F401,E402
from app import web_retail     # noqa: F401,E402
from app import web_reports    # noqa: F401,E402
from app import web_planning   # noqa: F401,E402
from app import web_reference  # noqa: F401,E402

# Blueprint verticals (the pattern for NEW modules).
from app import db_retail_tracker
from app.web_retail_tracker import bp as _retail_tracker_bp
db_retail_tracker.init_schema(_db_path)
app.register_blueprint(_retail_tracker_bp)

from app.web_notes import bp as _notes_bp
app.register_blueprint(_notes_bp)

from app.db import email as _db_email
from app.web_email import bp as _email_bp
_db_email.init_schema(_db_path)
app.register_blueprint(_email_bp)

from app.web_teams import bp as _teams_bp
app.register_blueprint(_teams_bp)

from app.db import topics as _db_topics
from app.web_topics import bp as _topics_bp
_db_topics.init_schema(_db_path)
app.register_blueprint(_topics_bp)

from app.db import entity_links as _db_entity_links
from app.web_entity_links import bp as _entity_links_bp
_db_entity_links.init_schema(_db_path)
app.register_blueprint(_entity_links_bp)

# Entity connections (2026-07-18) — many-to-many topic ↔ defect / retail /
# ecom / spillover links; drop-in _connections.html on the detail pages.
from app.db import entity_connections as _db_conn
from app.web_connections import bp as _conn_bp
_db_conn.init_schema(_db_path)
app.register_blueprint(_conn_bp)

# Shared Jira store (day plan 05.07 step 2) — no routes yet, the Gatekeeper
# v2 card (step 3) and the ECOM vertical (steps 7-8) consume it.
from app.db import jira as _db_jira
_db_jira.init_schema(_db_path)

# Gatekeeper v2 authored data (per jira ticket) — start, 2026-07-11.
from app.db import gatekeeper as _db_gatekeeper
_db_gatekeeper.init_schema(_db_path)

# ECOM vertical (day plan 05.07 steps 7+8) — importer + tables + pages.
from app.db import ecom as _db_ecom
from app.web_ecom import bp as _ecom_bp
_db_ecom.init_schema(_db_path)
app.register_blueprint(_ecom_bp)

# Manual Test Cases verticals (2026-08-05) — manual_retail + manual_ecom
# tables from the two "Manual Test Cases | …" tabs; one Blueprint for both
# streams (/manual/retail, /manual/ecom — list + simple status report).
from app.db import manual_tests as _db_manual
from app.web_manual_tests import bp as _manual_bp
_db_manual.init_schema(_db_path)
app.register_blueprint(_manual_bp)

# Report history (2026-08-05) — auto-saved on report email sends + the
# workbook Report-tab import button; /report-history with switcher.
from app.db import report_history as _db_hist
from app.web_report_history import bp as _hist_bp
_db_hist.init_schema(_db_path)
app.register_blueprint(_hist_bp)

# Next-step archive (generic component, 2026-07-10) — registry-driven.
from app.db import next_steps as _db_ns
from app.web_next_steps import bp as _ns_bp
_db_ns.init_schema(_db_path)
app.register_blueprint(_ns_bp)

# Order-details archive (2026-07-16) — grouped history batches; routes live
# with the other generic /order-details/... routes in web_spillover.
from app.db import order_archive as _db_oa
_db_oa.init_schema(_db_path)

# Teams chats & channels registry (2026-07-16) — /teams-chats management
# page, floating 💬 widget JSON, per-ticket refs. Old "Teams Channel" links
# rows are migrated into teams_chats at startup (idempotent).
from app.db import teams_chats as _db_tc
from app.web_teams_chats import bp as _tc_bp
_db_tc.init_schema(_db_path)
app.register_blueprint(_tc_bp)

# Issue-message builder (2026-07-16) — /message-types reference card +
# /issue-msg JSON for the ✉️ dialog; special texts fixed in issue_messages.py.
from app.db import message_types as _db_mt
from app.web_issue_msg import bp as _im_bp
_db_mt.init_schema(_db_path)
app.register_blueprint(_im_bp)

# Global search (2026-07-10) — floating 🔍 widget in base.html; source
# registry in app/db/search.py (order numbers now, topics via FTS later).
from app.web_search import bp as _search_bp
app.register_blueprint(_search_bp)

# Retrofits (2026-08-10) — coming system changes per channel; rendered at the
# bottom of the ECOM + Retail status reports, optionally linked to a Topic.
from app.db import retrofits as _db_retrofits
from app.web_retrofits import bp as _retrofits_bp
_db_retrofits.init_schema(_db_path)
app.register_blueprint(_retrofits_bp)

# Meeting types (2026-08-11) — the meeting dropdown is user-editable, so the
# list lives in its own table (seeded once from planning.MEETING_OPTIONS).
from app.db import planning as _db_planning
_db_planning.init_schema(_db_path)

# Deadlines & Burning (2026-08-11) — the short nag list; also drives the
# once-a-day dashboard popup.
from app.db import urgent as _db_urgent
from app.web_urgent import bp as _urgent_bp
_db_urgent.init_schema(_db_path)
app.register_blueprint(_urgent_bp)

# Delegated Testing (2026-08-26) — the delegated Jira export (uploaded on
# the card, tagged seen_in_delegated in the shared store) bucketed by
# status/assignee; authored blocked reason + next step per ticket.
from app.db import delegated as _db_delegated
from app.web_delegated import bp as _delegated_bp
_db_delegated.init_schema(_db_path)
app.register_blueprint(_delegated_bp)

# Blockers (2026-08-27, delegated build plan step 7) — defects/tasks/
# business clarifications that block Delegated Testing tickets; own entity,
# own notes thread, excluded from the delegated board by jira_key.
from app.db import blockers as _db_blockers
from app.web_blockers import bp as _blockers_bp
_db_blockers.init_schema(_db_path)
app.register_blueprint(_blockers_bp)

# CORE SOUTH Smoke Testing (2026-08-27) — EU CS Smoke Test execution
# workbook, uploaded on the card; eCOM/Retail scenarios + steps, WS +
# MB Invoice Validation filter applied at import.
from app.db import smoke as _db_smoke
from app.web_smoke import bp as _smoke_bp
_db_smoke.init_schema(_db_path)
app.register_blueprint(_smoke_bp)


if __name__ == "__main__":
    import threading
    import webbrowser

    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8010")).start()
    app.run(debug=False, host="127.0.0.1", port=8010)
