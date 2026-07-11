"""Unified notes + inbox + attachments (all entity types)

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


# ---------------------------------------------------------------------------
# Inbox — unfiled notes (entity_type='input', entity_id='inbox')
# ---------------------------------------------------------------------------

_INBOX_TARGET_TYPES = {"defect", "retail", "spillover", "ecom", "ecom_gatekeeper", "jira", "test_learning", "followup", "shelf", "topic", "contact", "link"}


def add_inbox_item(conn: sqlite3.Connection, heading: str | None, note_text: str | None) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO notes (entity_type, entity_id, created_at, heading, note)"
            " VALUES ('input', 'inbox', ?, ?, ?)",
            (now, heading, note_text),
        )
    return cur.lastrowid


def list_inbox_items(conn: sqlite3.Connection) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT n.*, COUNT(a.id) as att_count FROM notes n"
        " LEFT JOIN attachments a ON a.note_id = n.id"
        " WHERE n.entity_type = 'input' AND n.entity_id = 'inbox'"
        " GROUP BY n.id ORDER BY n.created_at DESC"
    ))


def get_inbox_item(conn: sqlite3.Connection, note_id: int) -> dict | None:
    cur = conn.execute(
        "SELECT * FROM notes WHERE id = ? AND entity_type = 'input' AND entity_id = 'inbox'",
        (note_id,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def count_inbox_items(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE entity_type = 'input' AND entity_id = 'inbox'"
    ).fetchone()
    return row[0] if row else 0


def file_inbox_item(
    conn: sqlite3.Connection, note_id: int, target_type: str, target_id: str
) -> bool:
    if target_type not in _INBOX_TARGET_TYPES:
        return False
    note = get_note(conn, note_id)
    if note is None or note["entity_type"] != "input" or note["entity_id"] != "inbox":
        return False
    target_exists = False
    if target_type == "defect":
        target_exists = conn.execute(
            "SELECT 1 FROM defects WHERE defect_id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "retail":
        target_exists = conn.execute(
            "SELECT 1 FROM retail WHERE retail_id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "spillover":
        target_exists = conn.execute(
            "SELECT 1 FROM spillover WHERE spillover_id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "ecom":
        target_exists = conn.execute(
            "SELECT 1 FROM ecom WHERE ecom_id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "ecom_gatekeeper":
        target_exists = conn.execute(
            "SELECT 1 FROM ecom_gatekeeper WHERE id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "jira":
        target_exists = conn.execute(
            "SELECT 1 FROM jira_issues WHERE jira_key = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "topic":
        target_exists = conn.execute(
            "SELECT 1 FROM topics WHERE id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "contact":
        target_exists = conn.execute(
            "SELECT 1 FROM contacts WHERE id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "link":
        target_exists = conn.execute(
            "SELECT 1 FROM links WHERE id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "test_learning":
        target_exists = conn.execute(
            "SELECT 1 FROM test_learnings WHERE id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "followup":
        target_exists = conn.execute(
            "SELECT 1 FROM followups WHERE id = ?", (target_id,)
        ).fetchone() is not None
    elif target_type == "shelf":
        target_exists = conn.execute(
            "SELECT 1 FROM shelf WHERE id = ?", (target_id,)
        ).fetchone() is not None
    if not target_exists:
        return False
    with conn:
        conn.execute(
            "UPDATE notes SET entity_type = ?, entity_id = ?"
            " WHERE id = ? AND entity_type = 'input'",
            (target_type, str(target_id), note_id),
        )
    return True


def delete_inbox_item(conn: sqlite3.Connection, note_id: int) -> list[str]:
    """Delete note + attachment rows; return filenames for caller to unlink from disk."""
    rows = _rows_to_dicts(conn.execute(
        "SELECT filename FROM attachments WHERE note_id = ?", (note_id,)
    ))
    filenames = [r["filename"] for r in rows]
    with conn:
        conn.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))
        conn.execute(
            "DELETE FROM notes WHERE id = ? AND entity_type = 'input'", (note_id,)
        )
    return filenames


def search_targets(conn: sqlite3.Connection, target_type: str, q: str) -> list[dict]:
    """Return [{"value": ..., "label": ...}] candidates for the inbox filing picker."""
    if target_type not in _INBOX_TARGET_TYPES:
        return []
    like = f"%{q.strip()}%"
    if target_type == "defect":
        rows = _rows_to_dicts(conn.execute(
            "SELECT defect_id, solman_name FROM defects"
            " WHERE defect_id LIKE ? OR solman_name LIKE ? ORDER BY defect_id LIMIT 20",
            (like, like),
        ))
        return [{"value": r["defect_id"],
                 "label": f"{r['defect_id']} — {r['solman_name'] or ''}".rstrip(" —")}
                for r in rows]
    elif target_type == "retail":
        rows = _rows_to_dicts(conn.execute(
            "SELECT retail_id, test_case_id, testcase_name, country FROM retail"
            " WHERE test_case_id LIKE ? OR testcase_name LIKE ? OR country LIKE ?"
            " ORDER BY test_case_id LIMIT 20",
            (like, like, like),
        ))
        return [{"value": str(r["retail_id"]),
                 "label": f"{r['test_case_id']} ({r['country']}) — {r['testcase_name'] or ''}".rstrip(" —")}
                for r in rows]
    elif target_type == "spillover":
        rows = _rows_to_dicts(conn.execute(
            "SELECT spillover_id, name, area, country FROM spillover"
            " WHERE name LIKE ? OR area LIKE ? OR country LIKE ? ORDER BY name LIMIT 20",
            (like, like, like),
        ))
        return [{"value": str(r["spillover_id"]),
                 "label": f"{r['name'] or '—'} ({r['area'] or ''}, {r['country'] or ''})".strip(", ()")}
                for r in rows]
    elif target_type == "ecom":
        rows = _rows_to_dicts(conn.execute(
            "SELECT ecom_id, jira_id, test_case_id, testcase_name, country FROM ecom"
            " WHERE jira_id LIKE ? OR test_case_id LIKE ? OR testcase_name LIKE ?"
            " ORDER BY jira_id LIMIT 20",
            (like, like, like),
        ))
        return [{"value": str(r["ecom_id"]),
                 "label": f"{r['jira_id']} — {r['test_case_id'] or ''} ({r['country'] or ''})".strip(" —()")}
                for r in rows]
    elif target_type == "ecom_gatekeeper":
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, jira_id, solman_id, testcase_name FROM ecom_gatekeeper"
            " WHERE jira_id LIKE ? OR solman_id LIKE ? OR testcase_name LIKE ?"
            " ORDER BY id LIMIT 20",
            (like, like, like),
        ))
        return [{"value": str(r["id"]),
                 "label": " — ".join(x for x in (r["jira_id"], r["solman_id"],
                                                 r["testcase_name"]) if x)
                          or f"Gatekeeper row #{r['id']}"}
                for r in rows]
    elif target_type == "jira":
        rows = _rows_to_dicts(conn.execute(
            "SELECT jira_key, solman_id, summary FROM jira_issues"
            " WHERE jira_key LIKE ? OR solman_id LIKE ? OR summary LIKE ?"
            " ORDER BY jira_key LIMIT 20",
            (like, like, like),
        ))
        return [{"value": r["jira_key"],
                 "label": f"{r['jira_key']} — {r['summary'] or r['solman_id'] or ''}".rstrip(" —")}
                for r in rows]
    elif target_type == "topic":
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, title, category FROM topics"
            " WHERE (title LIKE ? OR category LIKE ?) AND status = 'active'"
            " ORDER BY title LIMIT 20",
            (like, like),
        ))
        return [{"value": str(r["id"]),
                 "label": f"{r['title']} ({r['category'] or 'no category'})"}
                for r in rows]
    elif target_type == "contact":
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, name, email FROM contacts"
            " WHERE name LIKE ? OR email LIKE ? ORDER BY name LIMIT 20",
            (like, like),
        ))
        return [{"value": str(r["id"]),
                 "label": f"{r['name']}" + (f" ({r['email'].split(',')[0].strip()})" if r.get("email") else "")}
                for r in rows]
    elif target_type == "link":
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, description, tool FROM links"
            " WHERE description LIKE ? OR url LIKE ? OR tool LIKE ? ORDER BY description LIMIT 20",
            (like, like, like),
        ))
        return [{"value": str(r["id"]),
                 "label": f"{r['description']}" + (f" [{r['tool']}]" if r.get("tool") else "")}
                for r in rows]
    elif target_type == "test_learning":
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, topic, channel FROM test_learnings"
            " WHERE topic LIKE ? OR channel LIKE ? ORDER BY topic LIMIT 20",
            (like, like),
        ))
        return [{"value": str(r["id"]),
                 "label": f"{r['topic'] or '—'} ({r['channel'] or ''})".rstrip(" ()")}
                for r in rows]
    elif target_type == "followup":
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, with_whom, topic FROM followups"
            " WHERE with_whom LIKE ? OR topic LIKE ? ORDER BY with_whom LIMIT 20",
            (like, like),
        ))
        return [{"value": str(r["id"]),
                 "label": f"{r['with_whom'] or '—'} — {r['topic'] or ''}".rstrip(" —")}
                for r in rows]
    return []




def get_attachment(conn: sqlite3.Connection, attachment_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
    ))
    return rows[0] if rows else None


def add_attachment(
    conn: sqlite3.Connection,
    note_id: int,
    filename: str,
    original_name: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO attachments (note_id, filename, original_name, created_at)"
            " VALUES (?, ?, ?, ?)",
            (note_id, filename, original_name, now),
        )
    return get_attachment(conn, cur.lastrowid)


def get_attachments_for_notes(
    conn: sqlite3.Connection, note_ids: list[int]
) -> dict[int, list[dict]]:
    """Return {note_id: [attachments]} for a batch of note IDs."""
    if not note_ids:
        return {}
    ph = ",".join("?" * len(note_ids))
    rows = _rows_to_dicts(conn.execute(
        f"SELECT * FROM attachments WHERE note_id IN ({ph}) ORDER BY created_at",
        note_ids,
    ))
    result: dict[int, list[dict]] = {nid: [] for nid in note_ids}
    for row in rows:
        result[row["note_id"]].append(row)
    return result


def delete_attachment(conn: sqlite3.Connection, attachment_id: int) -> str | None:
    """Delete the DB record and return the filename so the caller can remove the file."""
    att = get_attachment(conn, attachment_id)
    if not att:
        return None
    with conn:
        conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    return att["filename"]


# ---------------------------------------------------------------------------
# Generic order_details — works for any entity_type / entity_id pair
# ---------------------------------------------------------------------------

