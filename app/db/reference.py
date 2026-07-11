"""Reference & shared logs — shelf, known prod defects, links, contacts, encouragements, test learnings/limitations, order details, ecom gatekeeper, report comments

Part of the app.db package (refactoring step 4).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from app.db.core import _rows_to_dicts

def create_shelf_item(
    conn: sqlite3.Connection,
    heading: str | None,
    area: str | None,
    category: str | None,
) -> int:
    """Insert a new shelf row and return its id."""
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO shelf (heading, area, category, created_at) VALUES (?, ?, ?, ?)",
            (heading or None, area or None, category or None, now),
        )
    return cur.lastrowid


def count_shelf_items(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM shelf").fetchone()
    return row[0] if row else 0


def list_shelf_items(
    conn: sqlite3.Connection,
    areas: list[str] | None = None,
    categories: list[str] | None = None,
) -> list[dict]:
    """Return all shelf rows, optionally filtered by area and/or category.

    Each row is augmented with a note_count (number of linked notes).
    """
    sql = """
        SELECT s.*,
               COUNT(n.id) AS note_count
          FROM shelf s
          LEFT JOIN notes n ON n.entity_type = 'shelf' AND n.entity_id = CAST(s.id AS TEXT)
    """
    params: list = []
    conditions: list[str] = []

    if areas:
        placeholders = ",".join("?" * len(areas))
        conditions.append(f"s.area IN ({placeholders})")
        params.extend(areas)
    if categories:
        placeholders = ",".join("?" * len(categories))
        conditions.append(f"s.category IN ({placeholders})")
        params.extend(categories)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY s.id ORDER BY s.created_at DESC"

    return _rows_to_dicts(conn.execute(sql, params))


def get_shelf_item(conn: sqlite3.Connection, shelf_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM shelf WHERE id = ?", (shelf_id,)
    ))
    return rows[0] if rows else None


def update_shelf_item(
    conn: sqlite3.Connection,
    shelf_id: int,
    heading: str | None,
    area: str | None,
    category: str | None,
) -> None:
    with conn:
        conn.execute(
            "UPDATE shelf SET heading = ?, area = ?, category = ? WHERE id = ?",
            (heading or None, area or None, category or None, shelf_id),
        )


def delete_shelf_item(conn: sqlite3.Connection, shelf_id: int) -> list[str]:
    """Delete a shelf item, its linked notes, and their attachments.

    Returns the list of attachment filenames so the caller can remove them from disk.
    """
    entity_id = str(shelf_id)
    note_ids = [
        r["id"] for r in _rows_to_dicts(conn.execute(
            "SELECT id FROM notes WHERE entity_type = 'shelf' AND entity_id = ?",
            (entity_id,),
        ))
    ]
    filenames: list[str] = []
    if note_ids:
        placeholders = ",".join("?" * len(note_ids))
        filenames = [
            r["filename"] for r in _rows_to_dicts(conn.execute(
                f"SELECT filename FROM attachments WHERE note_id IN ({placeholders})",
                note_ids,
            ))
        ]
        with conn:
            conn.execute(
                f"DELETE FROM attachments WHERE note_id IN ({placeholders})", note_ids
            )
            conn.execute(
                f"DELETE FROM notes WHERE id IN ({placeholders})", note_ids
            )
    with conn:
        conn.execute("DELETE FROM shelf WHERE id = ?", (shelf_id,))
    return filenames


def get_shelf_filter_options(conn: sqlite3.Connection) -> dict:
    """Return distinct area and category values for filter dropdowns."""
    def _vals(col: str) -> list[str]:
        return [
            r[col] for r in _rows_to_dicts(conn.execute(
                f"SELECT DISTINCT {col} FROM shelf WHERE {col} IS NOT NULL ORDER BY {col}"
            ))
        ]
    return {"areas": _vals("area"), "categories": _vals("category")}


def combine_shelf_items(
    conn: sqlite3.Connection,
    primary_id: int,
    secondary_ids: list[int],
) -> None:
    """Re-parent all notes from secondary shelf items to the primary, then delete secondaries.

    Attachments follow automatically because they reference note_id, not shelf_id.
    """
    if not secondary_ids:
        return
    primary_entity_id = str(primary_id)
    for sid in secondary_ids:
        with conn:
            conn.execute(
                "UPDATE notes SET entity_id = ? WHERE entity_type = 'shelf' AND entity_id = ?",
                (primary_entity_id, str(sid)),
            )
            conn.execute("DELETE FROM shelf WHERE id = ?", (sid,))




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




def _parse_tags(raw: str | None) -> set[str]:
    return {t.strip() for t in (raw or "").split(",") if t.strip()}


def get_link_options(conn: sqlite3.Connection) -> dict:
    rows = _rows_to_dicts(conn.execute("SELECT area, tool, tags FROM links"))
    areas = sorted({r["area"] for r in rows if r.get("area")})
    tools = sorted({r["tool"] for r in rows if r.get("tool")})
    all_tags: set[str] = set()
    for r in rows:
        all_tags |= _parse_tags(r.get("tags"))
    return {"areas": areas, "tools": tools, "tags": sorted(all_tags)}


def list_links(
    conn: sqlite3.Connection,
    areas: list[str] | None = None,
    tools: list[str] | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> list[dict]:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM links ORDER BY description COLLATE NOCASE"
    ))
    if areas:
        rows = [r for r in rows if r.get("area") in areas]
    if tools:
        rows = [r for r in rows if r.get("tool") in tools]
    if tags:
        tag_set = set(tags)
        rows = [r for r in rows if _parse_tags(r.get("tags")) & tag_set]
    if search:
        s = search.lower()
        rows = [r for r in rows if s in (r.get("description") or "").lower()]
    return rows


def get_link(conn: sqlite3.Connection, link_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,))
    rows = _rows_to_dicts(cur)
    return rows[0] if rows else None


def create_link(
    conn: sqlite3.Connection,
    description: str,
    url: str,
    area: str | None,
    tool: str | None,
    tags: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO links (description, url, area, tool, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (description, url, area or None, tool or None, tags or None, now, now),
        )
    return get_link(conn, cur.lastrowid)


def update_link(
    conn: sqlite3.Connection,
    link_id: int,
    description: str,
    url: str,
    area: str | None,
    tool: str | None,
    tags: str | None,
) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE links SET description=?, url=?, area=?, tool=?, tags=?, updated_at=?"
            " WHERE id=?",
            (description, url, area or None, tool or None, tags or None, now, link_id),
        )
    return get_link(conn, link_id)


def delete_link(conn: sqlite3.Connection, link_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM links WHERE id = ?", (link_id,))


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def find_contact_email(conn: sqlite3.Connection, name: str) -> str | None:
    """Best-effort contact email for a free-text name (e.g. followups.with_whom).
    Case-insensitive substring match either way; first hit wins."""
    name = (name or "").strip().lower()
    if not name:
        return None
    for row in conn.execute(
            "SELECT name, email FROM contacts WHERE email IS NOT NULL AND email != ''"):
        cname = (row[0] or "").strip().lower()
        if cname and (name in cname or cname in name):
            # contacts.email is free text and may hold several — take the first
            return row[1].replace(";", ",").split(",")[0].strip()
    return None


def upsert_contact_email(conn: sqlite3.Connection, name: str, email: str) -> str:
    """Save an email under a contact name (Teams-ping 'save to contacts').
    Updates the email of an existing name-matched contact, else creates a
    minimal contact. Returns 'updated' or 'created'."""
    name, email = (name or "").strip(), (email or "").strip()
    lname = name.lower()
    for row in conn.execute("SELECT id, name FROM contacts"):
        cname = (row[1] or "").strip().lower()
        if cname and (lname in cname or cname in lname):
            with conn:
                conn.execute("UPDATE contacts SET email=? WHERE id=?", (email, row[0]))
            return "updated"
    with conn:
        conn.execute(
            "INSERT INTO contacts (name, email, created_at, updated_at)"
            " VALUES (?, ?, datetime('now'), datetime('now'))", (name, email))
    return "created"


def get_contact_options(conn: sqlite3.Connection) -> dict:
    rows = _rows_to_dicts(conn.execute("SELECT area, topic, tags FROM contacts"))
    areas = sorted({r["area"] for r in rows if r.get("area")})
    topics = sorted({r["topic"] for r in rows if r.get("topic")})
    all_tags: set[str] = set()
    for r in rows:
        all_tags |= _parse_tags(r.get("tags"))
    return {"areas": areas, "topics": topics, "tags": sorted(all_tags)}


def list_contacts(
    conn: sqlite3.Connection,
    areas: list[str] | None = None,
    topics: list[str] | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> list[dict]:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM contacts ORDER BY name COLLATE NOCASE"
    ))
    if areas:
        rows = [r for r in rows if r.get("area") in areas]
    if topics:
        rows = [r for r in rows if r.get("topic") in topics]
    if tags:
        tag_set = set(tags)
        rows = [r for r in rows if _parse_tags(r.get("tags")) & tag_set]
    if search:
        s = search.lower()
        rows = [r for r in rows if s in (r.get("name") or "").lower()
                or s in (r.get("email") or "").lower()]
    return rows


def get_contact(conn: sqlite3.Connection, contact_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    rows = _rows_to_dicts(cur)
    return rows[0] if rows else None


def create_contact(
    conn: sqlite3.Connection,
    name: str,
    email: str | None,
    area: str | None,
    topic: str | None,
    comments: str | None,
    tags: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO contacts (name, email, area, topic, comments, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, email or None, area or None, topic or None,
             comments or None, tags or None, now, now),
        )
    return get_contact(conn, cur.lastrowid)


def update_contact(
    conn: sqlite3.Connection,
    contact_id: int,
    name: str,
    email: str | None,
    area: str | None,
    topic: str | None,
    comments: str | None,
    tags: str | None,
) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE contacts SET name=?, email=?, area=?, topic=?, comments=?, tags=?, updated_at=?"
            " WHERE id=?",
            (name, email or None, area or None, topic or None,
             comments or None, tags or None, now, contact_id),
        )
    return get_contact(conn, contact_id)


def delete_contact(conn: sqlite3.Connection, contact_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))


# ---------------------------------------------------------------------------
# Encouragements
# ---------------------------------------------------------------------------

def get_or_create_encouragement_person(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM encouragement_people WHERE LOWER(name) = LOWER(?)", (name,)
    ).fetchone()
    if row:
        return row[0]
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO encouragement_people (name, created_at) VALUES (?, ?)", (name, now)
        )
    return cur.lastrowid


def list_encouragement_people(conn: sqlite3.Connection) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM encouragement_people ORDER BY name"
    ))


def add_encouragement(conn: sqlite3.Connection, person_id: int, text: str, enc_date: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO encouragements (person_id, text, date, delivered, created_at)"
            " VALUES (?, ?, ?, 0, ?)",
            (person_id, text, enc_date, now),
        )
    return cur.lastrowid


def list_encouragements(conn: sqlite3.Connection, person_id: int | None = None) -> list[dict]:
    sql = """
        SELECT e.*, p.name AS person_name
        FROM encouragements e
        JOIN encouragement_people p ON p.id = e.person_id
    """
    params: list = []
    if person_id:
        sql += " WHERE e.person_id = ?"
        params.append(person_id)
    sql += " ORDER BY e.date DESC, e.created_at DESC"
    return _rows_to_dicts(conn.execute(sql, params))


def set_encouragement_delivered(conn: sqlite3.Connection, enc_id: int, value: bool) -> None:
    with conn:
        conn.execute(
            "UPDATE encouragements SET delivered = ? WHERE id = ?", (1 if value else 0, enc_id)
        )


def delete_encouragement(conn: sqlite3.Connection, enc_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM encouragements WHERE id = ?", (enc_id,))


def count_encouragements_to_deliver(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM encouragements WHERE delivered = 0").fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Test Learnings
# ---------------------------------------------------------------------------

def list_test_learnings(
    conn: sqlite3.Connection,
    channels: list[str] | None = None,
    tags: list[str] | None = None,
) -> list[dict]:
    where: list[str] = []
    params: list = []
    if channels:
        placeholders = ",".join("?" * len(channels))
        where.append(f"t.channel IN ({placeholders})")
        params.extend(channels)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    cur = conn.execute(f"""
        SELECT t.*,
               COUNT(n.id) AS note_count
        FROM   test_learnings t
        LEFT JOIN notes n ON n.entity_type = 'test_learning' AND n.entity_id = CAST(t.id AS TEXT)
        {clause}
        GROUP BY t.id
        ORDER BY t.channel COLLATE NOCASE, t.topic COLLATE NOCASE, t.learning COLLATE NOCASE
    """, params)
    rows = _rows_to_dicts(cur)
    if tags:
        tag_set = set(tags)
        rows = [r for r in rows if _parse_tags(r.get("tags")) & tag_set]
    return rows


def get_test_learning(conn: sqlite3.Connection, learning_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute("SELECT * FROM test_learnings WHERE id = ?", (learning_id,)))
    return rows[0] if rows else None


def get_test_learning_options(conn: sqlite3.Connection) -> dict:
    channels = [r[0] for r in conn.execute(
        "SELECT DISTINCT channel FROM test_learnings WHERE channel IS NOT NULL ORDER BY channel"
    ).fetchall()]
    all_tags: set[str] = set()
    for (raw,) in conn.execute("SELECT tags FROM test_learnings WHERE tags IS NOT NULL").fetchall():
        all_tags |= _parse_tags(raw)
    return {"channels": channels, "tags": sorted(all_tags)}


def create_test_learning(
    conn: sqlite3.Connection,
    channel: str,
    topic: str | None,
    learning: str,
    scenario: str | None,
    tags: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO test_learnings (channel, topic, learning, scenario, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (channel, topic or None, learning, scenario or None, tags or None, now, now),
        )
    return get_test_learning(conn, cur.lastrowid)


def update_test_learning(
    conn: sqlite3.Connection,
    learning_id: int,
    channel: str,
    topic: str | None,
    learning: str,
    scenario: str | None,
    tags: str | None,
) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE test_learnings SET channel=?, topic=?, learning=?, scenario=?, tags=?, updated_at=?"
            " WHERE id=?",
            (channel, topic or None, learning, scenario or None, tags or None, now, learning_id),
        )
    return get_test_learning(conn, learning_id)


def delete_test_learning(conn: sqlite3.Connection, learning_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM test_learnings WHERE id = ?", (learning_id,))


# ---------------------------------------------------------------------------
# Test Limitations
# ---------------------------------------------------------------------------

def list_test_limitations(
    conn: sqlite3.Connection,
    channels: list[str] | None = None,
) -> list[dict]:
    where: list[str] = []
    params: list = []
    if channels:
        placeholders = ",".join("?" * len(channels))
        where.append(f"t.channel IN ({placeholders})")
        params.extend(channels)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    cur = conn.execute(f"""
        SELECT t.*,
               COUNT(n.id) AS note_count
        FROM   test_limitations t
        LEFT JOIN notes n ON n.entity_type = 'test_limitation' AND n.entity_id = CAST(t.id AS TEXT)
        {clause}
        GROUP BY t.id
        ORDER BY t.channel COLLATE NOCASE, t.limitation COLLATE NOCASE
    """, params)
    return _rows_to_dicts(cur)


def get_test_limitation(conn: sqlite3.Connection, limitation_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute("SELECT * FROM test_limitations WHERE id = ?", (limitation_id,)))
    return rows[0] if rows else None


def get_test_limitation_options(conn: sqlite3.Connection) -> dict:
    channels = [r[0] for r in conn.execute(
        "SELECT DISTINCT channel FROM test_limitations WHERE channel IS NOT NULL ORDER BY channel"
    ).fetchall()]
    return {"channels": channels}


def create_test_limitation(
    conn: sqlite3.Connection,
    channel: str,
    limitation: str,
    scenario: str | None,
    comment: str | None,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO test_limitations (channel, limitation, scenario, comment, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (channel, limitation, scenario or None, comment or None, now, now),
        )
    return get_test_limitation(conn, cur.lastrowid)


def update_test_limitation(
    conn: sqlite3.Connection,
    limitation_id: int,
    channel: str,
    limitation: str,
    scenario: str | None,
    comment: str | None,
) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE test_limitations SET channel=?, limitation=?, scenario=?, comment=?, updated_at=?"
            " WHERE id=?",
            (channel, limitation, scenario or None, comment or None, now, limitation_id),
        )
    return get_test_limitation(conn, limitation_id)


def delete_test_limitation(conn: sqlite3.Connection, limitation_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM test_limitations WHERE id = ?", (limitation_id,))




def list_order_details(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> list[dict]:
    cur = conn.execute(
        "SELECT id, order_type, order_number, comment, docs_in_s4 FROM order_details"
        " WHERE entity_type = ? AND entity_id = ? ORDER BY id",
        (entity_type, entity_id),
    )
    return _rows_to_dicts(cur)


def add_order_detail(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> int:
    cur = conn.execute(
        "INSERT INTO order_details (entity_type, entity_id, order_type, order_number, comment, created_at)"
        " VALUES (?, ?, '', '', '', datetime('now'))",
        (entity_type, entity_id),
    )
    conn.commit()
    return cur.lastrowid


def update_order_detail(
    conn: sqlite3.Connection, detail_id: int, order_type: str, order_number: str,
    comment: str, docs_in_s4: int = 0
) -> None:
    conn.execute(
        "UPDATE order_details SET order_type = ?, order_number = ?, comment = ?, docs_in_s4 = ? WHERE id = ?",
        (order_type or "", order_number or "", comment or "", int(bool(docs_in_s4)), detail_id),
    )
    conn.commit()


def get_docs_s4_entity_ids(conn: sqlite3.Connection, entity_type: str) -> set:
    """Entity ids (of one type) that have at least one order row with docs-in-S4
    — drives the green ✓ on the Order-details button at page load."""
    cur = conn.execute(
        "SELECT DISTINCT entity_id FROM order_details"
        " WHERE entity_type = ? AND docs_in_s4 = 1", (entity_type,)
    )
    return {int(row[0]) for row in cur.fetchall()}


def get_docs_s4_spillover_ids(conn: sqlite3.Connection) -> set:
    return get_docs_s4_entity_ids(conn, "spillover")


def delete_order_detail(conn: sqlite3.Connection, detail_id: int) -> None:
    conn.execute("DELETE FROM order_details WHERE id = ?", (detail_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Spillover report selection
# ---------------------------------------------------------------------------



def list_ecom_gatekeeper_rows(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        """SELECT g.*,
                  COUNT(n.id) AS note_count
           FROM ecom_gatekeeper g
           LEFT JOIN notes n
             ON n.entity_type = 'ecom_gatekeeper' AND n.entity_id = CAST(g.id AS TEXT)
           GROUP BY g.id
           ORDER BY g.id"""
    )
    return _rows_to_dicts(cur)


def get_ecom_gatekeeper_row(conn: sqlite3.Connection, row_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM ecom_gatekeeper WHERE id = ?", (row_id,))
    rows = _rows_to_dicts(cur)
    return rows[0] if rows else None


def add_ecom_gatekeeper_row(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO ecom_gatekeeper (jira_id, solman_id, testcase_name, status, next_step, created_at)"
        " VALUES ('', '', '', 'open', '', datetime('now'))"
    )
    conn.commit()
    return cur.lastrowid


def set_ecom_gatekeeper_next_step(conn: sqlite3.Connection, row_id: int,
                                  next_step: str | None) -> None:
    """Only-this-field update (used by the next-step archive component)."""
    conn.execute("UPDATE ecom_gatekeeper SET next_step=? WHERE id=?",
                 (next_step or "", row_id))
    conn.commit()


def update_ecom_gatekeeper_row(
    conn: sqlite3.Connection, row_id: int,
    jira_id: str, solman_id: str, testcase_name: str, status: str, next_step: str
) -> None:
    conn.execute(
        "UPDATE ecom_gatekeeper"
        " SET jira_id=?, solman_id=?, testcase_name=?, status=?, next_step=?"
        " WHERE id=?",
        (jira_id or "", solman_id or "", testcase_name or "",
         status or "open", next_step or "", row_id),
    )
    conn.commit()


def delete_ecom_gatekeeper_row(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute(
        "DELETE FROM notes WHERE entity_type='ecom_gatekeeper' AND entity_id=?", (str(row_id),)
    )
    conn.execute(
        "DELETE FROM order_details WHERE entity_type='ecom_gatekeeper' AND entity_id=?", (str(row_id),)
    )
    conn.execute("DELETE FROM ecom_gatekeeper WHERE id=?", (row_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Report comments — free-text bullets shown in the status reports
# ---------------------------------------------------------------------------

def list_report_comments(conn: sqlite3.Connection, report: str) -> list[dict]:
    """Return all bullet comments for 'spillover' or 'retail', oldest-first."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM report_comments WHERE report = ? ORDER BY id", (report,)
    ))


def add_report_comment(conn: sqlite3.Connection, report: str, comment: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO report_comments (report, comment) VALUES (?, ?)",
        (report, comment),
    )
    conn.commit()
    return cur.lastrowid


def update_report_comment(conn: sqlite3.Connection, comment_id: int, comment: str) -> None:
    conn.execute(
        "UPDATE report_comments SET comment = ? WHERE id = ?", (comment, comment_id)
    )
    conn.commit()


def delete_report_comment(conn: sqlite3.Connection, comment_id: int) -> None:
    conn.execute("DELETE FROM report_comments WHERE id = ?", (comment_id,))
    conn.commit()
