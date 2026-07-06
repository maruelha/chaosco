"""Impacted-defects counting for the retail report (user decisions 2026-07-06):
- 'impacted' = TC references the defect AND has not passed yet; the passed
  family comes from status_mappings (passed_with_dtc) — one definition.
- passed references stay visible as passed_tc_count (muted '(+N passed)').
- MB vs Sales = the manual DTC O2C flag; unset counts as Sales but is
  surfaced (dtco2c_unset) for the diagnostics note.
"""
import pytest

from app import database
from app.db.retail import get_retail_defects_impacted
from app.reporter import compute_impacted_totals, load_status_mappings, passed_family

PASSED = ["Passed", "conditionally passed", "Passed pending solman",
          "Passed, pending solman"]


@pytest.fixture()
def conn(tmp_path):
    c = database.init_db(tmp_path / "report.db")
    yield c
    c.close()


def _defect(conn, defect_id, dtco2c=None, status="In Progress"):
    with conn:
        conn.execute(
            "INSERT INTO defects (defect_id, channel, solman_status) VALUES (?, 'Retail', ?)",
            (defect_id, status))
        if dtco2c is not None:
            conn.execute(
                "INSERT INTO defect_annotations (defect_id, dtco2c) VALUES (?,?)",
                (defect_id, dtco2c))


def _tc(conn, name, defect_ref, status):
    with conn:
        conn.execute(
            "INSERT INTO retail (match_key, test_case_id, testcase_name, country,"
            " defect_id_ref, status) VALUES (?,?,?,'Germany',?,?)",
            (f"{name}|{status}|{defect_ref}", name, name, defect_ref, status))


def test_passed_family_excluded_from_impacted(conn):
    _defect(conn, "D-1", dtco2c=1)
    _tc(conn, "t1", "D-1", "Blocked DTC")
    _tc(conn, "t2", "D-1", "Ready for retest")     # resolved, retesting: still impacted
    _tc(conn, "t3", "D-1", " passed ")             # passed: no longer impacted
    _tc(conn, "t4", "D-1", "conditionally passed")
    _tc(conn, "t5", "D-1", "Passed pending solman")

    rows = get_retail_defects_impacted(conn, PASSED)
    assert len(rows) == 1
    assert rows[0]["impacted_tc_count"] == 2
    assert rows[0]["passed_tc_count"] == 3


def test_mb_sales_split_and_undecided(conn):
    _defect(conn, "D-MB", dtco2c=1)       # decided: ours
    _defect(conn, "D-SALES", dtco2c=0)    # decided: Sales
    _defect(conn, "D-UNSET")              # nobody decided -> Sales + flagged
    for d in ("D-MB", "D-SALES", "D-UNSET"):
        _tc(conn, f"t-{d}", d, "Blocked - returned to sales")

    rows = {r["defect_id"]: r for r in get_retail_defects_impacted(conn, PASSED)}
    assert rows["D-UNSET"]["dtco2c_unset"] == 1
    assert rows["D-MB"]["dtco2c_unset"] == 0 and rows["D-SALES"]["dtco2c_unset"] == 0

    totals = compute_impacted_totals(list(rows.values()))
    assert totals["mb"] == 1
    assert totals["sales"] == 2                       # decided-Sales + undecided
    assert totals["total"] == 3
    assert [d["defect_id"] for d in totals["undecided"]] == ["D-UNSET"]


def test_confirmed_and_withdrawn_defects_excluded(conn):
    _defect(conn, "D-OPEN", dtco2c=1)
    _defect(conn, "D-DONE", dtco2c=1, status="Confirmed")
    _tc(conn, "t1", "D-OPEN", "Blocked DTC")
    _tc(conn, "t2", "D-DONE", "Blocked DTC")
    assert [r["defect_id"] for r in get_retail_defects_impacted(conn, PASSED)] == ["D-OPEN"]


def test_passed_family_comes_from_status_mappings(conn):
    # the report config is the single source of the passed definition
    fam = passed_family(load_status_mappings())
    assert "Passed" in fam and "conditionally passed" in fam
    _defect(conn, "D-1", dtco2c=1)
    _tc(conn, "t1", "D-1", fam[0])
    rows = get_retail_defects_impacted(conn, fam)
    assert rows[0]["impacted_tc_count"] == 0
    assert rows[0]["passed_tc_count"] == 1
