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

# Shared Jira store (day plan 05.07 step 2) — no routes yet, the Gatekeeper
# v2 card (step 3) and the ECOM vertical (steps 7-8) consume it.
from app.db import jira as _db_jira
_db_jira.init_schema(_db_path)

# ECOM vertical (day plan 05.07 step 7) — importer + tables; pages = step 8.
from app.db import ecom as _db_ecom
_db_ecom.init_schema(_db_path)


if __name__ == "__main__":
    import threading
    import webbrowser

    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, host="127.0.0.1", port=5000)
