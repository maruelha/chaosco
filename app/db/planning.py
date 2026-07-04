"""Planning — meeting prep, enhancements, todos, followups, CS follow-ups

Part of the app.db package (refactoring step 4).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from app.db.core import _rows_to_dicts

MEETING_OPTIONS = [
    "Balazs",
    "GPO",
    "Sync&Solve",
    "DTC O2C Daily",
    "Sales ECOM daily",
    "Other",
]

MEETING_OVERALL_TOPICS = [
    "CS Retail",
    "CS ECOM",
    "CS General",
    "ROE Retail",
    "ROE ECOM",
    "ROE General",
    "Orga",
    "AI",
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
    return _rows_to_dicts(conn.execute(f"""
        SELECT m.*,
               COUNT(n.id) AS note_count,
               d.solman_name        AS src_defect_name,
               r.test_case_id       AS src_tc_id,
               r.country            AS src_country,
               r.testcase_scenario  AS src_scenario,
               r.retail_id          AS src_retail_id
        FROM   meeting_prep m
        LEFT JOIN notes   n ON n.entity_type = 'meeting_prep' AND n.entity_id = CAST(m.id AS TEXT)
        LEFT JOIN defects d ON m.source_entity_type = 'defect'  AND d.defect_id = m.source_entity_id
        LEFT JOIN retail  r ON m.source_entity_type = 'retail'  AND CAST(r.retail_id AS TEXT) = m.source_entity_id
        {clause}
        GROUP BY m.id
        ORDER BY m.id DESC
    """, params))


def list_daily_defects(conn: sqlite3.Connection) -> list[dict]:
    """Defects flagged 'to discuss on daily', with next_step from annotations."""
    return _rows_to_dicts(conn.execute("""
        SELECT d.defect_id, d.solman_name, d.channel,
               a.next_step
        FROM defects d
        LEFT JOIN defect_annotations a ON a.defect_id = d.defect_id
        WHERE COALESCE(a.daily, 0) = 1
        ORDER BY d.channel, d.defect_id
    """))


def add_meeting_prep(
    conn: sqlite3.Connection,
    meeting: str,
    topic: str,
    source_entity_type: str | None = None,
    source_entity_id: str | None = None,
    overall_topic: str | None = None,
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO meeting_prep"
        " (meeting, topic, status, source_entity_type, source_entity_id, overall_topic, created_at, updated_at)"
        " VALUES (?, ?, 'planned', ?, ?, ?, ?, ?)",
        (meeting, topic, source_entity_type, source_entity_id, overall_topic or None, now, now),
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


def set_meeting_prep_topic(conn: sqlite3.Connection, item_id: int, topic: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE meeting_prep SET topic = ?, updated_at = ? WHERE id = ?",
        (topic, now, item_id),
    )
    conn.commit()


def set_meeting_prep_overall_topic(conn: sqlite3.Connection, item_id: int, overall_topic: str | None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE meeting_prep SET overall_topic = ?, updated_at = ? WHERE id = ?",
        (overall_topic or None, now, item_id),
    )
    conn.commit()


def delete_meeting_prep(conn: sqlite3.Connection, item_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM meeting_prep WHERE id = ?", (item_id,))


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


def update_enhancement(
    conn: sqlite3.Connection,
    item_id: int,
    area: str | None,
    enhancement: str,
    priority: str,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE enhancements SET area = ?, enhancement = ?, priority = ?, updated_at = ? WHERE id = ?",
            (area or None, enhancement, priority, now, item_id),
        )


def delete_enhancement(conn: sqlite3.Connection, item_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM enhancements WHERE id = ?", (item_id,))


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


def update_todo(conn: sqlite3.Connection, todo_id: int, area: str, kind: str,
                topic: str, priority: str, due_date: str, for_whom: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE todos SET area=?, kind=?, topic=?, priority=?, due_date=?, for_whom=?, updated_at=? WHERE id=?",
        (area or None, kind or None, topic, priority, due_date or None, for_whom or None, now, todo_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

FOLLOWUP_STATUSES = ["open", "in_progress", "done"]


def get_followups(conn: sqlite3.Connection,
                  with_whom: list[str] | str | None = None,
                  when_next: str | None = None,
                  status: str | None = None,
                  group_name: list[str] | None = None,
                  include_done: bool = False) -> list[dict]:
    where, params = [], []
    if not include_done:
        where.append("f.status != 'done'")
    if with_whom:
        if isinstance(with_whom, str):
            with_whom = [with_whom]
        or_clauses = " OR ".join("f.with_whom LIKE ?" for _ in with_whom)
        where.append(f"({or_clauses})")
        params.extend(f"%{w}%" for w in with_whom)
    if when_next:
        where.append("f.when_next = ?"); params.append(when_next)
    if status:
        where.append("f.status = ?"); params.append(status)
    if group_name:
        placeholders = ",".join("?" for _ in group_name)
        where.append(f"f.group_name IN ({placeholders})")
        params.extend(group_name)
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
    rows = conn.execute(
        "SELECT DISTINCT with_whom FROM followups WHERE with_whom IS NOT NULL"
    ).fetchall()
    seen, names = set(), []
    for (val,) in rows:
        for name in [n.strip() for n in val.split(",")]:
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    names.sort()
    groups = [r[0] for r in conn.execute(
        "SELECT DISTINCT group_name FROM followups WHERE group_name IS NOT NULL ORDER BY group_name"
    ).fetchall()]
    return {"with_whom": names, "groups": groups}


def add_followup(conn: sqlite3.Connection, with_whom: str, topic: str,
                 when_next: str, group_name: str | None = None) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO followups (with_whom, topic, when_next, group_name, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, 'open', ?, ?)",
        (with_whom, topic, when_next or None, group_name or None, now, now),
    )
    conn.commit()
    return cur.lastrowid


def update_followup(conn: sqlite3.Connection, followup_id: int, with_whom: str,
                    topic: str, when_next: str | None, group_name: str | None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE followups SET with_whom=?, topic=?, when_next=?, group_name=?, updated_at=? WHERE id=?",
        (with_whom, topic, when_next or None, group_name or None, now, followup_id),
    )
    conn.commit()


def delete_followup(conn: sqlite3.Connection, followup_id: int) -> None:
    conn.execute("DELETE FROM notes WHERE entity_type='followup' AND entity_id=?", (str(followup_id),))
    conn.execute("DELETE FROM followups WHERE id=?", (followup_id,))
    conn.commit()


def get_followup_by_id(conn: sqlite3.Connection, followup_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM followups WHERE id = ?", (followup_id,)
    ))
    return rows[0] if rows else None


def set_followup_status(conn: sqlite3.Connection, followup_id: int, status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("UPDATE followups SET status=?, updated_at=? WHERE id=?", (status, now, followup_id))
    conn.commit()




CS_FOLLOWUP_STATUSES = ["open", "in_progress", "done"]


def list_cs_followups(
    conn: sqlite3.Connection,
    areas: list[str] | None = None,
    with_whom: list[str] | None = None,
    statuses: list[str] | None = None,
    include_done: bool = False,
) -> list[dict]:
    where: list[str] = []
    params: list = []
    if not include_done and not statuses:
        where.append("f.status != 'done'")
    if areas:
        placeholders = ",".join("?" * len(areas))
        where.append(f"f.area IN ({placeholders})")
        params.extend(areas)
    if with_whom:
        placeholders = ",".join("?" * len(with_whom))
        where.append(f"f.with_whom IN ({placeholders})")
        params.extend(with_whom)
    if statuses:
        placeholders = ",".join("?" * len(statuses))
        where.append(f"f.status IN ({placeholders})")
        params.extend(statuses)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    cur = conn.execute(f"""
        SELECT f.*,
               COUNT(n.id) AS note_count
        FROM   cs_followups f
        LEFT JOIN notes n ON n.entity_type = 'cs_followup' AND n.entity_id = CAST(f.id AS TEXT)
        {clause}
        GROUP BY f.id
        ORDER BY
          CASE f.status WHEN 'in_progress' THEN 0 WHEN 'open' THEN 1 ELSE 2 END,
          f.topic COLLATE NOCASE
    """, params)
    return _rows_to_dicts(cur)


def get_cs_followup(conn: sqlite3.Connection, followup_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM cs_followups WHERE id = ?", (followup_id,))
    rows = _rows_to_dicts(cur)
    return rows[0] if rows else None


def get_cs_followup_options(conn: sqlite3.Connection) -> dict:
    areas = [r[0] for r in conn.execute(
        "SELECT DISTINCT area FROM cs_followups WHERE area IS NOT NULL ORDER BY area"
    ).fetchall()]
    with_whom = [r[0] for r in conn.execute(
        "SELECT DISTINCT with_whom FROM cs_followups WHERE with_whom IS NOT NULL ORDER BY with_whom"
    ).fetchall()]
    return {"areas": areas, "with_whom": with_whom}


def create_cs_followup(
    conn: sqlite3.Connection,
    area: str | None,
    jira_id: str | None,
    topic: str,
    description: str | None,
    next_step: str | None,
    with_whom: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO cs_followups (area, jira_id, topic, description, next_step, with_whom,"
            " status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)",
            (area or None, jira_id or None, topic, description or None,
             next_step or None, with_whom or None, now, now),
        )
    return get_cs_followup(conn, cur.lastrowid)


def update_cs_followup(
    conn: sqlite3.Connection,
    followup_id: int,
    area: str | None,
    jira_id: str | None,
    topic: str,
    description: str | None,
    next_step: str | None,
    with_whom: str | None,
    status: str | None = None,
) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE cs_followups SET area=?, jira_id=?, topic=?, description=?, next_step=?,"
            " with_whom=?, status=COALESCE(?, status), updated_at=? WHERE id=?",
            (area or None, jira_id or None, topic, description or None,
             next_step or None, with_whom or None, status, now, followup_id),
        )
    return get_cs_followup(conn, followup_id)


def set_cs_followup_status(conn: sqlite3.Connection, followup_id: int, status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE cs_followups SET status=?, updated_at=? WHERE id=?",
            (status, now, followup_id),
        )


def delete_cs_followup(conn: sqlite3.Connection, followup_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM cs_followups WHERE id = ?", (followup_id,))


# ---------------------------------------------------------------------------
# Attachments (screenshots linked to notes)
# ---------------------------------------------------------------------------

