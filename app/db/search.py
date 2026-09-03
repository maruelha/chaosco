"""Global search — source registry (2026-07-10).

v1 searches ORDER NUMBERS. Each source below is one block: where to look,
how to label a hit, which entity a hit belongs to. Adding a new searchable
source later (e.g. topics via SQLite FTS5 — deliberately NOT embeddings
until FTS proves insufficient [discussion 2026-07-10]) = one more block;
the widget UI never changes.

Returns plain dicts grouped by source; the web layer maps (type, id) → URL.
"""
from __future__ import annotations

import re
import sqlite3

from app.db.core import _rows_to_dicts

_MIN_QUERY_LEN = 3


def _snippet(text: str | None, q: str, ctx: int = 35) -> str:
    """Plain-text snippet around the first hit of q (HTML stripped)."""
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    i = plain.lower().find(q.lower())
    if i < 0:
        return plain[:80]
    start, end = max(0, i - ctx), i + len(q) + ctx
    return (("…" if start > 0 else "") + plain[start:end]
            + ("…" if end < len(plain) else ""))


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
        elif etype == "jira":
            # shared gatekeeper/ECOM order rows (addressed by jira key, 2026-07-16)
            row = conn.execute("SELECT summary FROM jira_issues WHERE jira_key=?",
                               (eid,)).fetchone()
            label = f"{eid} — {row[0]}" if row and row[0] else str(eid)
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

    # -- 6. Jira tickets — acceptance criteria + comment bodies (2026-08-05).
    # This is where Gatekeeper/ECOM order numbers actually live (testers fill
    # the AC checklist / write them into comments); one hit per ticket.
    jira_hits: dict[str, dict] = {}
    for r in _rows_to_dicts(conn.execute(
            "SELECT jira_key, summary, acceptance_criteria FROM jira_issues"
            " WHERE acceptance_criteria LIKE ? LIMIT 20", (like,))):
        jira_hits[r["jira_key"]] = {
            "type": "jira", "id": r["jira_key"],
            "label": f"{r['jira_key']} — {r['summary'] or ''}".rstrip(" —"),
            "match": "AC: " + _snippet(r["acceptance_criteria"], q)}
    for r in _rows_to_dicts(conn.execute(
            "SELECT c.jira_key, i.summary, c.body FROM jira_comments c"
            " LEFT JOIN jira_issues i ON i.jira_key = c.jira_key"
            " WHERE c.body LIKE ? LIMIT 20", (like,))):
        if r["jira_key"] in jira_hits:
            continue
        jira_hits[r["jira_key"]] = {
            "type": "jira", "id": r["jira_key"],
            "label": f"{r['jira_key']} — {r['summary'] or ''}".rstrip(" —"),
            "match": "Comment: " + _snippet(r["body"], q)}
    _add("Jira tickets", list(jira_hits.values())[:20])

    # -- 7. Notes — heading + body, Inbox included (2026-08-05). The web
    # layer resolves entity_type/entity_id to a URL via the notes REGISTRY
    # (inbox = entity_type 'input'); unknown entity types are dropped there.
    _add("Notes", [
        {"type": "note", "id": r["id"],
         "entity_type": r["entity_type"], "entity_id": r["entity_id"],
         "label": (r["heading"] or "").strip() or "(no heading)",
         "match": _snippet(r["note"], q)}
        for r in _rows_to_dicts(conn.execute(
            "SELECT id, entity_type, entity_id, heading, note FROM notes"
            " WHERE heading LIKE ? OR note LIKE ? LIMIT 20", (like, like)))])

    # -- 8. Sustainphase Issues (rewritten 2026-09-03) — ASPEN incident
    # number + title (Go-Live defect tracker). Portable case-insensitive LIKE.
    try:
        si_rows = _rows_to_dicts(conn.execute(
            "SELECT incident_number, title FROM sustain_incidents"
            " WHERE LOWER(incident_number) LIKE LOWER(?)"
            "    OR LOWER(title) LIKE LOWER(?) LIMIT 20", (like, like)))
    except sqlite3.OperationalError:
        si_rows = []  # module not initialised in this DB
    si_hits = [{
        "type": "sustain_incident", "id": r["incident_number"],
        "label": f"{r['incident_number']} — {r['title'] or ''}".rstrip(" —"),
        "match": r["incident_number"]
                 if q.lower() in r["incident_number"].lower()
                 else _snippet(r["title"], q)}
        for r in si_rows]
    _add("Sustainphase Issues", si_hits)

    # -- 9. Smoke scenarios (2026-08-28 [USER]) — scenario names + step
    # ASPEN tickets; one hit per scenario, ws picks the target page.
    smoke_hits: dict[int, dict] = {}
    try:
        for r in _rows_to_dicts(conn.execute(
                "SELECT id, ws, scenario FROM smoke_scenarios"
                " WHERE LOWER(scenario) LIKE LOWER(?) LIMIT 20", (like,))):
            smoke_hits[r["id"]] = {
                "type": "smoke", "id": r["id"], "ws": r["ws"],
                "label": r["scenario"] or "(no name)",
                "match": _snippet(r["scenario"], q)}
        for r in _rows_to_dicts(conn.execute(
                "SELECT DISTINCT s.id, s.ws, s.scenario, st.aspen_ticket"
                " FROM smoke_steps st JOIN smoke_scenarios s"
                " ON s.id = st.scenario_id"
                " WHERE LOWER(st.aspen_ticket) LIKE LOWER(?) LIMIT 20",
                (like,))):
            smoke_hits.setdefault(r["id"], {
                "type": "smoke", "id": r["id"], "ws": r["ws"],
                "label": r["scenario"] or "(no name)",
                "match": f"ASPEN {r['aspen_ticket']}"})
    except sqlite3.OperationalError:
        pass  # module not initialised in this DB
    _add("Smoke scenarios", list(smoke_hits.values())[:20])

    # -- 10. Delegated tickets (2026-08-28 [USER]) — key + summary of the
    # delegated-tagged tickets, linking to the DELEGATED ticket detail
    # (until now they only surfaced via the Jira AC/comments block, which
    # links to the gatekeeper view).
    try:
        del_hits = [
            {"type": "delegated", "id": r["jira_key"],
             "label": f"{r['jira_key']} — {r['summary'] or ''}".rstrip(" —"),
             "match": r["jira_status"] or ""}
            for r in _rows_to_dicts(conn.execute(
                "SELECT jira_key, summary, jira_status FROM jira_issues"
                " WHERE seen_in_delegated = 1"
                " AND (LOWER(jira_key) LIKE LOWER(?)"
                "      OR LOWER(summary) LIKE LOWER(?)) LIMIT 20",
                (like, like)))]
    except sqlite3.OperationalError:
        del_hits = []  # jira schema / column not initialised in this DB
    _add("Delegated Testing", del_hits)

    return groups
