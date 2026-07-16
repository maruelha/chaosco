"""Teams chats & channels registry + per-entity references (2026-07-16).

[USER decisions]: ONE dedicated table (a chat can be addressed by a copied
deep link OR by member emails — links rows can't hold that), ONE clean
management UI (/teams-chats), ONE `pinned` flag driving the floating 💬
widget. Existing "Teams Channel" links rows are MIGRATED here (idempotent,
at startup) so channels and chats live in one place; the ping-page channel
picker keeps its routes but reads this table now.

Tickets REFERENCE registry rows (teams_chat_refs, same connected-not-copied
philosophy as the shared jira orders): rename/fix a chat once, every ticket
shows the new one. Address = generic (entity_type, entity_id); currently
retail, spillover, and jira (= gatekeeper ticket + ECOM board).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app import teams_link
from app.db.core import _rows_to_dicts, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams_chats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'chat',   -- 'chat' | 'channel'
    link        TEXT,                           -- copied Teams deep link
    emails      TEXT,                           -- OR: member emails (comma-sep)
    description TEXT,
    pinned      INTEGER NOT NULL DEFAULT 0,     -- shows in the floating widget
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teams_chat_refs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    chat_id     INTEGER NOT NULL,               -- FK teams_chats
    created_at  TEXT NOT NULL,
    UNIQUE (entity_type, entity_id, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_tc_refs_entity
    ON teams_chat_refs(entity_type, entity_id);
"""

_MIGRATED_TOOL = "Teams Channel"   # links.tool value of the old storage


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        migrate_channel_links(conn)
    finally:
        conn.close()


def migrate_channel_links(conn: sqlite3.Connection) -> int:
    """Move links rows with tool='Teams Channel' into teams_chats
    (kind='channel') and delete them from links — idempotent (after the
    first run nothing matches). Returns # moved."""
    now = datetime.now().isoformat(timespec="seconds")
    try:
        rows = _rows_to_dicts(conn.execute(
            "SELECT id, description, url FROM links WHERE tool = ?",
            (_MIGRATED_TOOL,)))
    except sqlite3.OperationalError:
        return 0  # links table not created yet (partial init in tests)
    with conn:
        for r in rows:
            conn.execute(
                "INSERT INTO teams_chats (name, kind, link, created_at, updated_at)"
                " VALUES (?, 'channel', ?, ?, ?)",
                (r["description"], r["url"], now, now))
            conn.execute("DELETE FROM links WHERE id = ?", (r["id"],))
    return len(rows)


# ---------------------------------------------------------------------------
# registry CRUD
# ---------------------------------------------------------------------------

def resolve_chat_url(chat: dict) -> str:
    """Stored deep link wins; otherwise build one from the member emails."""
    if (chat.get("link") or "").strip():
        return chat["link"].strip()
    emails = (chat.get("emails") or "").strip()
    if emails:
        return teams_link.build_chat_link(emails, "", chat.get("name"))
    return ""


def list_teams_chats(conn: sqlite3.Connection, pinned_only: bool = False,
                     q: str = "") -> list[dict]:
    sql = "SELECT * FROM teams_chats"
    where, params = [], []
    if pinned_only:
        where.append("pinned = 1")
    if q:
        where.append("(name LIKE ? OR COALESCE(description,'') LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY pinned DESC, name COLLATE NOCASE"
    rows = _rows_to_dicts(conn.execute(sql, params))
    for r in rows:
        r["url"] = resolve_chat_url(r)
    return rows


def get_teams_chat(conn: sqlite3.Connection, chat_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM teams_chats WHERE id = ?", (chat_id,)))
    if not rows:
        return None
    rows[0]["url"] = resolve_chat_url(rows[0])
    return rows[0]


def create_teams_chat(conn: sqlite3.Connection, name: str, kind: str = "chat",
                      link: str | None = None, emails: str | None = None,
                      description: str | None = None, pinned: int = 0) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO teams_chats (name, kind, link, emails, description,"
            " pinned, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (name, kind if kind in ("chat", "channel") else "chat",
             link or None, emails or None, description or None,
             1 if pinned else 0, now, now))
    return cur.lastrowid


def update_teams_chat(conn: sqlite3.Connection, chat_id: int, name: str,
                      kind: str, link: str | None, emails: str | None,
                      description: str | None, pinned: int) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "UPDATE teams_chats SET name=?, kind=?, link=?, emails=?,"
            " description=?, pinned=?, updated_at=? WHERE id=?",
            (name, kind if kind in ("chat", "channel") else "chat",
             link or None, emails or None, description or None,
             1 if pinned else 0, now, chat_id))


def delete_teams_chat(conn: sqlite3.Connection, chat_id: int) -> None:
    """Deletes the registry row AND all its ticket references."""
    with conn:
        conn.execute("DELETE FROM teams_chat_refs WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM teams_chats WHERE id = ?", (chat_id,))


# ---------------------------------------------------------------------------
# per-entity references
# ---------------------------------------------------------------------------

def list_chat_refs(conn: sqlite3.Connection, entity_type: str,
                   entity_id: str) -> list[dict]:
    try:
        rows = _rows_to_dicts(conn.execute(
            "SELECT c.*, r.id AS ref_id FROM teams_chat_refs r"
            " JOIN teams_chats c ON c.id = r.chat_id"
            " WHERE r.entity_type = ? AND r.entity_id = ?"
            " ORDER BY c.name COLLATE NOCASE", (entity_type, str(entity_id))))
    except sqlite3.OperationalError:
        return []  # schema not initialised (partial-init test fixtures)
    for r in rows:
        r["url"] = resolve_chat_url(r)
    return rows


def attach_chat(conn: sqlite3.Connection, entity_type: str, entity_id: str,
                chat_id: int) -> bool:
    if conn.execute("SELECT 1 FROM teams_chats WHERE id=?", (chat_id,)
                    ).fetchone() is None:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO teams_chat_refs (entity_type, entity_id,"
            " chat_id, created_at) VALUES (?,?,?,?)",
            (entity_type, str(entity_id), chat_id, now))
    return True


def detach_chat(conn: sqlite3.Connection, entity_type: str, entity_id: str,
                chat_id: int) -> None:
    with conn:
        conn.execute(
            "DELETE FROM teams_chat_refs WHERE entity_type=? AND entity_id=?"
            " AND chat_id=?", (entity_type, str(entity_id), chat_id))


def chats_by_entity(conn: sqlite3.Connection, entity_type: str) -> dict:
    """entity_id -> [{id, name, url}] for one type — feeds the 💬 buttons in
    list rows (rendered only where something is attached)."""
    try:
        rows = _rows_to_dicts(conn.execute(
            "SELECT r.entity_id, c.id, c.name, c.link, c.emails FROM teams_chat_refs r"
            " JOIN teams_chats c ON c.id = r.chat_id WHERE r.entity_type = ?"
            " ORDER BY c.name COLLATE NOCASE", (entity_type,)))
    except sqlite3.OperationalError:
        return {}  # schema not initialised (partial-init test fixtures)
    out: dict = {}
    for r in rows:
        out.setdefault(r["entity_id"], []).append(
            {"id": r["id"], "name": r["name"], "url": resolve_chat_url(r)})
    return out
