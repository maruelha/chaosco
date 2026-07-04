"""Tests for the Retail Requirements Tracker counting service (step 3).

The counting rules where a bug would be a silently wrong green:
- a (test, country) pair with multiple passed runs counts ONCE
- a previously passed test that is reopened UN-counts (live derivation)
- ALL-requirements derive their target from the active-country list
- named targets ("UK, IE") require EVERY listed country, not any-N
- an override adds exactly one country and survives status changes
- tab 4: category picks the applicable test kinds; done = all applicable
  kinds passed or overridden
- unresolved requirements / unknown categories are flagged, never counted done
"""
import pytest

from app.retail_tracker_counting import (
    build_passed_pairs,
    compute_requirements,
    compute_cpm,
)

ACTIVE = ["Germany", "Ireland", "United Kingdom"]


def req(id=1, test_case_id="T1", required_dtc=1, all_countries=0, **kw):
    base = {"id": id, "area": "sales", "name": f"req{id}",
            "test_case_id": test_case_id, "required_dtc": required_dtc,
            "all_countries": all_countries}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# build_passed_pairs
# ---------------------------------------------------------------------------

def test_duplicate_passed_runs_count_once():
    rows = [("T1", "Germany", "Passed"), ("T1", "Germany", "Passed")]
    assert build_passed_pairs(rows) == {("T1", "germany")}


def test_only_passed_status_counts():
    rows = [("T1", "Germany", "Passed"), ("T1", "Ireland", "Ready for retest"),
            ("T1", "United Kingdom", "Blocked DTC"), ("T2", "Germany", " passed ")]
    assert build_passed_pairs(rows) == {("T1", "germany"), ("T2", "germany")}


# ---------------------------------------------------------------------------
# requirements (tabs 1-3)
# ---------------------------------------------------------------------------

def test_simple_count_requirement_done():
    out = compute_requirements([req(required_dtc=2)], {},
                               {("T1", "germany"), ("T1", "ireland")}, ACTIVE, {})
    r = out["items"][0]
    assert r["done"] is True
    assert r["required"] == 2
    assert r["counted"] == ["Germany", "Ireland"]


def test_reopened_test_uncounts():
    # same requirement, but Ireland's pass was reopened -> only Germany counts
    out = compute_requirements([req(required_dtc=2)], {},
                               {("T1", "germany")}, ACTIVE, {})
    r = out["items"][0]
    assert r["done"] is False
    assert r["counted"] == ["Germany"]


def test_all_countries_derives_from_active_list():
    passed = {("T1", "germany"), ("T1", "ireland"), ("T1", "united kingdom")}
    out = compute_requirements([req(all_countries=1, required_dtc=None)], {},
                               passed, ACTIVE, {})
    assert out["items"][0]["required"] == 3
    assert out["items"][0]["done"] is True
    # a market is added -> the same requirement reopens
    out = compute_requirements([req(all_countries=1, required_dtc=None)], {},
                               passed, ACTIVE + ["Poland"], {})
    assert out["items"][0]["required"] == 4
    assert out["items"][0]["done"] is False


def test_named_targets_require_every_listed_country():
    targets = {1: ["United Kingdom", "Ireland"]}
    # two passes, but Germany is not a target -> NOT done, and progress
    # counts only target countries: 1/2, not 2/2 (user bug report 2026-07-04)
    out = compute_requirements([req(required_dtc=2)], targets,
                               {("T1", "germany"), ("T1", "united kingdom")}, ACTIVE, {})
    assert out["items"][0]["done"] is False
    assert out["items"][0]["progress_count"] == 1
    # both targets pass -> done
    out = compute_requirements([req(required_dtc=2)], targets,
                               {("T1", "ireland"), ("T1", "united kingdom")}, ACTIVE, {})
    assert out["items"][0]["done"] is True
    assert out["items"][0]["progress_count"] == 2
    assert out["items"][0]["targets"] == ["United Kingdom", "Ireland"]


def test_override_adds_exactly_one_country_and_survives_status():
    overrides = {1: ["Ireland"]}
    out = compute_requirements([req(required_dtc=2)], {},
                               {("T1", "germany")}, ACTIVE, overrides)
    r = out["items"][0]
    assert r["done"] is True
    assert r["counted"] == ["Germany", "Ireland"]
    assert r["overridden"] == ["Ireland"]
    # override on an already-passed country does not double count
    out = compute_requirements([req(required_dtc=2)], {},
                               {("T1", "ireland")}, ACTIVE, overrides)
    assert out["items"][0]["counted"] == ["Ireland"]
    assert out["items"][0]["done"] is False


def test_unresolved_requirement_flagged_never_done():
    out = compute_requirements([req(test_case_id=None)], {},
                               {("T1", "germany")}, ACTIVE, {})
    r = out["items"][0]
    assert r["done"] is False
    assert r["unresolved"] is True
    assert out["summary"]["unresolved"] == 1


def test_summary_counts():
    reqs = [req(id=1, required_dtc=1), req(id=2, required_dtc=3),
            req(id=3, test_case_id=None)]
    out = compute_requirements(reqs, {}, {("T1", "germany")}, ACTIVE, {})
    assert out["summary"] == {"total": 3, "done": 1, "open": 2, "unresolved": 1}


# ---------------------------------------------------------------------------
# tab 4 (country x payment method)
# ---------------------------------------------------------------------------

TAB4_TESTS = {"sale_card": "TC_SC", "sale_voucher": "TC_SV",
              "return_card": "TC_RC", "return_voucher": "TC_RV"}


def cpm(id=1, country="Germany", category="card", active=1, **kw):
    base = {"id": id, "country": country, "method_name": "AMEX",
            "category": category, "active": active}
    base.update(kw)
    return base


def test_passed_test_alone_is_not_done_only_ready():
    # both card tests green in Germany, but nobody confirmed the METHOD yet
    passed = {("TC_SC", "germany"), ("TC_RC", "germany")}
    out = compute_cpm([cpm()], TAB4_TESTS, passed, {})
    r = out["items"][0]
    assert r["done"] is False
    assert r["ready"] is True          # tests green -> checking is possible now
    assert r["kinds"]["sale_card"] == {"passed": True, "checked": False}
    assert out["summary"]["ready"] == 1


def test_done_requires_all_applicable_kinds_checked():
    passed = {("TC_SC", "germany"), ("TC_RC", "germany")}
    out = compute_cpm([cpm()], TAB4_TESTS, passed, {1: {"sale_card"}})
    assert out["items"][0]["done"] is False            # return_card unchecked
    out = compute_cpm([cpm()], TAB4_TESTS, passed, {1: {"sale_card", "return_card"}})
    assert out["items"][0]["done"] is True
    assert out["summary"]["done"] == 1


def test_voucher_row_uses_voucher_kinds_only():
    out = compute_cpm([cpm(category="voucher")], TAB4_TESTS, set(),
                      {1: {"sale_voucher", "return_voucher"}})
    assert out["items"][0]["done"] is True
    # card checks are irrelevant for a voucher row
    out = compute_cpm([cpm(category="voucher")], TAB4_TESTS, set(),
                      {1: {"sale_card", "return_card"}})
    assert out["items"][0]["done"] is False


def test_check_without_pass_still_counts_as_human_decision():
    # a check can stand alone (e.g. covered in an earlier run) — human wins
    out = compute_cpm([cpm()], TAB4_TESTS, set(),
                      {1: {"sale_card", "return_card"}})
    r = out["items"][0]
    assert r["done"] is True
    assert r["kinds"]["sale_card"] == {"passed": False, "checked": True}


def test_unknown_category_flagged_never_done():
    out = compute_cpm([cpm(category=None)], TAB4_TESTS,
                      {("TC_SC", "germany"), ("TC_RC", "germany"),
                       ("TC_SV", "germany"), ("TC_RV", "germany")}, {})
    r = out["items"][0]
    assert r["done"] is False
    assert r["unknown_category"] is True
    assert out["summary"]["unknown_category"] == 1


def test_inactive_cpm_rows_excluded():
    out = compute_cpm([cpm(active=0)], TAB4_TESTS, set(), {})
    assert out["items"] == []
    assert out["summary"]["total"] == 0
