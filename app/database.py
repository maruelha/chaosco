"""Storage layer — the ONLY module that writes SQL.

Public API:
    init_db(db_path)                        -> sqlite3.Connection  (startup only)
    get_connection(db_path)                 -> sqlite3.Connection  (per request)
    get_filter_options(conn)                -> dict
    list_defects(conn, ...)                 -> list[dict]
    get_defect(conn, defect_id)             -> dict | None
    upsert_defect_annotation(conn, ...)     -> None
    list_notes_for_defect(conn, defect_id) -> list[dict]
    get_note(conn, note_id)                 -> dict | None
    add_note(conn, ...)                     -> None
    update_note(conn, ...)                  -> None
    delete_note(conn, note_id)              -> None
    upsert_defects(conn, rows, today)       -> dict
    upsert_spillover_rows(conn, rows, today) -> dict
    get_spillover(conn, ...)                -> list[dict]
    get_spillover_by_id(conn, spillover_id) -> dict | None
    get_spillover_annotation(conn, spillover_id) -> dict | None
    upsert_spillover_annotation(conn, ...)  -> None
    upsert_retail_rows(conn, rows, today)   -> dict
    get_retail(conn, ...)                   -> list[dict]
    get_retail_filter_options(conn)         -> dict
    get_retail_by_id(conn, retail_id)       -> dict | None
    get_retail_annotation(conn, retail_id)  -> dict | None
    upsert_retail_annotation(conn, ...)     -> None
    list_known_prod_defects(conn)           -> list[dict]
    get_known_prod_defect(conn, id)         -> dict | None
    create_known_prod_defect(conn, ...)     -> dict
    update_known_prod_defect(conn, id, ...) -> dict | None
    delete_known_prod_defect(conn, id)      -> None
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

_DATE_FIELDS = frozenset({"date_reported", "date_closed"})

# All columns that are refreshed on every import (everything except defect_id and first_seen).
_UPSERT_COLS = [
    "channel", "solman_name", "raised_by", "order_number",
    "date_reported", "country", "scenario", "exists_in_production",
    "affected_testcases_raw", "retest_dependency", "blocks_execution",
    "defect_reason", "solman_status", "priority", "assigned_to",
    "tech_team", "date_closed", "excel_row",
]

_ALL_INSERT_COLS = ["defect_id"] + _UPSERT_COLS + ["first_seen", "last_seen"]

_UPSERT_SQL = """
    INSERT INTO defects ({cols})
    VALUES ({placeholders})
    ON CONFLICT(defect_id) DO UPDATE SET
        {updates}
""".format(
    cols=", ".join(_ALL_INSERT_COLS),
    placeholders=", ".join(f":{c}" for c in _ALL_INSERT_COLS),
    # first_seen intentionally absent from the UPDATE clause — it is set once on INSERT only
    updates=",\n        ".join(
        f"{c} = excluded.{c}" for c in _UPSERT_COLS + ["last_seen"]
    ),
)


# ---------------------------------------------------------------------------
# Spillover upsert SQL
# ---------------------------------------------------------------------------

_SPILLOVER_MUTABLE = [
    "type", "name", "country", "area", "status", "assigned_to",
    "external_id", "order_numbers", "content", "comment", "excel_row",
]
_SPILLOVER_INSERT_COLS = _SPILLOVER_MUTABLE + ["match_key", "first_seen", "last_seen"]

_SPILLOVER_UPSERT_SQL = """
    INSERT INTO spillover ({cols})
    VALUES ({placeholders})
    ON CONFLICT(match_key) DO UPDATE SET
        {updates}
""".format(
    cols=", ".join(_SPILLOVER_INSERT_COLS),
    placeholders=", ".join(f":{c}" for c in _SPILLOVER_INSERT_COLS),
    # first_seen and spillover_id intentionally absent from UPDATE — set once on INSERT only
    updates=",\n        ".join(
        f"{c} = excluded.{c}" for c in _SPILLOVER_MUTABLE + ["last_seen"]
    ),
)


# ---------------------------------------------------------------------------
# Retail upsert SQL
# ---------------------------------------------------------------------------

_RETAIL_MUTABLE = [
    "test_case_id", "country",
    "testcase_name", "testcase_scenario", "status", "assigned_to",
    "key_user_responsible", "evidence_in_sharepoint", "sales_file",
    "execution_started", "execution_completed", "order_number",
    "old_order_numbers", "defect_id_ref", "s4_sales_order",
    "s4_billing_documents", "s4_journal_invoice_entry", "delivery_note",
    "comment", "reason_for_pass_with_reservation", "excel_row",
]
_RETAIL_INSERT_COLS = _RETAIL_MUTABLE + ["match_key", "first_seen", "last_seen"]

_RETAIL_UPSERT_SQL = """
    INSERT INTO retail ({cols})
    VALUES ({placeholders})
    ON CONFLICT(match_key) DO UPDATE SET
        {updates}
""".format(
    cols=", ".join(_RETAIL_INSERT_COLS),
    placeholders=", ".join(f":{c}" for c in _RETAIL_INSERT_COLS),
    updates=",\n        ".join(
        f"{c} = excluded.{c}" for c in _RETAIL_MUTABLE + ["last_seen"]
    ),
)


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
    """)
    conn.commit()
    # Additive migrations — safe to run on existing DBs
    for col in ("critical_for_signoff TEXT", "comment_for_signoff TEXT"):
        try:
            conn.execute(f"ALTER TABLE spillover_annotations ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("comments TEXT", "confluence TEXT"):
        try:
            conn.execute(f"ALTER TABLE known_prod_defects ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("action_needed INTEGER DEFAULT 0",):
        try:
            conn.execute(f"ALTER TABLE retail_annotations ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("kind TEXT",):
        try:
            conn.execute(f"ALTER TABLE todos ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    for col in ("source TEXT",):
        try:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    # Spillover match key changed from type||name||country to excel_row.
    # UPDATE preserves spillover_id values so FK links in spillover_annotations
    # stay intact.  The importer overwrites remaining columns on next run.
    conn.execute(
        "UPDATE spillover SET match_key = CAST(excel_row AS TEXT)"
        " WHERE match_key LIKE '%||%'"
    )
    conn.commit()
    return conn


def _normalise_date(val: str) -> str | None:
    """Return YYYY-MM-DD string, or None for blank / unrecognised values."""
    if not val or not val.strip():
        return None
    # pandas may produce "2026-05-28 00:00:00" — take the date part only
    s = val.strip().split(" ")[0].split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else (val.strip() or None)


def _is_blank_row(row: dict) -> bool:
    """True when every field value (excluding the excel_row counter) is empty."""
    return all(not str(v).strip() for k, v in row.items() if k != "excel_row")


def _build_record(row: dict, defect_id: str, today: str) -> dict:
    rec: dict = {"defect_id": defect_id, "first_seen": today, "last_seen": today}
    for col in _UPSERT_COLS:
        if col == "excel_row":
            rec[col] = row.get("excel_row")
        elif col in _DATE_FIELDS:
            rec[col] = _normalise_date(row.get(col, "") or "")
        else:
            s = str(row.get(col, "") or "").strip()
            rec[col] = s if s else None
    return rec


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_filter_options(conn: sqlite3.Connection) -> dict:
    """Return distinct channel and solman_status values for building filter dropdowns."""
    channels = [r[0] for r in conn.execute(
        "SELECT DISTINCT channel FROM defects WHERE channel IS NOT NULL ORDER BY channel"
    ).fetchall()]
    statuses = [r[0] for r in conn.execute(
        "SELECT DISTINCT solman_status FROM defects WHERE solman_status IS NOT NULL ORDER BY solman_status"
    ).fetchall()]
    return {"channels": channels, "statuses": statuses}


def list_defects(
    conn: sqlite3.Connection,
    search: str | None = None,
    channel: str | None = None,
    statuses: list[str] | None = None,
    action_needed: str | None = None,
    exclude_statuses: list[str] | None = None,
) -> list[dict]:
    """Return defects rows with optional filters, LEFT JOINed with defect_annotations."""
    sql = """
        SELECT d.defect_id, d.channel, d.country, d.solman_status, d.priority,
               d.assigned_to, d.excel_row, d.solman_name, d.exists_in_production,
               COALESCE(a.action_needed, 0) AS action_needed,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'defect' AND n.entity_id = d.defect_id) AS note_count
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE 1=1
    """
    params: list = []
    if search:
        sql += " AND d.defect_id LIKE ?"
        params.append(f"%{search}%")
    if channel:
        sql += " AND d.channel = ?"
        params.append(channel)
    if statuses:
        ph = ",".join("?" * len(statuses))
        sql += f" AND d.solman_status IN ({ph})"
        params.extend(statuses)
    elif exclude_statuses:
        ph = ",".join("?" * len(exclude_statuses))
        sql += f" AND (d.solman_status IS NULL OR d.solman_status NOT IN ({ph}))"
        params.extend(exclude_statuses)
    if action_needed == "yes":
        sql += " AND COALESCE(a.action_needed, 0) = 1"
    elif action_needed == "no":
        sql += " AND COALESCE(a.action_needed, 0) = 0"
    sql += " ORDER BY d.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_defect(conn: sqlite3.Connection, defect_id: str) -> dict | None:
    """Return one defect with its annotation fields (NULL if no annotation row exists)."""
    sql = """
        SELECT d.*,
               a.description, a.business_impact, a.reach, a.retest_needs,
               a.next_step, COALESCE(a.action_needed, 0) AS action_needed,
               a.comments, a.updated_at
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE d.defect_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (defect_id,)))
    return rows[0] if rows else None


def upsert_defect_annotation(
    conn: sqlite3.Connection,
    defect_id: str,
    description: str | None,
    business_impact: str | None,
    reach: str | None,
    retest_needs: str | None,
    next_step: str | None,
    action_needed: bool,
    comments: str | None,
) -> None:
    """Insert or update the annotation row for defect_id. Never touches the defects table."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO defect_annotations
                (defect_id, description, business_impact, reach, retest_needs,
                 next_step, action_needed, comments, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(defect_id) DO UPDATE SET
                description     = excluded.description,
                business_impact = excluded.business_impact,
                reach           = excluded.reach,
                retest_needs    = excluded.retest_needs,
                next_step       = excluded.next_step,
                action_needed   = excluded.action_needed,
                comments        = excluded.comments,
                updated_at      = excluded.updated_at
            """,
            (defect_id, description, business_impact, reach, retest_needs,
             next_step, 1 if action_needed else 0, comments, now),
        )


def list_notes(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> list[dict]:
    """All notes for an entity, newest-first."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM notes WHERE entity_type = ? AND entity_id = ? ORDER BY created_at DESC",
        (entity_type, str(entity_id)),
    ))


def get_note(conn: sqlite3.Connection, note_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM notes WHERE id = ?", (note_id,)
    ))
    return rows[0] if rows else None


def add_note(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    heading: str | None,
    note_text: str | None,
    source: str | None = None,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT INTO notes (entity_type, entity_id, created_at, heading, note, source) VALUES (?, ?, ?, ?, ?, ?)",
            (entity_type, str(entity_id), now, heading, note_text, source),
        )


def update_note(
    conn: sqlite3.Connection,
    note_id: int,
    heading: str | None,
    note_text: str | None,
) -> None:
    with conn:
        conn.execute(
            "UPDATE notes SET heading = ?, note = ? WHERE id = ?",
            (heading, note_text, note_id),
        )


def delete_note(conn: sqlite3.Connection, note_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def upsert_defects(conn: sqlite3.Connection, rows: list[dict], today: str) -> dict:
    """Process rows and upsert into defects.  All writes are in one transaction.

    Returns:
        {
            "inserted": int,
            "updated": int,
            "skipped_blank_id": int,
            "skipped_duplicate": int,
            "ignored_blank": int,
            "skipped_rows": list[dict],   # rows to write to skip-log
        }
    """
    n_inserted = 0
    n_updated = 0
    n_skipped_blank_id = 0
    n_skipped_duplicate = 0
    n_ignored_blank = 0
    skipped_rows: list[dict] = []
    seen_ids: set[str] = set()

    with conn:
        existing_ids = {r[0] for r in conn.execute("SELECT defect_id FROM defects")}

        for row in rows:
            # 1. Entirely blank — ignore silently
            if _is_blank_row(row):
                n_ignored_blank += 1
                continue

            defect_id = str(row.get("defect_id", "") or "").strip()

            # 2. Has content but no defect_id — skip and log
            if not defect_id:
                n_skipped_blank_id += 1
                skipped_rows.append({**row, "reason": "blank_defect_id"})
                continue

            # 3. Duplicate defect_id within this import — keep first, skip rest
            if defect_id in seen_ids:
                n_skipped_duplicate += 1
                skipped_rows.append({**row, "reason": "duplicate_defect_id"})
                continue

            seen_ids.add(defect_id)
            is_new = defect_id not in existing_ids

            conn.execute(_UPSERT_SQL, _build_record(row, defect_id, today))

            if is_new:
                n_inserted += 1
                existing_ids.add(defect_id)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_blank_id": n_skipped_blank_id,
        "skipped_duplicate": n_skipped_duplicate,
        "ignored_blank": n_ignored_blank,
        "skipped_rows": skipped_rows,
    }


# ---------------------------------------------------------------------------
# Spillover storage
# ---------------------------------------------------------------------------

def _retail_match_key(test_case_id: str, country: str) -> str:
    return "||".join(
        re.sub(r"\s+", " ", str(p or "")).strip().lower()
        for p in (test_case_id, country)
    )


def _spillover_match_key(excel_row: int | str) -> str:
    """Match key is the Excel row number — stable regardless of name/country edits."""
    return str(excel_row)


def upsert_spillover_rows(conn: sqlite3.Connection, rows: list[dict], today: str) -> dict:
    """Process parsed spillover rows and upsert into the spillover table.

    Rows with a non-empty _skip_reason (blank name) are collected and returned for
    skip-log writing; they are never inserted. Fully blank rows are expected to have
    been removed by parse_spillover before reaching here.

    Returns:
        {
            "inserted": int,
            "updated": int,
            "skipped_blank_name": int,
            "skipped_rows": list[dict],
        }
    """
    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    skipped_rows: list[dict] = []

    with conn:
        existing_keys = {r[0] for r in conn.execute("SELECT match_key FROM spillover")}

        for row in rows:
            if row.get("_skip_reason"):
                n_skipped += 1
                skipped_rows.append({**row, "reason": row["_skip_reason"]})
                continue

            mk = _spillover_match_key(row.get("excel_row", 0))
            is_new = mk not in existing_keys

            def _s(field: str):
                v = str(row.get(field, "") or "").strip()
                return v if v else None

            rec = {
                "type":          _s("type"),
                "name":          _s("name"),
                "country":       _s("country"),
                "area":          _s("area"),
                "status":        _s("status"),
                "assigned_to":   _s("assigned_to"),
                "external_id":   _s("external_id"),
                "order_numbers": _s("order_numbers"),
                "content":       _s("content"),
                "comment":       _s("comment"),
                "excel_row":     row.get("excel_row"),
                "match_key":     mk,
                "first_seen":    today,
                "last_seen":     today,
            }
            conn.execute(_SPILLOVER_UPSERT_SQL, rec)

            if is_new:
                n_inserted += 1
                existing_keys.add(mk)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_blank_name": n_skipped,
        "skipped_rows": skipped_rows,
    }


def get_spillover(
    conn: sqlite3.Connection,
    statuses: list[str] | None = None,
    areas: list[str] | None = None,
    types: list[str] | None = None,
    assignees: list[str] | None = None,
    search: str | None = None,
    exclude_statuses: list[str] | None = None,
) -> list[dict]:
    """Return spillover rows LEFT JOINed with annotations. All filters are optional.

    Each filter accepts a list; multiple values are combined with IN (...).
    exclude_statuses: hidden when no explicit status filter is active.
    """
    sql = """
        SELECT s.*,
               a.importance_for_signoff, a.next_step, a.comment_history,
               a.critical_for_signoff, a.comment_for_signoff,
               a.updated_at AS annotation_updated_at
        FROM spillover s
        LEFT JOIN spillover_annotations a ON a.spillover_id = s.spillover_id
        WHERE 1=1
    """
    params: list = []

    def _in(col: str, values: list[str]) -> None:
        ph = ",".join("?" * len(values))
        sql_parts.append(f" AND {col} IN ({ph})")
        params.extend(values)

    sql_parts: list[str] = []
    if statuses:
        _in("s.status", statuses)
    if areas:
        _in("s.area", areas)
    if types:
        _in("s.type", types)
    if assignees:
        _in("s.assigned_to", assignees)
    sql += "".join(sql_parts)

    if search:
        sql += " AND (s.name LIKE ? OR s.external_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if exclude_statuses and not statuses:
        ph = ",".join("?" * len(exclude_statuses))
        sql += f" AND (s.status IS NULL OR s.status NOT IN ({ph}))"
        params.extend(exclude_statuses)
    sql += " ORDER BY s.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_spillover_filter_options(conn: sqlite3.Connection) -> dict:
    """Return distinct values for each filter dropdown."""
    def _vals(col: str) -> list:
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM spillover WHERE {col} IS NOT NULL ORDER BY {col}"
        ).fetchall()]
    return {
        "areas":     _vals("area"),
        "types":     _vals("type"),
        "statuses":  _vals("status"),
        "assignees": _vals("assigned_to"),
    }


def get_spillover_by_id(conn: sqlite3.Connection, spillover_id: int) -> dict | None:
    """Return one spillover row with its annotation fields (NULL if no annotation exists)."""
    sql = """
        SELECT s.*,
               a.importance_for_signoff, a.next_step, a.comment_history,
               a.critical_for_signoff, a.comment_for_signoff,
               a.updated_at AS annotation_updated_at
        FROM spillover s
        LEFT JOIN spillover_annotations a ON a.spillover_id = s.spillover_id
        WHERE s.spillover_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (spillover_id,)))
    return rows[0] if rows else None


def get_spillover_annotation(conn: sqlite3.Connection, spillover_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM spillover_annotations WHERE spillover_id = ?", (spillover_id,)
    ))
    return rows[0] if rows else None


def upsert_retail_rows(conn: sqlite3.Connection, rows: list[dict], today: str) -> dict:
    """Match-key upsert for retail rows. Never deletes. Returns counts + skipped rows."""
    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    skipped_rows: list[dict] = []

    with conn:
        existing_keys = {r[0] for r in conn.execute("SELECT match_key FROM retail")}

        for row in rows:
            if row.get("_skip_reason"):
                n_skipped += 1
                skipped_rows.append({**row, "reason": row["_skip_reason"]})
                continue

            mk = _retail_match_key(
                row.get("test_case_id", "") or "",
                row.get("country", "") or "",
            )
            is_new = mk not in existing_keys

            def _s(field: str):
                v = str(row.get(field, "") or "").strip()
                return v if v else None

            rec = {col: _s(col) for col in _RETAIL_MUTABLE if col != "excel_row"}
            rec["excel_row"] = row.get("excel_row")
            rec["match_key"] = mk
            rec["first_seen"] = today
            rec["last_seen"] = today

            conn.execute(_RETAIL_UPSERT_SQL, rec)
            if is_new:
                n_inserted += 1
                existing_keys.add(mk)
            else:
                n_updated += 1

    return {
        "inserted": n_inserted,
        "updated": n_updated,
        "skipped_blank_key": n_skipped,
        "skipped_rows": skipped_rows,
    }


def get_retail(
    conn: sqlite3.Connection,
    statuses: list[str] | None = None,
    assignees: list[str] | None = None,
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    search_defect: str | None = None,
    search_order: str | None = None,
    search_billing: str | None = None,
    action_needed: str | None = None,
) -> list[dict]:
    """Return retail rows LEFT JOINed with annotations. All filters/searches optional and ANDed."""
    sql = """
        SELECT r.*,
               a.next_step, a.comment_history,
               a.updated_at AS annotation_updated_at,
               COALESCE(a.action_needed, 0) AS action_needed,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'retail'
                AND n.entity_id = CAST(r.retail_id AS TEXT)) AS note_count
        FROM retail r
        LEFT JOIN retail_annotations a ON a.retail_id = r.retail_id
        WHERE 1=1
    """
    params: list = []
    sql_parts: list[str] = []

    def _in(col: str, values: list[str]) -> None:
        ph = ",".join("?" * len(values))
        sql_parts.append(f" AND {col} IN ({ph})")
        params.extend(values)

    if statuses:   _in("r.status", statuses)
    if assignees:  _in("r.assigned_to", assignees)
    if countries:  _in("r.country", countries)
    if scenarios:  _in("r.testcase_scenario", scenarios)
    sql += "".join(sql_parts)

    if search_defect:
        sql += " AND r.defect_id_ref LIKE ?"
        params.append(f"%{search_defect}%")
    if search_order:
        sql += " AND r.order_number LIKE ?"
        params.append(f"%{search_order}%")
    if search_billing:
        sql += " AND r.s4_billing_documents LIKE ?"
        params.append(f"%{search_billing}%")

    if action_needed == "yes":
        sql += " AND COALESCE(a.action_needed, 0) = 1"
    elif action_needed == "no":
        sql += " AND COALESCE(a.action_needed, 0) = 0"

    sql += " ORDER BY r.excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def get_retail_filter_options(conn: sqlite3.Connection) -> dict:
    def _vals(col: str) -> list:
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM retail WHERE {col} IS NOT NULL ORDER BY {col}"
        ).fetchall()]
    return {
        "statuses":  _vals("status"),
        "assignees": _vals("assigned_to"),
        "countries": _vals("country"),
        "scenarios": _vals("testcase_scenario"),
    }


def get_retail_by_id(conn: sqlite3.Connection, retail_id: int) -> dict | None:
    sql = """
        SELECT r.*,
               a.next_step, a.comment_history,
               a.updated_at AS annotation_updated_at,
               COALESCE(a.action_needed, 0) AS action_needed,
               (SELECT COUNT(*) FROM notes n WHERE n.entity_type = 'retail'
                AND n.entity_id = CAST(r.retail_id AS TEXT)) AS note_count
        FROM retail r
        LEFT JOIN retail_annotations a ON a.retail_id = r.retail_id
        WHERE r.retail_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (retail_id,)))
    return rows[0] if rows else None


def get_retail_annotation(conn: sqlite3.Connection, retail_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM retail_annotations WHERE retail_id = ?", (retail_id,)
    ))
    return rows[0] if rows else None


def upsert_retail_annotation(
    conn: sqlite3.Connection,
    retail_id: int,
    next_step: str | None,
    comment_history: str | None,
    action_needed: int = 0,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO retail_annotations (retail_id, next_step, comment_history, action_needed, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(retail_id) DO UPDATE SET
                next_step       = excluded.next_step,
                comment_history = excluded.comment_history,
                action_needed   = excluded.action_needed,
                updated_at      = excluded.updated_at
            """,
            (retail_id, next_step, comment_history, action_needed, now),
        )


def get_retail_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {status_value: count} for all rows in the retail table.

    Kept as a standalone function so a future step can persist the raw counts
    before passing them to reporter.compute_retail_report().
    """
    rows = conn.execute(
        "SELECT COALESCE(status, '') AS status, COUNT(*) AS cnt FROM retail GROUP BY status"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def list_known_prod_defects(conn: sqlite3.Connection) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM known_prod_defects ORDER BY created_at DESC"
    ))


def get_known_prod_defect(conn: sqlite3.Connection, record_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM known_prod_defects WHERE id = ?", (record_id,)
    ))
    return rows[0] if rows else None


def create_known_prod_defect(
    conn: sqlite3.Connection,
    short_description: str | None,
    scenario: str | None,
    description: str | None,
    biz_impact: str | None,
    numbers: str | None,
    refs: str | None,
    next_steps: str | None,
    comments: str | None,
    confluence: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            """INSERT INTO known_prod_defects
               (short_description, scenario, description, biz_impact,
                numbers, refs, next_steps, comments, confluence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (short_description, scenario, description, biz_impact,
             numbers, refs, next_steps, comments, confluence, now, now),
        )
        new_id = cur.lastrowid
    return get_known_prod_defect(conn, new_id)


def update_known_prod_defect(
    conn: sqlite3.Connection,
    record_id: int,
    short_description: str | None,
    scenario: str | None,
    description: str | None,
    biz_impact: str | None,
    numbers: str | None,
    refs: str | None,
    next_steps: str | None,
    comments: str | None,
    confluence: str | None,
) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """UPDATE known_prod_defects SET
               short_description=?, scenario=?, description=?, biz_impact=?,
               numbers=?, refs=?, next_steps=?, comments=?, confluence=?, updated_at=?
               WHERE id=?""",
            (short_description, scenario, description, biz_impact,
             numbers, refs, next_steps, comments, confluence, now, record_id),
        )
    return get_known_prod_defect(conn, record_id)


def delete_known_prod_defect(conn: sqlite3.Connection, record_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM known_prod_defects WHERE id = ?", (record_id,))


def upsert_spillover_annotation(
    conn: sqlite3.Connection,
    spillover_id: int,
    importance_for_signoff: str | None,
    next_step: str | None,
    comment_history: str | None,
    critical_for_signoff: str | None = None,
    comment_for_signoff: str | None = None,
) -> None:
    """Insert or update the annotation for a spillover row. Never touches the spillover table."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO spillover_annotations
                (spillover_id, importance_for_signoff, next_step, comment_history,
                 critical_for_signoff, comment_for_signoff, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(spillover_id) DO UPDATE SET
                importance_for_signoff = excluded.importance_for_signoff,
                next_step              = excluded.next_step,
                comment_history        = excluded.comment_history,
                critical_for_signoff   = excluded.critical_for_signoff,
                comment_for_signoff    = excluded.comment_for_signoff,
                updated_at             = excluded.updated_at
            """,
            (spillover_id, importance_for_signoff, next_step, comment_history,
             critical_for_signoff, comment_for_signoff, now),
        )


# ---------------------------------------------------------------------------
# Meeting prep
# ---------------------------------------------------------------------------

MEETING_OPTIONS = [
    "Balazs",
    "GPO",
    "Sync&Solve",
    "DTC O2C Daily",
    "Sales ECOM daily",
    "Other",
]


def get_meeting_prep(conn: sqlite3.Connection,
                     meeting: str | None = None,
                     status: str | None = None) -> list[dict]:
    where, params = [], []
    if meeting:
        where.append("m.meeting = ?")
        params.append(meeting)
    if status:
        where.append("m.status = ?")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT m.*,
               COUNT(n.id) AS note_count
        FROM   meeting_prep m
        LEFT JOIN notes n ON n.entity_type = 'meeting_prep' AND n.entity_id = CAST(m.id AS TEXT)
        {clause}
        GROUP BY m.id
        ORDER BY m.id DESC
    """, params).fetchall()
    cur = conn.execute("SELECT m.*, 0 AS note_count FROM meeting_prep m LIMIT 0")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def add_meeting_prep(conn: sqlite3.Connection, meeting: str, topic: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO meeting_prep (meeting, topic, status, created_at, updated_at)"
        " VALUES (?, ?, 'planned', ?, ?)",
        (meeting, topic, now, now),
    )
    conn.commit()
    return cur.lastrowid


def set_meeting_prep_status(conn: sqlite3.Connection, item_id: int, status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE meeting_prep SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, item_id),
    )
    conn.commit()


def set_meeting_prep_note(conn: sqlite3.Connection, item_id: int, note: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE meeting_prep SET note = ?, updated_at = ? WHERE id = ?",
        (note, now, item_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Enhancements
# ---------------------------------------------------------------------------

ENHANCEMENT_PRIORITIES = ["High", "Medium", "Low"]
ENHANCEMENT_STATUSES   = ["not_started", "in_progress", "closed"]


def get_enhancements(conn: sqlite3.Connection,
                     area: str | None = None,
                     priority: str | None = None,
                     status: str | None = None,
                     include_closed: bool = False) -> list[dict]:
    where, params = [], []
    if not include_closed:
        where.append("status != 'closed'")
    elif status:
        where.append("status = ?")
        params.append(status)
    if area:
        where.append("area = ?")
        params.append(area)
    if priority:
        where.append("priority = ?")
        params.append(priority)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    order  = "ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, id"
    rows = conn.execute(
        f"SELECT * FROM enhancements {clause} {order}", params
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM enhancements LIMIT 0").description]
    return [dict(zip(cols, r)) for r in rows]


def get_enhancement_areas(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT area FROM enhancements WHERE area IS NOT NULL ORDER BY area"
    ).fetchall()
    return [r[0] for r in rows]


def add_enhancement(conn: sqlite3.Connection, area: str, enhancement: str,
                    priority: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO enhancements (area, enhancement, priority, status, created_at, updated_at)"
        " VALUES (?, ?, ?, 'not_started', ?, ?)",
        (area or None, enhancement, priority, now, now),
    )
    conn.commit()
    return cur.lastrowid


def set_enhancement_status(conn: sqlite3.Connection, item_id: int, status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE enhancements SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, item_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# To-do list
# ---------------------------------------------------------------------------

TODO_STATUSES   = ["open", "in_progress", "blocked", "closed"]
TODO_PRIORITIES = ["High", "Medium", "Low"]


def get_todos(conn: sqlite3.Connection,
              area: str | None = None,
              status: str | None = None,
              priority: str | None = None,
              for_whom: str | None = None,
              due_date: str | None = None,
              include_closed: bool = False) -> list[dict]:
    where, params = [], []
    if not include_closed:
        where.append("t.status != 'closed'")
    if area:
        where.append("t.area = ?"); params.append(area)
    if status:
        where.append("t.status = ?"); params.append(status)
    if priority:
        where.append("t.priority = ?"); params.append(priority)
    if for_whom:
        where.append("t.for_whom = ?"); params.append(for_whom)
    if due_date:
        where.append("t.due_date = ?"); params.append(due_date)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT t.*,
               COUNT(n.id) AS note_count
        FROM   todos t
        LEFT JOIN notes n ON n.entity_type = 'todo' AND n.entity_id = CAST(t.id AS TEXT)
        {clause}
        GROUP BY t.id
        ORDER BY
          CASE t.status WHEN 'blocked' THEN 0 WHEN 'in_progress' THEN 1
                        WHEN 'open' THEN 2 ELSE 3 END,
          CASE t.priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
          t.due_date NULLS LAST
    """, params).fetchall()
    cur = conn.execute("SELECT t.*, 0 AS note_count FROM todos t LIMIT 0")
    col_names = [d[0] for d in cur.description]
    return [dict(zip(col_names, r)) for r in rows]


def get_todo_filter_options(conn: sqlite3.Connection) -> dict:
    areas    = [r[0] for r in conn.execute(
        "SELECT DISTINCT area FROM todos WHERE area IS NOT NULL ORDER BY area").fetchall()]
    for_whom = [r[0] for r in conn.execute(
        "SELECT DISTINCT for_whom FROM todos WHERE for_whom IS NOT NULL ORDER BY for_whom").fetchall()]
    return {"areas": areas, "for_whom": for_whom}


def add_todo(conn: sqlite3.Connection, area: str, kind: str, topic: str,
             priority: str, due_date: str, for_whom: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO todos (area, kind, topic, status, priority, due_date, for_whom, created_at, updated_at)"
        " VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)",
        (area or None, kind or None, topic, priority, due_date or None, for_whom or None, now, now),
    )
    conn.commit()
    return cur.lastrowid


def set_todo_status(conn: sqlite3.Connection, todo_id: int, status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("UPDATE todos SET status=?, updated_at=? WHERE id=?", (status, now, todo_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

FOLLOWUP_STATUSES = ["open", "in_progress", "done"]


def get_followups(conn: sqlite3.Connection,
                  with_whom: str | None = None,
                  when_next: str | None = None,
                  status: str | None = None,
                  include_done: bool = False) -> list[dict]:
    where, params = [], []
    if not include_done:
        where.append("f.status != 'done'")
    if with_whom:
        where.append("f.with_whom = ?"); params.append(with_whom)
    if when_next:
        where.append("f.when_next = ?"); params.append(when_next)
    if status:
        where.append("f.status = ?"); params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT f.*,
               COUNT(n.id) AS note_count
        FROM   followups f
        LEFT JOIN notes n ON n.entity_type = 'followup' AND n.entity_id = CAST(f.id AS TEXT)
        {clause}
        GROUP BY f.id
        ORDER BY
          CASE f.status WHEN 'in_progress' THEN 0 WHEN 'open' THEN 1 ELSE 2 END,
          f.when_next NULLS LAST
    """, params).fetchall()
    cur = conn.execute("SELECT f.*, 0 AS note_count FROM followups f LIMIT 0")
    col_names = [d[0] for d in cur.description]
    return [dict(zip(col_names, r)) for r in rows]


def get_followup_filter_options(conn: sqlite3.Connection) -> dict:
    with_whom = [r[0] for r in conn.execute(
        "SELECT DISTINCT with_whom FROM followups WHERE with_whom IS NOT NULL ORDER BY with_whom"
    ).fetchall()]
    return {"with_whom": with_whom}


def add_followup(conn: sqlite3.Connection, with_whom: str, topic: str, when_next: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO followups (with_whom, topic, when_next, status, created_at, updated_at)"
        " VALUES (?, ?, ?, 'open', ?, ?)",
        (with_whom, topic, when_next or None, now, now),
    )
    conn.commit()
    return cur.lastrowid


def set_followup_status(conn: sqlite3.Connection, followup_id: int, status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("UPDATE followups SET status=?, updated_at=? WHERE id=?", (status, now, followup_id))
    conn.commit()
