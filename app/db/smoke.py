"""CORE SOUTH Smoke Testing (planning chat 2026-08-27).

Imported from the EU CS Smoke Test execution workbook, WS in
{eCOM, Retail} with MB Invoice Validation = WAHR only (see
docs/claude/smoke.md). smoke_scenarios / smoke_steps is a 1:n import pair
(replace-all on each import, like every other imported vertical) — never
holds user-authored data.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.core import get_connection

# eCOM scenarios split into OMNI vs ECOM by Package (planning chat
# 2026-08-27) — everything else eCOM falls into ECOM.
OMNI_PACKAGES = {"click & collect", "ship from store", "return in store"}

STATUS_NOT_STARTED = "Not Started"
STATUS_IN_PROGRESS = "In Progress"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS smoke_scenarios (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    row_id       INTEGER,
    package      TEXT,
    ws           TEXT,
    scenario     TEXT,
    comment      TEXT,
    status       TEXT,
    company_code TEXT,
    sales_org    TEXT,
    plant        TEXT,
    store_code   TEXT
);
CREATE INDEX IF NOT EXISTS ix_smoke_scenarios_ws ON smoke_scenarios(ws);

-- USER-AUTHORED (2026-08-28): Marina's own comment + next step per
-- scenario, keyed by the Excel RowID (stable across re-imports —
-- replace_all rewrites smoke_scenarios/smoke_steps but NEVER this table).
CREATE TABLE IF NOT EXISTS smoke_annotations (
    row_id     INTEGER PRIMARY KEY,
    comment    TEXT,
    next_step  TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS smoke_steps (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id       INTEGER NOT NULL REFERENCES smoke_scenarios(id),
    row_id            INTEGER,
    step              TEXT,
    expected_result   TEXT,
    comment           TEXT,
    owner_email       TEXT,
    owner             TEXT,
    ws_executing      TEXT,
    aspen_ticket      TEXT,
    execution_status  TEXT,
    progress          TEXT
);
CREATE INDEX IF NOT EXISTS ix_smoke_steps_scenario ON smoke_steps(scenario_id);
"""


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # migrations (safe to re-run)
        for ddl in (
            # KT tracking (2026-08-28 [USER]): which smoke scenarios had
            # their knowledge transfer — authored checkbox + date.
            "ALTER TABLE smoke_annotations ADD COLUMN"
            " kt_done INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE smoke_annotations ADD COLUMN kt_date TEXT",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_smoke_annotations(conn: sqlite3.Connection) -> dict[int, dict]:
    """{row_id: {'comment': ..., 'next_step': ...}} — Marina's authored
    fields, merged onto the scenarios in the web layer. Tolerant of the
    table not existing yet (partial-init test fixtures)."""
    try:
        return {r: {"comment": c, "next_step": ns,
                    "kt_done": bool(kt), "kt_date": kd}
                for r, c, ns, kt, kd in conn.execute(
                    "SELECT row_id, comment, next_step, kt_done, kt_date"
                    " FROM smoke_annotations")}
    except sqlite3.OperationalError:
        return {}


def get_smoke_comment(conn: sqlite3.Connection, row_id: int) -> str | None:
    row = conn.execute(
        "SELECT comment FROM smoke_annotations WHERE row_id=?",
        (row_id,)).fetchone()
    return row[0] if row else None


def set_smoke_comment(conn: sqlite3.Connection, row_id: int,
                      comment: str | None) -> None:
    """Only-this-field upsert (inline edit on the scenario accordion)."""
    with conn:
        conn.execute("""
            INSERT INTO smoke_annotations (row_id, comment, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(row_id) DO UPDATE SET
                comment    = excluded.comment,
                updated_at = excluded.updated_at
        """, (row_id, comment or None, _now()))


def get_smoke_next_step(conn: sqlite3.Connection, row_id: int) -> str | None:
    row = conn.execute(
        "SELECT next_step FROM smoke_annotations WHERE row_id=?",
        (row_id,)).fetchone()
    return row[0] if row else None


def set_smoke_next_step(conn: sqlite3.Connection, row_id: int,
                        next_step: str | None) -> None:
    """Only-this-field upsert (inline edit + next-step archive component,
    entity type 'smoke')."""
    with conn:
        conn.execute("""
            INSERT INTO smoke_annotations (row_id, next_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(row_id) DO UPDATE SET
                next_step  = excluded.next_step,
                updated_at = excluded.updated_at
        """, (row_id, next_step or None, _now()))


def set_smoke_kt(conn: sqlite3.Connection, row_id: int, done: bool,
                 kt_date: str | None) -> None:
    """Only-these-fields upsert — KT (knowledge transfer) checkbox + date
    per scenario [USER 2026-08-28]."""
    with conn:
        conn.execute("""
            INSERT INTO smoke_annotations (row_id, kt_done, kt_date, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(row_id) DO UPDATE SET
                kt_done    = excluded.kt_done,
                kt_date    = excluded.kt_date,
                updated_at = excluded.updated_at
        """, (row_id, 1 if done else 0, (kt_date or "").strip() or None, _now()))


def scenario_count(conn: sqlite3.Connection) -> int:
    """Total imported scenarios (eCOM + Retail) — dashboard card badge.
    Tolerant of the table not existing yet (partial-init test fixtures)."""
    try:
        return conn.execute("SELECT COUNT(*) FROM smoke_scenarios").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def is_omni_package(package: str | None) -> bool:
    return (package or "").strip().lower() in OMNI_PACKAGES


def replace_all(conn: sqlite3.Connection, scenarios: list[dict]) -> dict:
    """Replace the whole import: delete everything, insert fresh.

    `scenarios` is a list of scenario dicts (row_id, package, ws, scenario,
    comment, status, company_code, sales_org, plant, store_code), each with
    a 'steps' key holding that scenario's step dicts (row_id, step,
    expected_result, comment, owner_email, owner, ws_executing,
    aspen_ticket, execution_status, progress). Returns
    {'scenarios': n, 'steps': n}.
    """
    n_scenarios = 0
    n_steps = 0
    with conn:
        conn.execute("DELETE FROM smoke_steps")
        conn.execute("DELETE FROM smoke_scenarios")
        for s in scenarios:
            cur = conn.execute(
                "INSERT INTO smoke_scenarios"
                " (row_id, package, ws, scenario, comment, status,"
                "  company_code, sales_org, plant, store_code)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s.get("row_id"), s.get("package"), s.get("ws"),
                 s.get("scenario"), s.get("comment"), s.get("status"),
                 s.get("company_code"), s.get("sales_org"), s.get("plant"),
                 s.get("store_code")))
            scenario_id = cur.lastrowid
            n_scenarios += 1
            for st in s.get("steps", []):
                conn.execute(
                    "INSERT INTO smoke_steps"
                    " (scenario_id, row_id, step, expected_result, comment,"
                    "  owner_email, owner, ws_executing, aspen_ticket,"
                    "  execution_status, progress)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (scenario_id, st.get("row_id"), st.get("step"),
                     st.get("expected_result"), st.get("comment"),
                     st.get("owner_email"), st.get("owner"),
                     st.get("ws_executing"), st.get("aspen_ticket"),
                     st.get("execution_status"), st.get("progress")))
                n_steps += 1
    return {"scenarios": n_scenarios, "steps": n_steps}


def list_scenarios(conn: sqlite3.Connection, ws: str) -> list[dict]:
    """Scenarios for one WS ('eCOM' or 'Retail'), each with its 'steps'
    list attached, ordered by RowID. Tolerant of the tables not existing
    yet (partial-init test fixtures, same pattern as the rest of app.db)."""
    try:
        scenarios = _rows_to_dicts(conn.execute(
            "SELECT * FROM smoke_scenarios WHERE ws = ? ORDER BY row_id",
            (ws,)))
    except sqlite3.OperationalError:
        return []
    if not scenarios:
        return []
    ids = [s["id"] for s in scenarios]
    placeholders = ",".join("?" for _ in ids)
    steps_by_scenario: dict[int, list[dict]] = {sid: [] for sid in ids}
    for step in _rows_to_dicts(conn.execute(
            f"SELECT * FROM smoke_steps WHERE scenario_id IN ({placeholders})"
            f" ORDER BY row_id", ids)):
        steps_by_scenario[step["scenario_id"]].append(step)
    for s in scenarios:
        s["steps"] = steps_by_scenario[s["id"]]
    return scenarios


def get_scenario(conn: sqlite3.Connection, scenario_id: int) -> dict | None:
    rows = _rows_to_dicts(conn.execute(
        "SELECT * FROM smoke_scenarios WHERE id = ?", (scenario_id,)))
    if not rows:
        return None
    scenario = rows[0]
    scenario["steps"] = _rows_to_dicts(conn.execute(
        "SELECT * FROM smoke_steps WHERE scenario_id = ? ORDER BY row_id",
        (scenario_id,)))
    return scenario


def _status_counts(scenarios: list[dict]) -> dict:
    """total / not_started / in_progress / completed over a list of scenario
    dicts. Blank/NaN Status folds into not_started — untouched reads as not
    started for this overview [judgment call 2026-08-27, flagged to Marina]."""
    counts = {"total": len(scenarios), "not_started": 0, "in_progress": 0,
              "completed": 0}
    for s in scenarios:
        status = (s.get("status") or "").strip()
        if status == STATUS_IN_PROGRESS:
            counts["in_progress"] += 1
        elif status == STATUS_NOT_STARTED or not status:
            counts["not_started"] += 1
        else:
            counts["completed"] += 1
    return counts


def overview_counts(conn: sqlite3.Connection) -> dict:
    """{'ecom': {...}, 'omni': {...}, 'retail': {...}} — total/not_started/
    in_progress/completed per report, from scenario Status. eCOM scenarios
    split OMNI vs ECOM by Package (is_omni_package)."""
    ecom_all = list_scenarios(conn, "eCOM")
    omni = [s for s in ecom_all if is_omni_package(s.get("package"))]
    ecom = [s for s in ecom_all if not is_omni_package(s.get("package"))]
    retail = list_scenarios(conn, "Retail")
    return {
        "ecom": _status_counts(ecom),
        "omni": _status_counts(omni),
        "retail": _status_counts(retail),
    }
