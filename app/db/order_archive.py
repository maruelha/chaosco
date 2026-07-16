"""Order-details archive — grouped history storage (2026-07-16).

"Archive selected as group" [USER]: the SELECTED live order rows of an entity
are copied here as one batch (shared batch_id + archived_at + optional label)
and removed from the live order_details table — the live list stays short,
the past stays visible, and orders that belong together (sales + return +
exchange order of one transaction chain) stay together. Same generic
(entity_type, entity_id) address as notes / order_details / next_step_history;
consumed by the drop-in component _order_details.html.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import _rows_to_dicts, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS order_details_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    batch_id     INTEGER NOT NULL,
    order_type   TEXT,
    order_number TEXT,
    comment      TEXT,
    docs_in_s4   INTEGER DEFAULT 0,
    label        TEXT,
    archived_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_od_hist_entity
    ON order_details_history(entity_type, entity_id);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def archive_order_details(conn: sqlite3.Connection, entity_type: str,
                          entity_id: str, detail_ids: list[int],
                          label: str = "") -> dict:
    """Copy the selected live rows into history as ONE batch, then delete them.

    Only rows that belong to (entity_type, entity_id) are archived — ids of
    other entities are silently ignored. Returns {"batch_id", "count"};
    count 0 means nothing matched and nothing was written.
    """
    if not detail_ids:
        return {"batch_id": None, "count": 0}
    placeholders = ",".join("?" * len(detail_ids))
    rows = _rows_to_dicts(conn.execute(
        f"SELECT id, order_type, order_number, comment, docs_in_s4"
        f" FROM order_details WHERE entity_type=? AND entity_id=?"
        f" AND id IN ({placeholders}) ORDER BY id",
        (entity_type, str(entity_id), *detail_ids)))
    if not rows:
        return {"batch_id": None, "count": 0}

    archived_at = datetime.now().isoformat(sep=" ", timespec="minutes")
    with conn:
        batch_id = conn.execute(
            "SELECT COALESCE(MAX(batch_id), 0) + 1 FROM order_details_history"
        ).fetchone()[0]
        conn.executemany(
            "INSERT INTO order_details_history (entity_type, entity_id,"
            " batch_id, order_type, order_number, comment, docs_in_s4,"
            " label, archived_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [(entity_type, str(entity_id), batch_id, r["order_type"],
              r["order_number"], r["comment"], r["docs_in_s4"] or 0,
              label or "", archived_at) for r in rows])
        conn.execute(
            f"DELETE FROM order_details WHERE id IN "
            f"({','.join('?' * len(rows))})", [r["id"] for r in rows])
    return {"batch_id": batch_id, "count": len(rows)}


def list_order_batches(conn: sqlite3.Connection, entity_type: str,
                       entity_id: str) -> list[dict]:
    """Batches newest first, each with its rows oldest-first (like the live
    table). Shape: {batch_id, label, archived_at, items: [row, ...]}."""
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM order_details_history WHERE entity_type=? AND"
        " entity_id=? ORDER BY batch_id DESC, id",
        (entity_type, str(entity_id))))
    batches: list[dict] = []
    for r in rows:
        if not batches or batches[-1]["batch_id"] != r["batch_id"]:
            batches.append({"batch_id": r["batch_id"], "label": r["label"],
                            "archived_at": r["archived_at"], "items": []})
        batches[-1]["items"].append(
            {k: r[k] for k in ("id", "order_type", "order_number",
                               "comment", "docs_in_s4")})
    return batches


def delete_order_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM order_details_history WHERE batch_id=?",
                     (batch_id,))
