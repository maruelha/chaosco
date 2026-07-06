"""Retail Requirements Tracker — schema + all SQL for the tracker vertical.

Own module by design (see docs/project_review_2026-07-04.md): new verticals get
their own DB module instead of growing database.py. Same rule as everywhere else:
the web layer never writes SQL — it calls functions here.

Tables:
    tracker_countries        — the tracker's own active-country list (join key vs
                               retail.country; the Excel's "18 = all" derives from
                               the active rows here, never from a hardcoded number)
    retail_requirements      — one row per requirement from tracking Excel tabs 1-3
    country_payment_methods  — tab 4 matrix (filled in step 2)
    tested_overrides         — "counted as done by decision"; the ONLY stored
                               tested-state, mandatory reason (used from step 5)

No stored passes: completion is always computed live from retail statuses.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app import database

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracker_countries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,      -- join key against retail.country
    excel_header TEXT,                       -- column header in the tracking Excel
    active       INTEGER NOT NULL DEFAULT 1,
    sort_order   INTEGER
);

CREATE TABLE IF NOT EXISTS retail_requirements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    area           TEXT NOT NULL,            -- sales | return | payment_general
    scenario_label TEXT,
    name           TEXT NOT NULL,
    excel_test_ref TEXT,                     -- the Excel's GKP…MU01 id, display only
    test_name      TEXT,                     -- name after the underscore (resolution key)
    test_case_id   TEXT,                     -- resolved dashboard id; NULL = unresolved
    sale_test_ref  TEXT,                     -- informational only (return tab)
    required_raw   TEXT,                     -- as written in Excel: '18', '3', '1 or 5'
    required_dtc   INTEGER,                  -- parsed count; NULL if all_countries or unparseable
    all_countries  INTEGER NOT NULL DEFAULT 0,
    comment        TEXT,
    excel_row      INTEGER,
    created_at     TEXT NOT NULL,
    UNIQUE(area, excel_row)
);

CREATE TABLE IF NOT EXISTS country_payment_methods (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    country     TEXT NOT NULL,
    method_name TEXT NOT NULL,
    category    TEXT,                        -- card | voucher
    active      INTEGER NOT NULL DEFAULT 1,
    excel_row   INTEGER,
    created_at  TEXT NOT NULL,
    UNIQUE(country, method_name)
);

CREATE TABLE IF NOT EXISTS tracker_missing_tests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,                -- user-authored: a test that SHOULD exist
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirement_country_targets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER NOT NULL,         -- FK retail_requirements
    country        TEXT NOT NULL,            -- named target: THIS country must pass
    UNIQUE(requirement_id, country)
);

CREATE TABLE IF NOT EXISTS tracker_tab4_tests (
    test_kind      TEXT PRIMARY KEY,         -- sale_card | sale_voucher | return_card | return_voucher
    excel_test_ref TEXT,                     -- Excel GKP…MU01 id, display only
    test_name      TEXT,                     -- resolution key (name after underscore)
    test_case_id   TEXT                      -- resolved dashboard id
);

CREATE TABLE IF NOT EXISTS cpm_checks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cpm_id     INTEGER NOT NULL,              -- FK country_payment_methods
    test_kind  TEXT NOT NULL,                 -- sale_card | sale_voucher | return_card | return_voucher
    created_at TEXT NOT NULL,
    UNIQUE(cpm_id, test_kind)
);
-- presence of a row = "this payment method WAS covered in that test kind's
-- passed run" — a manual human confirmation (the live pass alone cannot know
-- which methods a run exercised)

CREATE TABLE IF NOT EXISTS tested_overrides (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER,                  -- FK retail_requirements (tabs 1-3)
    cpm_id         INTEGER,                  -- FK country_payment_methods (tab 4)
    test_kind      TEXT,                     -- tab-4 checkbox kind, NULL for tabs 1-3
    country        TEXT NOT NULL,
    reason         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
"""


def init_schema(db_path: Path) -> None:
    conn = database.get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        # migrations (safe to re-run)
        for ddl in (
            "ALTER TABLE country_payment_methods ADD COLUMN comment TEXT",
            # user-authored, never touched by the importer (comment = Excel text)
            "ALTER TABLE country_payment_methods ADD COLUMN user_comment TEXT",
            "ALTER TABLE retail_requirements ADD COLUMN user_comment TEXT",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # already exists
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------

def seed_countries(conn: sqlite3.Connection, countries: list[tuple[str, str]]) -> int:
    """Insert countries (name, excel_header) if not present. Returns # inserted."""
    inserted = 0
    with conn:
        for order, (name, header) in enumerate(countries):
            cur = conn.execute(
                "INSERT OR IGNORE INTO tracker_countries (name, excel_header, active, sort_order)"
                " VALUES (?, ?, 1, ?)",
                (name, header, order),
            )
            inserted += cur.rowcount
    return inserted


def list_countries(conn: sqlite3.Connection, active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM tracker_countries"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY sort_order, name"
    return _rows_to_dicts(conn.execute(sql))


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

def upsert_requirements(conn: sqlite3.Connection, recs: list[dict]) -> dict:
    """Upsert by (area, excel_row). A manually resolved test_case_id is never
    overwritten with NULL by a re-run."""
    inserted = updated = 0
    now = _now()
    with conn:
        for r in recs:
            row = conn.execute(
                "SELECT id, test_case_id FROM retail_requirements WHERE area=? AND excel_row=?",
                (r["area"], r["excel_row"]),
            ).fetchone()  # tuple: (id, test_case_id)
            if row is None:
                conn.execute(
                    "INSERT INTO retail_requirements (area, scenario_label, name,"
                    " excel_test_ref, test_name, test_case_id, sale_test_ref,"
                    " required_raw, required_dtc, all_countries, comment, excel_row, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["area"], r["scenario_label"], r["name"], r["excel_test_ref"],
                     r["test_name"], r["test_case_id"], r["sale_test_ref"],
                     r["required_raw"], r["required_dtc"], r["all_countries"],
                     r["comment"], r["excel_row"], now),
                )
                inserted += 1
            else:
                keep_id = row[1] if r["test_case_id"] is None else r["test_case_id"]
                conn.execute(
                    "UPDATE retail_requirements SET scenario_label=?, name=?,"
                    " excel_test_ref=?, test_name=?, test_case_id=?, sale_test_ref=?,"
                    " required_raw=?, required_dtc=?, all_countries=?, comment=?"
                    " WHERE id=?",
                    (r["scenario_label"], r["name"], r["excel_test_ref"], r["test_name"],
                     keep_id, r["sale_test_ref"], r["required_raw"], r["required_dtc"],
                     r["all_countries"], r["comment"], row[0]),
                )
                updated += 1
    return {"inserted": inserted, "updated": updated}


def delete_requirements_not_in(conn: sqlite3.Connection,
                               keys: set[tuple[str, int]]) -> int:
    """Remove importer-derived rows no longer present in the parse (e.g. after
    a dedup-priority change). Their country targets go too. Returns # removed."""
    stale = [row[0] for row in conn.execute(
                 "SELECT id, area, excel_row FROM retail_requirements")
             if (row[1], row[2]) not in keys]
    with conn:
        for req_id in stale:
            conn.execute("DELETE FROM requirement_country_targets WHERE requirement_id=?",
                         (req_id,))
            conn.execute("DELETE FROM retail_requirements WHERE id=?", (req_id,))
    return len(stale)


def list_requirements(conn: sqlite3.Connection, area: str | None = None,
                      unresolved_only: bool = False) -> list[dict]:
    sql, params = "SELECT * FROM retail_requirements WHERE 1=1", []
    if area:
        sql += " AND area = ?"
        params.append(area)
    if unresolved_only:
        sql += " AND test_case_id IS NULL"
    sql += " ORDER BY area, excel_row"
    return _rows_to_dicts(conn.execute(sql, params))


def list_needs_decision(conn: sqlite3.Connection) -> list[dict]:
    """Rows whose 'DTC required' could not be parsed (e.g. '1 or 5')."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM retail_requirements"
        " WHERE all_countries = 0 AND required_dtc IS NULL"
        " ORDER BY area, excel_row"))


def requirement_counts(conn: sqlite3.Connection) -> dict:
    out = {"by_area": {}, "total": 0, "unresolved": 0, "needs_decision": 0}
    for area, n in conn.execute(
            "SELECT area, COUNT(*) FROM retail_requirements GROUP BY area"):
        out["by_area"][area] = n
        out["total"] += n
    out["unresolved"] = conn.execute(
        "SELECT COUNT(*) FROM retail_requirements WHERE test_case_id IS NULL").fetchone()[0]
    out["needs_decision"] = conn.execute(
        "SELECT COUNT(*) FROM retail_requirements"
        " WHERE all_countries = 0 AND required_dtc IS NULL").fetchone()[0]
    return out


def resolve_requirement(conn: sqlite3.Connection, req_id: int, test_case_id: str | None) -> None:
    with conn:
        conn.execute("UPDATE retail_requirements SET test_case_id=? WHERE id=?",
                     (test_case_id or None, req_id))


def assign_test_to_unresolved(conn: sqlite3.Connection, req_id: int,
                              test_case_id: str) -> bool:
    """Reverse manual pick (coverage check): link a passed dashboard test to a
    still-UNRESOLVED requirement. Refuses resolved rows so an existing link is
    never silently replaced. Returns True if the row was updated."""
    with conn:
        cur = conn.execute(
            "UPDATE retail_requirements SET test_case_id=?"
            " WHERE id=? AND test_case_id IS NULL",
            (test_case_id, req_id))
    return cur.rowcount == 1


def set_requirement_user_comment(conn: sqlite3.Connection, req_id: int,
                                 user_comment: str | None) -> None:
    with conn:
        conn.execute("UPDATE retail_requirements SET user_comment=? WHERE id=?",
                     (user_comment or None, req_id))


def replace_requirement_targets(conn: sqlite3.Connection, req_id: int,
                                countries: list[str]) -> None:
    """Named country targets (user decision 2026-07-04: comments like 'UK, IE'
    mean THOSE specific countries). Importer-derived, replaced on re-import."""
    with conn:
        conn.execute("DELETE FROM requirement_country_targets WHERE requirement_id=?",
                     (req_id,))
        for c in countries:
            conn.execute(
                "INSERT OR IGNORE INTO requirement_country_targets (requirement_id, country)"
                " VALUES (?,?)", (req_id, c))


def get_targets_by_requirement(conn: sqlite3.Connection) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for req_id, country in conn.execute(
            "SELECT requirement_id, country FROM requirement_country_targets"
            " ORDER BY requirement_id, country"):
        out.setdefault(req_id, []).append(country)
    return out


# ---------------------------------------------------------------------------
# Tab 4 — country-specific payment methods
# ---------------------------------------------------------------------------

def upsert_cpm_rows(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    """Upsert by (country, method_name). A manually set category is never
    overwritten with NULL by a re-run (the Excel's category cells are messy)."""
    inserted = updated = 0
    now = _now()
    with conn:
        for r in rows:
            existing = conn.execute(
                "SELECT id, category FROM country_payment_methods"
                " WHERE country=? AND method_name=?",
                (r["country"], r["method_name"]),
            ).fetchone()  # tuple: (id, category)
            if existing is None:
                conn.execute(
                    "INSERT INTO country_payment_methods"
                    " (country, method_name, category, active, excel_row, comment, created_at)"
                    " VALUES (?,?,?,1,?,?,?)",
                    (r["country"], r["method_name"], r["category"],
                     r["excel_row"], r["comment"], now),
                )
                inserted += 1
            else:
                keep_cat = existing[1] if r["category"] is None else r["category"]
                conn.execute(
                    "UPDATE country_payment_methods SET category=?, excel_row=?, comment=?"
                    " WHERE id=?",
                    (keep_cat, r["excel_row"], r["comment"], existing[0]),
                )
                updated += 1
    return {"inserted": inserted, "updated": updated}


def list_cpm(conn: sqlite3.Connection, unknown_category_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM country_payment_methods"
    if unknown_category_only:
        sql += " WHERE category IS NULL"
    sql += " ORDER BY country, method_name"
    return _rows_to_dicts(conn.execute(sql))


def cpm_counts(conn: sqlite3.Connection) -> dict:
    out = {"total": 0, "card": 0, "voucher": 0, "unknown": 0, "countries": 0}
    for cat, n in conn.execute(
            "SELECT category, COUNT(*) FROM country_payment_methods GROUP BY category"):
        out["total"] += n
        if cat == "card":
            out["card"] = n
        elif cat == "voucher":
            out["voucher"] = n
        else:
            out["unknown"] += n
    out["countries"] = conn.execute(
        "SELECT COUNT(DISTINCT country) FROM country_payment_methods").fetchone()[0]
    return out


def delete_cpm_not_in(conn: sqlite3.Connection,
                      keys: set[tuple[str, str]]) -> int:
    """Remove tab-4 rows no longer in the parse (e.g. the excluded 'Offline
    Transactions' rows). Their overrides go too. Returns # removed."""
    stale = [row[0] for row in conn.execute(
                 "SELECT id, country, method_name FROM country_payment_methods")
             if (row[1], row[2]) not in keys]
    with conn:
        for cpm_id in stale:
            conn.execute("DELETE FROM tested_overrides WHERE cpm_id=?", (cpm_id,))
            conn.execute("DELETE FROM cpm_checks WHERE cpm_id=?", (cpm_id,))
            conn.execute("DELETE FROM country_payment_methods WHERE id=?", (cpm_id,))
    return len(stale)


def set_cpm_category(conn: sqlite3.Connection, cpm_id: int, category: str | None) -> None:
    with conn:
        conn.execute("UPDATE country_payment_methods SET category=? WHERE id=?",
                     (category or None, cpm_id))


def set_cpm_user_comment(conn: sqlite3.Connection, cpm_id: int,
                         user_comment: str | None) -> None:
    with conn:
        conn.execute("UPDATE country_payment_methods SET user_comment=? WHERE id=?",
                     (user_comment or None, cpm_id))


def set_cpm_check(conn: sqlite3.Connection, cpm_id: int, test_kind: str,
                  value: bool) -> None:
    """Manual confirmation that this method was covered in that test kind's run."""
    with conn:
        if value:
            conn.execute(
                "INSERT OR IGNORE INTO cpm_checks (cpm_id, test_kind, created_at)"
                " VALUES (?,?,?)", (cpm_id, test_kind, _now()))
        else:
            conn.execute("DELETE FROM cpm_checks WHERE cpm_id=? AND test_kind=?",
                         (cpm_id, test_kind))


def get_cpm_checks(conn: sqlite3.Connection) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for cpm_id, kind in conn.execute("SELECT cpm_id, test_kind FROM cpm_checks"):
        out.setdefault(cpm_id, set()).add(kind)
    return out


def upsert_tab4_tests(conn: sqlite3.Connection, tests: list[dict]) -> None:
    with conn:
        for t in tests:
            conn.execute(
                "INSERT INTO tracker_tab4_tests (test_kind, excel_test_ref, test_name, test_case_id)"
                " VALUES (?,?,?,?)"
                " ON CONFLICT(test_kind) DO UPDATE SET excel_test_ref=excluded.excel_test_ref,"
                " test_name=excluded.test_name,"
                " test_case_id=COALESCE(excluded.test_case_id, tracker_tab4_tests.test_case_id)",
                (t["test_kind"], t["excel_test_ref"], t["test_name"], t["test_case_id"]),
            )


def list_tab4_tests(conn: sqlite3.Connection) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM tracker_tab4_tests ORDER BY test_kind"))


# ---------------------------------------------------------------------------
# Missing tests (user-authored alarm list on the board)
# ---------------------------------------------------------------------------

def add_missing_test(conn: sqlite3.Connection, text: str) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO tracker_missing_tests (text, created_at) VALUES (?,?)",
            (text, _now()))
    return cur.lastrowid


def list_missing_tests(conn: sqlite3.Connection) -> list[dict]:
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM tracker_missing_tests ORDER BY created_at, id"))


def delete_missing_test(conn: sqlite3.Connection, item_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM tracker_missing_tests WHERE id=?", (item_id,))


# ---------------------------------------------------------------------------
# Counting inputs (see retail_tracker_counting.py)
# ---------------------------------------------------------------------------

def get_passed_status_rows(conn: sqlite3.Connection) -> list[tuple]:
    """All (test_case_id, country, status) rows from retail — the counting
    service filters for 'Passed' itself (keeps the rule in ONE place)."""
    return conn.execute(
        "SELECT test_case_id, country, status FROM retail"
        " WHERE test_case_id IS NOT NULL AND country IS NOT NULL").fetchall()


def get_requirement_overrides(conn: sqlite3.Connection) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for req_id, country in conn.execute(
            "SELECT requirement_id, country FROM tested_overrides"
            " WHERE requirement_id IS NOT NULL"):
        out.setdefault(req_id, []).append(country)
    return out


def get_cpm_overrides(conn: sqlite3.Connection) -> dict[int, list[tuple[str, str]]]:
    out: dict[int, list[tuple[str, str]]] = {}
    for cpm_id, kind, country in conn.execute(
            "SELECT cpm_id, test_kind, country FROM tested_overrides"
            " WHERE cpm_id IS NOT NULL"):
        out.setdefault(cpm_id, []).append((kind, country))
    return out


def get_passed_test_coverage(conn: sqlite3.Connection) -> dict:
    """Of the distinct test cases with >=1 pass in retail: how many are linked
    to at least one requirement (or are a tab-4 fixed test)? The unmatched list
    is the actionable part — green tests the tracker is not counting anywhere."""
    linked = {row[0] for row in conn.execute(
        "SELECT DISTINCT test_case_id FROM retail_requirements"
        " WHERE test_case_id IS NOT NULL")}
    linked |= {row[0] for row in conn.execute(
        "SELECT test_case_id FROM tracker_tab4_tests WHERE test_case_id IS NOT NULL")}
    passed = _rows_to_dicts(conn.execute(
        "SELECT DISTINCT test_case_id, testcase_name FROM retail"
        " WHERE lower(trim(status)) = 'passed' ORDER BY test_case_id"))
    unmatched = [t for t in passed if t["test_case_id"] not in linked]
    return {"passed_total": len(passed),
            "matched": len(passed) - len(unmatched),
            "unmatched": unmatched}


# ---------------------------------------------------------------------------
# Lookups against the imported retail table (read-only)
# ---------------------------------------------------------------------------

def build_retail_name_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """Map normalized name-after-underscore -> test_case_id from retail.testcase_name."""
    lookup: dict[str, str] = {}
    for test_case_id, name in conn.execute(
            "SELECT DISTINCT test_case_id, testcase_name FROM retail"
            " WHERE testcase_name IS NOT NULL"):
        if "_" in name:
            key = " ".join(name.split("_", 1)[1].split()).lower()
            lookup.setdefault(key, test_case_id)
    return lookup


def get_retail_test_options(conn: sqlite3.Connection) -> list[dict]:
    """Distinct dashboard tests for the manual-resolve dropdown."""
    return _rows_to_dicts(conn.execute(
        "SELECT DISTINCT test_case_id, testcase_name FROM retail"
        " WHERE testcase_name IS NOT NULL ORDER BY testcase_name"))
