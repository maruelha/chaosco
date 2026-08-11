"""Deadlines & Burning — the things that must not slip [USER 2026-08-11].

A deliberately small nag list: a topic, optionally a date it must be done
by, and which kind of pressure it carries. Three categories, because they
nag differently:

    deadline      — must be done before a specific date
    burning       — urgent regardless of a date
    uncomfortable — a promise you'd be ashamed not to keep

Not a to-do module: this is the short list that gets pushed in your face on
every first app open of the day (the dashboard popup). Anything that doesn't
deserve that treatment belongs in To-Do or Topics.

SQL kept Postgres-portable (CLAUDE.md rule 7); dates are ISO 'YYYY-MM-DD'
strings, and "overdue" is decided in Python so no date functions are needed.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

# key, label, blurb — the order is the order everything renders in
URGENT_CATEGORIES = [
    ("deadline",      "Deadline",      "must be done before a date"),
    ("burning",       "Burning",       "urgent, date or not"),
    ("uncomfortable", "Uncomfortable", "promises I'd be ashamed not to keep"),
]
CATEGORY_KEYS = [k for k, _, _ in URGENT_CATEGORIES]
CATEGORY_LABELS = {k: label for k, label, _ in URGENT_CATEGORIES}

# Second axis [USER 2026-08-11]: which side of the work an item belongs to.
# Empty is allowed on purpose — not everything is one or the other, and being
# forced to choose would stop things being written down.
URGENT_AREAS = ["Sales ECOM", "MB"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS urgent_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    category   TEXT NOT NULL,              -- deadline | burning | uncomfortable
    title      TEXT NOT NULL,
    due_date   TEXT,                       -- ISO 'YYYY-MM-DD', optional
    note       TEXT,
    area       TEXT,                       -- Sales ECOM | MB | NULL
    done       INTEGER NOT NULL DEFAULT 0,
    done_at    TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # additive migration for DBs created before 2026-08-11
        try:
            conn.execute("ALTER TABLE urgent_items ADD COLUMN area TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_category(category: str | None) -> str:
    key = (category or "").strip().lower()
    return key if key in CATEGORY_KEYS else CATEGORY_KEYS[0]


def _clean_area(area: str | None) -> str | None:
    """Canonical spelling whatever casing arrives; anything unknown (including
    blank) means 'not assigned', which is a valid state."""
    for a in URGENT_AREAS:
        if (area or "").strip().lower() == a.lower():
            return a
    return None


def _clean_date(value: str | None) -> str | None:
    """Keep only a real ISO date; anything else is dropped rather than stored
    as junk that would then sort and compare wrongly."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def decorate(items: list[dict], today: str | None = None) -> list[dict]:
    """Add the fields the UI needs: days_left (None when no date), overdue,
    due_today. Computed in Python so the DB stays date-function free."""
    today_d = date.fromisoformat(today) if today else date.today()
    for it in items:
        due = it.get("due_date")
        it["days_left"] = None
        it["overdue"] = False
        it["due_today"] = False
        if due:
            try:
                delta = (date.fromisoformat(due) - today_d).days
            except ValueError:
                continue
            it["days_left"] = delta
            it["overdue"] = delta < 0 and not it.get("done")
            it["due_today"] = delta == 0 and not it.get("done")
    return items


def list_urgent(conn: sqlite3.Connection, include_done: bool = False,
                today: str | None = None, area: str | None = None) -> list[dict]:
    """Open items first, dated ones before undated, earliest date first;
    then the category order, then newest. `area` filters to one side of the
    work ("Sales ECOM" / "MB"); pass "none" for the unassigned ones."""
    sql = "SELECT * FROM urgent_items WHERE 1=1"
    params: list = []
    if not include_done:
        sql += " AND done = 0"
    if area:
        if area.strip().lower() == "none":
            sql += " AND (area IS NULL OR area = '')"
        else:
            sql += " AND area = ?"
            params.append(_clean_area(area))
    sql += " ORDER BY done, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, id DESC"
    items = _rows_to_dicts(conn.execute(sql, params))
    order = {k: i for i, k in enumerate(CATEGORY_KEYS)}
    items.sort(key=lambda r: (
        r["done"],
        0 if r.get("due_date") else 1,
        r.get("due_date") or "",
        order.get(r.get("category"), 99),
    ))
    return decorate(items, today)


def list_by_category(conn: sqlite3.Connection, include_done: bool = False,
                     today: str | None = None,
                     area: str | None = None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {k: [] for k in CATEGORY_KEYS}
    for item in list_urgent(conn, include_done=include_done, today=today,
                            area=area):
        grouped.setdefault(item["category"], []).append(item)
    return grouped


def get_urgent(conn: sqlite3.Connection, item_id: int) -> dict | None:
    rows = decorate(_rows_to_dicts(conn.execute(
        "SELECT * FROM urgent_items WHERE id = ?", (item_id,))))
    return rows[0] if rows else None


def create_urgent(conn: sqlite3.Connection, category: str, title: str,
                  due_date: str | None = None, note: str | None = None,
                  area: str | None = None) -> int:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO urgent_items (category, title, due_date, note, area,"
            " done, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (_clean_category(category), title.strip(), _clean_date(due_date),
             (note or "").strip() or None, _clean_area(area), now, now))
    return cur.lastrowid


def update_urgent(conn: sqlite3.Connection, item_id: int, category: str,
                  title: str, due_date: str | None, note: str | None,
                  area: str | None = None) -> None:
    with conn:
        conn.execute(
            "UPDATE urgent_items SET category=?, title=?, due_date=?, note=?,"
            " area=?, updated_at=? WHERE id=?",
            (_clean_category(category), title.strip(), _clean_date(due_date),
             (note or "").strip() or None, _clean_area(area), _now(), item_id))


def set_done(conn: sqlite3.Connection, item_id: int, done: bool) -> None:
    now = _now()
    with conn:
        conn.execute(
            "UPDATE urgent_items SET done=?, done_at=?, updated_at=? WHERE id=?",
            (1 if done else 0, now if done else None, now, item_id))


def delete_urgent(conn: sqlite3.Connection, item_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM urgent_items WHERE id = ?", (item_id,))


def urgent_counts(conn: sqlite3.Connection, today: str | None = None) -> dict:
    """Counts for the dashboard card, the popup decision and the area filter:
    {'open': n, 'overdue': n, 'due_today': n, '<category>': n,
     'areas': {'Sales ECOM': n, 'MB': n, 'none': n}}."""
    items = list_urgent(conn, include_done=False, today=today)
    out = {"open": len(items),
           "overdue": sum(1 for i in items if i["overdue"]),
           "due_today": sum(1 for i in items if i["due_today"])}
    for key in CATEGORY_KEYS:
        out[key] = sum(1 for i in items if i["category"] == key)
    out["areas"] = {a: sum(1 for i in items if i.get("area") == a)
                    for a in URGENT_AREAS}
    out["areas"]["none"] = sum(1 for i in items if not i.get("area"))
    return out
