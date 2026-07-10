"""Global search — source registry (2026-07-10).

v1 searches ORDER NUMBERS. Each source below is one block: where to look,
how to label a hit, which entity a hit belongs to. Adding a new searchable
source later (e.g. topics via SQLite FTS5 — deliberately NOT embeddings
until FTS proves insufficient [discussion 2026-07-10]) = one more block;
the widget UI never changes.

Returns plain dicts grouped by source; the web layer maps (type, id) → URL.
"""
from __future__ import annotations

import sqlite3

from app.db.core import _rows_to_dicts

_MIN_QUERY_LEN = 3


def search_order_number(conn: sqlite3.Connection, q: str) -> list[dict]:
    """Contains-search across every place an order number lives.

    Returns [{"group": <source label>, "hits": [{"type", "id", "label",
    "match"}]}] — only non-empty groups, max 20 hits per source."""
    q = (q or "").strip()
    if len(q) < _MIN_QUERY_LEN:
        return []
    like = f"%{q}%"
    groups: list[dict] = []

    def _add(group: str, hits: list[dict]) -> None:
        if hits:
            groups.append({"group": group, "hits": hits})

    # -- 1. Order-details lines (manually maintained, pinned to an entity) --
    od_rows = _rows_to_dicts(conn.execute(
        "SELECT entity_type, entity_id, order_type, order_number, comment"
        " FROM order_details WHERE order_number LIKE ? LIMIT 20", (like,)))
    od_hits = []
    for r in od_rows:
        etype, eid = r["entity_type"], r["entity_id"]
        label = None
        if etype == "spillover":
            row = conn.execute("SELECT name FROM spillover WHERE spillover_id=?",
                               (eid,)).fetchone()
            label = row[0] if row else None
        elif etype == "ecom_gatekeeper":
            row = conn.execute("SELECT testcase_name FROM ecom_gatekeeper WHERE id=?",
                               (eid,)).fetchone()
            label = (row[0] if row else None) or f"Gatekeeper row #{eid}"
        elif etype == "ecom":
            row = conn.execute("SELECT test_case_id, country FROM ecom WHERE ecom_id=?",
                               (eid,)).fetchone()
            label = f"{row[0]} / {row[1]}" if row else None
        if label is None:
            continue  # orphaned line — nothing to navigate to
        match = r["order_number"]
        if r["order_type"]:
            match = f"[{r['order_type']}] {match}"
        if r["comment"]:
            match += f" — {r['comment']}"
        od_hits.append({"type": etype, "id": eid, "label": label, "match": match})
    _add("Order details", od_hits)

    # -- 2. Spillover imported cell --
    _add("Spillover", [
        {"type": "spillover", "id": r["spillover_id"], "label": r["name"] or "(no name)",
         "match": r["order_numbers"]}
        for r in _rows_to_dicts(conn.execute(
            "SELECT spillover_id, name, order_numbers FROM spillover"
            " WHERE order_numbers LIKE ? LIMIT 20", (like,)))])

    # -- 3. Retail imported cells --
    _add("Retail", [
        {"type": "retail", "id": r["retail_id"],
         "label": f"{r['test_case_id']} / {r['country']}",
         "match": " · ".join(x for x in (r["order_number"], r["old_order_numbers"]) if x)}
        for r in _rows_to_dicts(conn.execute(
            "SELECT retail_id, test_case_id, country, order_number, old_order_numbers"
            " FROM retail WHERE order_number LIKE ? OR old_order_numbers LIKE ?"
            " LIMIT 20", (like, like)))])

    # -- 4. ECOM imported cells --
    _add("ECOM", [
        {"type": "ecom", "id": r["ecom_id"],
         "label": f"{r['jira_id']} — {r['test_case_id'] or ''}".rstrip(" —"),
         "match": " · ".join(x for x in (r["order_number"], r["old_order_numbers"]) if x)}
        for r in _rows_to_dicts(conn.execute(
            "SELECT ecom_id, jira_id, test_case_id, order_number, old_order_numbers"
            " FROM ecom WHERE order_number LIKE ? OR old_order_numbers LIKE ?"
            " LIMIT 20", (like, like)))])

    # -- 5. Defects imported cell --
    _add("Defects", [
        {"type": "defect", "id": r["defect_id"],
         "label": f"{r['defect_id']} — {r['solman_name'] or ''}".rstrip(" —"),
         "match": r["order_number"]}
        for r in _rows_to_dicts(conn.execute(
            "SELECT defect_id, solman_name, order_number FROM defects"
            " WHERE order_number LIKE ? LIMIT 20", (like,)))])

    return groups
