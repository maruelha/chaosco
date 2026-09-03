"""Connection + schema for the coordination DB (app.db.core).

get_connection() per request; init_db() once at startup (DDL + migrations).
Also home of the shared row->dict helper used by every sibling module.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open and return a connection. Schema must already exist (call init_db once first)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create schema if needed, return open connection. Call once at startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS defects (
            defect_id              TEXT PRIMARY KEY,
            channel                TEXT,
            solman_name            TEXT,
            raised_by              TEXT,
            order_number           TEXT,
            date_reported          TEXT,
            country                TEXT,
            scenario               TEXT,
            exists_in_production   TEXT,
            affected_testcases_raw TEXT,
            retest_dependency      TEXT,
            blocks_execution       TEXT,
            defect_reason          TEXT,
            solman_status          TEXT,
            priority               TEXT,
            assigned_to            TEXT,
            tech_team              TEXT,
            date_closed            TEXT,
            excel_row              INTEGER,
            first_seen             TEXT,
            last_seen              TEXT
        );

        -- User's structured annotations — created here, NEVER written by the importer.
        CREATE TABLE IF NOT EXISTS defect_annotations (
            defect_id        TEXT PRIMARY KEY REFERENCES defects(defect_id),
            description      TEXT,
            business_impact  TEXT,
            reach            TEXT,
            retest_needs     TEXT,
            next_step        TEXT,
            action_needed    INTEGER,
            comments         TEXT,
            updated_at       TEXT
        );

        -- Shared notes log — entity_type + entity_id identify the parent row.
        -- entity_type: 'defect', 'retail', ... entity_id: TEXT representation of PK.
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            heading     TEXT,
            note        TEXT,
            source      TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_notes_entity ON notes(entity_type, entity_id);

        -- Legacy table kept for migration only — no longer written to.
        CREATE TABLE IF NOT EXISTS defect_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            defect_id   TEXT REFERENCES defects(defect_id),
            created_at  TEXT,
            heading     TEXT,
            note        TEXT
        );

        -- Spillover imported rows — upserted each import, never deleted.
        CREATE TABLE IF NOT EXISTS spillover (
            spillover_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            type           TEXT,
            name           TEXT,
            country        TEXT,
            area           TEXT,
            status         TEXT,
            assigned_to    TEXT,
            external_id    TEXT,
            order_numbers  TEXT,
            content        TEXT,
            comment        TEXT,
            excel_row      INTEGER,
            match_key      TEXT NOT NULL,
            first_seen     TEXT,
            last_seen      TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_spillover_match ON spillover(match_key);

        -- Retail test-case rows — upserted each import, never deleted.
        CREATE TABLE IF NOT EXISTS retail (
            retail_id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            test_case_id                     TEXT NOT NULL,
            country                          TEXT NOT NULL,
            testcase_name                    TEXT,
            testcase_scenario                TEXT,
            status                           TEXT,
            assigned_to                      TEXT,
            key_user_responsible             TEXT,
            evidence_in_sharepoint           TEXT,
            sales_file                       TEXT,
            execution_started                TEXT,
            execution_completed              TEXT,
            store_no                         TEXT,
            order_number                     TEXT,
            old_order_numbers                TEXT,
            defect_id_ref                    TEXT,
            s4_sales_order                   TEXT,
            s4_billing_documents             TEXT,
            s4_journal_invoice_entry         TEXT,
            delivery_note                    TEXT,
            comment                          TEXT,
            reason_for_pass_with_reservation TEXT,
            excel_row                        INTEGER,
            match_key                        TEXT NOT NULL,
            first_seen                       TEXT,
            last_seen                        TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_retail_match ON retail(match_key);

        -- Authored retail annotations — NEVER written by the importer.
        CREATE TABLE IF NOT EXISTS retail_annotations (
            retail_id       INTEGER PRIMARY KEY REFERENCES retail(retail_id),
            next_step       TEXT,
            comment_history TEXT,
            updated_at      TEXT
        );

        -- Authored working fields — NEVER written by the importer.
        CREATE TABLE IF NOT EXISTS spillover_annotations (
            spillover_id           INTEGER PRIMARY KEY REFERENCES spillover(spillover_id),
            importance_for_signoff TEXT,
            next_step              TEXT,
            comment_history        TEXT,
            updated_at             TEXT
        );

        -- Manually tracked production defects for sign-off discussions.
        CREATE TABLE IF NOT EXISTS todos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            area       TEXT,
            kind       TEXT,
            topic      TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'open',
            priority   TEXT NOT NULL DEFAULT 'Medium',
            due_date   TEXT,
            for_whom   TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS meeting_prep (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting    TEXT NOT NULL,
            topic      TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'planned',
            note       TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS enhancements (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            area         TEXT,
            enhancement  TEXT NOT NULL,
            priority     TEXT NOT NULL DEFAULT 'Medium',
            status       TEXT NOT NULL DEFAULT 'not_started',
            created_at   TEXT,
            updated_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS followups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            with_whom  TEXT NOT NULL,
            topic      TEXT NOT NULL,
            when_next  TEXT,
            status     TEXT NOT NULL DEFAULT 'open',
            created_at TEXT,
            updated_at TEXT
        );

        -- Pick lists for the follow-up board: one row per selectable
        -- "with whom" party (kind='person') or group (kind='group').
        CREATE TABLE IF NOT EXISTS followup_options (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            kind       TEXT NOT NULL,
            value      TEXT NOT NULL,
            created_at TEXT,
            UNIQUE (kind, value)
        );

        CREATE TABLE IF NOT EXISTS known_prod_defects (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            technical_key     TEXT,
            short_description TEXT,
            numbers           TEXT,
            biz_impact        TEXT,
            description       TEXT,
            scenario          TEXT,
            refs              TEXT,
            next_steps        TEXT,
            comments          TEXT,
            created_at        TEXT,
            updated_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS prod_defect_review_comments (
            comment_id   TEXT PRIMARY KEY,
            defect_id    TEXT,
            defect_label TEXT,
            author       TEXT,
            comment_text TEXT NOT NULL,
            created_at   TEXT,
            export_id    TEXT,
            report_date  TEXT,
            imported_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS links (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            url         TEXT NOT NULL,
            area        TEXT,
            tool        TEXT,
            tags        TEXT,
            created_at  TEXT,
            updated_at  TEXT
        );

        -- link ↔ mini app references (2026-09-03 [USER]) — a Links-card link
        -- can belong to several apps; slugs validated against app/mini_apps.py
        CREATE TABLE IF NOT EXISTS link_apps (
            link_id    INTEGER NOT NULL,   -- FK links
            app_slug   TEXT NOT NULL,      -- app/mini_apps.APPS key
            created_at TEXT,
            PRIMARY KEY (link_id, app_slug)
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT,
            area        TEXT,
            topic       TEXT,
            comments    TEXT,
            tags        TEXT,
            created_at  TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS test_learnings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel     TEXT NOT NULL DEFAULT 'Retail',
            topic       TEXT,
            learning    TEXT NOT NULL,
            scenario    TEXT,
            tags        TEXT,
            created_at  TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS test_limitations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel     TEXT NOT NULL DEFAULT 'Retail',
            limitation  TEXT NOT NULL,
            scenario    TEXT,
            comment     TEXT,
            created_at  TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS cs_followups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            area        TEXT,
            jira_id     TEXT,
            topic       TEXT NOT NULL,
            description TEXT,
            next_step   TEXT,
            with_whom   TEXT,
            status      TEXT NOT NULL DEFAULT 'open',
            created_at  TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS encouragement_people (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS encouragements (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id  INTEGER NOT NULL REFERENCES encouragement_people(id),
            text       TEXT NOT NULL,
            date       TEXT NOT NULL,
            delivered  INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        -- Screenshot attachments linked to individual notes.
        -- Files live in data/uploads/; this table holds the reference.
        CREATE TABLE IF NOT EXISTS attachments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id       INTEGER NOT NULL REFERENCES notes(id),
            filename      TEXT NOT NULL,
            original_name TEXT,
            created_at    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_attachments_note ON attachments(note_id);

        -- Tracks which spillover items Marina has chosen to include in the status report.
        -- A row present = included; no row = not included.
        CREATE TABLE IF NOT EXISTS spillover_report_selection (
            spillover_id INTEGER PRIMARY KEY
        );

        -- Generic order-number log — entity_type + entity_id identify the parent row.
        -- Mirrors the notes table pattern so any entity type can have order lines.
        CREATE TABLE IF NOT EXISTS order_details (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type  TEXT NOT NULL,
            entity_id    TEXT NOT NULL,
            order_number TEXT,
            comment      TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_order_details_entity
            ON order_details(entity_type, entity_id);

        -- ECOM Gatekeeper Check — manually authored pre-handoff quality checks.
        -- Notes + order_details hang off this via entity_type='ecom_gatekeeper'.
        CREATE TABLE IF NOT EXISTS ecom_gatekeeper (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            jira_id       TEXT,
            solman_id     TEXT,
            testcase_name TEXT,
            status        TEXT NOT NULL DEFAULT 'open',
            next_step     TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Free-text bullet points shown in the status reports.
        -- report = 'spillover' | 'retail'
        CREATE TABLE IF NOT EXISTS report_comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            report     TEXT NOT NULL,
            comment    TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Shelf — catch-all store for inbox items that don't belong to a specific entity.
        -- Notes and attachments link via the shared notes table (entity_type='shelf').
        CREATE TABLE IF NOT EXISTS shelf (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            heading    TEXT,
            area       TEXT,
            category   TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    # Additive migrations — safe to run on existing DBs
    for col in ("sales_or_dtc TEXT",):  # Excel "Sales or DTC" column [USER 2026-07-10]
        try:
            conn.execute(f"ALTER TABLE defects ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("critical_for_signoff TEXT", "comment_for_signoff TEXT", "signoff_group TEXT",
                "with_whom TEXT"):  # Sales | MB — who follows up [USER 2026-07-09]
        try:
            conn.execute(f"ALTER TABLE spillover_annotations ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("comments TEXT", "confluence TEXT",
                # Known Production Issues [USER 2026-08-06]: channel/type
                # classify the entry; sub_case = the specific sub-case of
                # the scenario it happens in; how_to_detect = how Ops finds
                # these cases in the system; how_to_handle = what to do
                # about it. channel is optional, never backfilled/forced.
                "channel TEXT", "type TEXT",
                "sub_case TEXT", "how_to_detect TEXT", "how_to_handle TEXT",
                # Mark Fixed / Archive [USER 2026-08-27]: fixed items drop out
                # of the active list, downloads, email report and the ECOM
                # Spillover Report section (all read via the same
                # list_known_prod_defects default), but stay in the DB and
                # are reachable on the Archive view for reference/reopen.
                "status TEXT NOT NULL DEFAULT 'open'", "fixed_at TEXT",
                # Audience checkboxes [USER 2026-08-27] — which team(s) an
                # issue is relevant for; independent flags, an item can be
                # both/neither.
                "relevant_core_south INTEGER NOT NULL DEFAULT 0",
                "relevant_gbs_ops INTEGER NOT NULL DEFAULT 0",
                # Human-readable ID [USER 2026-08-27] — ECOM-001 / RETAIL-001,
                # assigned once at creation (app.db.reference._next_display_id),
                # never regenerated even if channel changes later. NULL when
                # no channel is set — the scheme has no prefix without one.
                "display_id TEXT"):
        try:
            conn.execute(f"ALTER TABLE known_prod_defects ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_known_prod_defects_display_id"
        " ON known_prod_defects(display_id) WHERE display_id IS NOT NULL")
    conn.commit()
    # Backfill display_id for pre-existing rows, oldest first per channel —
    # idempotent (only rows still NULL are touched, so a second run is a
    # no-op) [USER 2026-08-27].
    pending = conn.execute(
        "SELECT id, channel FROM known_prod_defects"
        " WHERE display_id IS NULL AND channel IN ('ECOM', 'Retail')"
        " ORDER BY created_at, id"
    ).fetchall()
    if pending:
        counters = {"ECOM": 0, "Retail": 0}
        prefixes = {"ECOM": "ECOM", "Retail": "RETAIL"}
        for rec_id, channel in pending:
            counters[channel] += 1
            conn.execute(
                "UPDATE known_prod_defects SET display_id = ? WHERE id = ?",
                (f"{prefixes[channel]}-{counters[channel]:03d}", rec_id))
        conn.commit()
    for col in ("action_needed INTEGER DEFAULT 0",):
        try:
            conn.execute(f"ALTER TABLE retail_annotations ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("store_no TEXT",):  # Excel "Store No." column [USER 2026-08-05]
        try:
            conn.execute(f"ALTER TABLE retail ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("kind TEXT",):
        try:
            conn.execute(f"ALTER TABLE todos ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    # notes: source tag + inbox reference fields / routing (2026-07-16 —
    # order_number/solman_id/jira_id feed the inbox auto-file matching;
    # route_to = Contact/Link/Follow-up incoming-bucket routing)
    for col in ("source TEXT", "order_number TEXT", "solman_id TEXT",
                "jira_id TEXT", "route_to TEXT"):
        try:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    # working-notes pages (2026-09-01 [USER]): the stand-alone Delegated
    # Ways-of-Working page joined the generic note_page mechanism the day
    # it was built — its notes move from ('delegated_wow','main') to
    # ('note_page','delegated_wow'). Idempotent: no rows match after the
    # first run.
    conn.execute(
        "UPDATE notes SET entity_type='note_page', entity_id='delegated_wow'"
        " WHERE entity_type='delegated_wow' AND entity_id='main'")
    conn.commit()
    for col in ("source_entity_type TEXT", "source_entity_id TEXT", "overall_topic TEXT"):
        try:
            conn.execute(f"ALTER TABLE meeting_prep ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("dtco2c INTEGER DEFAULT 0", "dtco2c_resp TEXT", "daily INTEGER DEFAULT 0"):
        try:
            conn.execute(f"ALTER TABLE defect_annotations ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("order_type TEXT", "docs_in_s4 INTEGER DEFAULT 0"):
        try:
            conn.execute(f"ALTER TABLE order_details ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("group_name TEXT",):
        try:
            conn.execute(f"ALTER TABLE followups ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    # call-out archive (2026-08-28 [USER]): archived call-outs leave the
    # live report but keep their dates
    for col in ("archived_at TEXT",):
        try:
            conn.execute(f"ALTER TABLE report_comments ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    # "With whom" / "Group" used to be free text on the follow-up board.  Seed
    # the pick lists from whatever is already in use, once, so nothing is lost
    # (duplicate spellings can then be merged by renaming an entry).
    if not conn.execute("SELECT COUNT(*) FROM followup_options").fetchone()[0]:
        now = datetime.now().isoformat(timespec="seconds")
        for kind, col in (("person", "with_whom"), ("group", "group_name")):
            values = conn.execute(
                f"SELECT DISTINCT {col} FROM followups"
                f" WHERE {col} IS NOT NULL AND TRIM({col}) <> ''"
            ).fetchall()
            for (val,) in values:
                conn.execute(
                    "INSERT INTO followup_options (kind, value, created_at)"
                    " VALUES (?, ?, ?) ON CONFLICT (kind, value) DO NOTHING",
                    (kind, val.strip(), now),
                )
        conn.commit()
    # Spillover match key changed from type||name||country to excel_row.
    # UPDATE preserves spillover_id values so FK links in spillover_annotations
    # stay intact.  The importer overwrites remaining columns on next run.
    conn.execute(
        "UPDATE spillover SET match_key = CAST(excel_row AS TEXT)"
        " WHERE match_key LIKE '%||%'"
    )
    conn.commit()
    return conn




def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


