"""Storage layer facade — re-exports the app.db package.

The old 2,800-line database.py was split by domain (refactoring step 4):

    app/db/core.py          connection + schema (init_db, get_connection)
    app/db/defects.py       defects vertical
    app/db/spillover.py     spillover vertical
    app/db/retail.py        retail vertical
    app/db/notes.py         unified notes + inbox + attachments
    app/db/planning.py      meeting prep, enhancements, todos, followups,
                            cs_followups
    app/db/reference.py     shelf, known prod defects, links, contacts,
                            encouragements, learnings, limitations,
                            order details, ecom gatekeeper, report comments

Callers keep writing `from app import database` / `database.<fn>` — every
public name is re-exported here. New code may import from app.db.<module>
directly. The rule is unchanged: ALL SQL lives in the storage layer.
"""
from app.db.core import get_connection, init_db, _rows_to_dicts  # noqa: F401
from app.db.defects import *        # noqa: F401,F403
from app.db.notes import *          # noqa: F401,F403
from app.db.spillover import *      # noqa: F401,F403
from app.db.retail import *         # noqa: F401,F403
from app.db.planning import *      # noqa: F401,F403
from app.db.reference import *     # noqa: F401,F403
from app.db.topics import *        # noqa: F401,F403
from app.db.entity_links import *  # noqa: F401,F403
from app.db.jira import *          # noqa: F401,F403
from app.db.ecom import *          # noqa: F401,F403
from app.db.next_steps import *    # noqa: F401,F403
