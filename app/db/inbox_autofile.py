"""Inbox auto-file — field-based matching (2026-07-16).

[USER decisions]: FIELDS ONLY (no text scanning yet) · preview-then-confirm
· targets = jira tickets (gatekeeper/ECOM world) AND defects · only
UNAMBIGUOUS matches move, everything else stays in the inbox with a reason
· route_to (contact/link/followup) pushes to that module's (module,
'incoming') bucket — never auto-connected to a row.

Precedence per item: route_to > jira_id > solman_id > order_number — the
FIRST PRESENT field decides; if it doesn't resolve, the item is skipped
(no fall-through to weaker fields — predictability over cleverness).
"""
from __future__ import annotations

import sqlite3

from app.db.notes import _ROUTE_TO_MODULES, file_inbox_item, list_inbox_items

_ROUTE_LABELS = {"contact": "Contacts — Incoming", "link": "Links — Incoming",
                 "followup": "Follow-ups — Incoming"}


def _jira_label(conn: sqlite3.Connection, jira_key: str) -> str:
    row = conn.execute("SELECT summary FROM jira_issues WHERE jira_key=?",
                       (jira_key,)).fetchone()
    return f"{jira_key} — {row[0]}" if row and row[0] else jira_key


def _defect_label(conn: sqlite3.Connection, defect_id: str) -> str:
    row = conn.execute("SELECT solman_name FROM defects WHERE defect_id=?",
                       (defect_id,)).fetchone()
    return f"{defect_id} — {row[0]}" if row and row[0] else defect_id


def _resolve_jira_id(conn, value: str) -> list[tuple[str, str]]:
    return [("jira", r[0]) for r in conn.execute(
        "SELECT jira_key FROM jira_issues WHERE TRIM(jira_key) = TRIM(?)"
        " COLLATE NOCASE", (value,))]


def _resolve_solman_id(conn, value: str) -> list[tuple[str, str]]:
    hits = [("jira", r[0]) for r in conn.execute(
        "SELECT jira_key FROM jira_issues WHERE TRIM(COALESCE(solman_id,''))"
        " = TRIM(?) COLLATE NOCASE", (value,))]
    hits += [("defect", r[0]) for r in conn.execute(
        "SELECT defect_id FROM defects WHERE TRIM(defect_id) = TRIM(?)"
        " COLLATE NOCASE", (value,))]
    return hits


def _resolve_order_number(conn, value: str) -> list[tuple[str, str]]:
    hits = {("jira", r[0]) for r in conn.execute(
        "SELECT entity_id FROM order_details WHERE entity_type='jira'"
        " AND TRIM(COALESCE(order_number,'')) = TRIM(?) COLLATE NOCASE", (value,))}
    hits |= {("jira", r[0]) for r in conn.execute(
        "SELECT jira_id FROM ecom WHERE TRIM(COALESCE(order_number,''))"
        " = TRIM(?) COLLATE NOCASE AND TRIM(COALESCE(jira_id,'')) <> ''", (value,))}
    hits |= {("defect", r[0]) for r in conn.execute(
        "SELECT defect_id FROM defects WHERE TRIM(COALESCE(order_number,''))"
        " = TRIM(?) COLLATE NOCASE", (value,))}
    return sorted(hits)


def _resolve_item(conn, item: dict) -> dict:
    """One inbox item -> {action:'move', target_type, target_id, label, via}
    or {action:'skip', reason}."""
    route = (item.get("route_to") or "").strip()
    if route:
        if route not in _ROUTE_TO_MODULES:
            return {"action": "skip", "reason": f"unknown route '{route}'"}
        return {"action": "move", "target_type": route, "target_id": "incoming",
                "label": _ROUTE_LABELS[route], "via": "route"}

    for field, resolver in (("jira_id", _resolve_jira_id),
                            ("solman_id", _resolve_solman_id),
                            ("order_number", _resolve_order_number)):
        value = (item.get(field) or "").strip()
        if not value:
            continue
        hits = resolver(conn, value)
        if len(hits) == 1:
            ttype, tid = hits[0]
            label = (_jira_label(conn, tid) if ttype == "jira"
                     else _defect_label(conn, tid))
            return {"action": "move", "target_type": ttype, "target_id": tid,
                    "label": label, "via": field}
        if not hits:
            return {"action": "skip",
                    "reason": f"no match for {field} '{value}'"}
        return {"action": "skip",
                "reason": f"ambiguous — {len(hits)} matches for {field} '{value}'"}
    return {"action": "skip", "reason": "no reference fields set"}


def preview_autofile(conn: sqlite3.Connection) -> dict:
    """Dry run over every inbox item that carries any field. Items without
    fields are left out entirely (they are normal manual-filing inbox notes)."""
    movable, skipped = [], []
    for item in list_inbox_items(conn):
        if not any((item.get(f) or "").strip()
                   for f in ("route_to", "jira_id", "solman_id", "order_number")):
            continue
        res = _resolve_item(conn, item)
        entry = {"note_id": item["id"],
                 "heading": item["heading"] or "(no heading)", **res}
        (movable if res["action"] == "move" else skipped).append(entry)
    return {"movable": movable, "skipped": skipped}


def apply_autofile(conn: sqlite3.Connection, note_ids: list[int]) -> dict:
    """Move the given inbox items — every match is RECOMPUTED server-side
    (a stale preview can't misfile). Returns per-note results + counts."""
    filed, skipped = 0, 0
    results = []
    wanted = set(note_ids)
    for item in list_inbox_items(conn):
        if item["id"] not in wanted:
            continue
        res = _resolve_item(conn, item)
        if res["action"] == "move":
            if res["via"] == "route":
                with conn:
                    conn.execute(
                        "UPDATE notes SET entity_type=?, entity_id='incoming'"
                        " WHERE id=? AND entity_type='input'",
                        (res["target_type"], item["id"]))
                ok = True
            else:
                ok = file_inbox_item(conn, item["id"],
                                     res["target_type"], res["target_id"])
            if ok:
                filed += 1
                results.append({"note_id": item["id"], "filed_to": res["label"]})
                continue
            res = {"action": "skip", "reason": "target vanished"}
        skipped += 1
        results.append({"note_id": item["id"], "skipped": res["reason"]})
    return {"filed": filed, "skipped": skipped, "results": results}
