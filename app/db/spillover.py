"""Core South Spillover — imported rows, annotations, report selection

Part of the app.db package (refactoring step 4) — split out of the old
monolithic database.py. Callers keep using `from app import database`,
which re-exports everything from these modules.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts

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
    critical: list[str] | None = None,
    with_whom: list[str] | None = None,
    in_report: str | None = None,
    search: str | None = None,
    exclude_statuses: list[str] | None = None,
) -> list[dict]:
    """Return spillover rows LEFT JOINed with annotations. All filters are optional.

    Each filter accepts a list; multiple values are combined with IN (...).
    exclude_statuses: hidden when no explicit status filter is active.
    in_report: 'yes' = only lines picked for the status report, 'no' = the rest.
    """
    sql = """
        SELECT s.*,
               a.importance_for_signoff, a.next_step, a.comment_history,
               a.critical_for_signoff, a.comment_for_signoff, a.signoff_group,
               a.with_whom,
               a.updated_at AS annotation_updated_at,
               EXISTS(SELECT 1 FROM spillover_report_selection sel
                      WHERE sel.spillover_id = s.spillover_id) AS in_report,
               (SELECT COUNT(*) FROM notes n
                WHERE n.entity_type = 'spillover' AND n.entity_id = CAST(s.spillover_id AS TEXT)
               ) AS note_count
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
    if critical:
        _in("a.critical_for_signoff", critical)
    if with_whom:
        _in("a.with_whom", with_whom)
    sql += "".join(sql_parts)

    if in_report == "yes":
        sql += (" AND s.spillover_id IN"
                " (SELECT spillover_id FROM spillover_report_selection)")
    elif in_report == "no":
        sql += (" AND s.spillover_id NOT IN"
                " (SELECT spillover_id FROM spillover_report_selection)")

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
               a.critical_for_signoff, a.comment_for_signoff, a.signoff_group,
               a.updated_at AS annotation_updated_at
        FROM spillover s
        LEFT JOIN spillover_annotations a ON a.spillover_id = s.spillover_id
        WHERE s.spillover_id = ?
    """
    rows = _rows_to_dicts(conn.execute(sql, (spillover_id,)))
    return rows[0] if rows else None


def set_spillover_next_step(conn: sqlite3.Connection, spillover_id: int,
                            next_step: str | None) -> None:
    """Only-this-field upsert (used by the next-step archive component)."""
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO spillover_annotations (spillover_id, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(spillover_id) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (spillover_id, next_step or None, now))


def set_spillover_with_whom(conn: sqlite3.Connection, spillover_id: int,
                            with_whom: str | None) -> None:
    """Who follows up: 'Sales' | 'MB' | None [USER 2026-07-09]. Touches ONLY
    this field — the other annotation fields stay as they are."""
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO spillover_annotations (spillover_id, with_whom, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(spillover_id) DO UPDATE SET
                with_whom  = excluded.with_whom,
                updated_at = excluded.updated_at
        """, (spillover_id, with_whom or None, now))


def get_spillover_annotation(conn: sqlite3.Connection, spillover_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM spillover_annotations WHERE spillover_id = ?", (spillover_id,)
    ))
    return rows[0] if rows else None




def upsert_spillover_annotation(
    conn: sqlite3.Connection,
    spillover_id: int,
    importance_for_signoff: str | None,
    next_step: str | None,
    comment_history: str | None,
    critical_for_signoff: str | None = None,
    comment_for_signoff: str | None = None,
    signoff_group: str | None = None,
) -> None:
    """Insert or update the annotation for a spillover row. Never touches the spillover table."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO spillover_annotations
                (spillover_id, importance_for_signoff, next_step, comment_history,
                 critical_for_signoff, comment_for_signoff, signoff_group, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(spillover_id) DO UPDATE SET
                importance_for_signoff = excluded.importance_for_signoff,
                next_step              = excluded.next_step,
                comment_history        = excluded.comment_history,
                critical_for_signoff   = excluded.critical_for_signoff,
                comment_for_signoff    = excluded.comment_for_signoff,
                signoff_group          = excluded.signoff_group,
                updated_at             = excluded.updated_at
            """,
            (spillover_id, importance_for_signoff, next_step, comment_history,
             critical_for_signoff, comment_for_signoff, signoff_group, now),
        )




def get_spillover_report_ids(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute("SELECT spillover_id FROM spillover_report_selection").fetchall()
    return {r[0] for r in rows}


def toggle_spillover_report_item(conn: sqlite3.Connection, spillover_id: int) -> bool:
    """Toggle inclusion. Returns True if now included, False if now excluded."""
    exists = conn.execute(
        "SELECT 1 FROM spillover_report_selection WHERE spillover_id = ?", (spillover_id,)
    ).fetchone()
    if exists:
        conn.execute("DELETE FROM spillover_report_selection WHERE spillover_id = ?", (spillover_id,))
        conn.commit()
        return False
    conn.execute("INSERT INTO spillover_report_selection (spillover_id) VALUES (?)", (spillover_id,))
    conn.commit()
    return True


def include_spillover_report_ids(conn: sqlite3.Connection, ids: list[int]) -> None:
    for sid in ids:
        conn.execute(
            "INSERT OR IGNORE INTO spillover_report_selection (spillover_id) VALUES (?)", (sid,)
        )
    conn.commit()


def clear_spillover_report(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM spillover_report_selection")
    conn.commit()


def get_spillover_report_items(conn: sqlite3.Connection) -> list[dict]:
    """Return spillover rows + annotations for all selected items, ordered by area then name."""
    cur = conn.execute("""
        SELECT s.spillover_id, s.name, s.area, s.status, s.order_numbers,
               a.next_step, a.critical_for_signoff, a.comment_for_signoff,
               a.importance_for_signoff, a.signoff_group, a.with_whom
        FROM spillover s
        JOIN spillover_report_selection sel ON sel.spillover_id = s.spillover_id
        LEFT JOIN spillover_annotations a ON a.spillover_id = s.spillover_id
        ORDER BY s.area NULLS LAST, s.name
    """)
    return _rows_to_dicts(cur)


def set_spillover_comment_for_signoff(conn: sqlite3.Connection, spillover_id: int,
                                      comment: str | None) -> None:
    """Only-this-field upsert (inline comment on the report table)."""
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute("""
            INSERT INTO spillover_annotations (spillover_id, comment_for_signoff, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(spillover_id) DO UPDATE SET
                comment_for_signoff = excluded.comment_for_signoff,
                updated_at          = excluded.updated_at
        """, (spillover_id, comment or None, now))


# ---------------------------------------------------------------------------
# ECOM Gatekeeper Check
# ---------------------------------------------------------------------------

