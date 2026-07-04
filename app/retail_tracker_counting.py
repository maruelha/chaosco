"""Retail Requirements Tracker — the counting service (step 3).

Pure functions: statuses + overrides in, completion out. No SQL in here —
`compute_from_db()` at the bottom assembles the inputs via db_retail_tracker.

The central rule (handoff decision #1): NOTHING is stored as "tested".
Completion is derived per call from the CURRENT retail statuses, so a
reopened or failing test un-counts automatically. The only stored tested
state is a human override (with a mandatory reason).

Counting rules:
- a (test, country) pair counts ONCE no matter how many passed runs exist
- only status 'Passed' counts (case/whitespace-insensitive)
- named targets (e.g. "UK, IE") -> done when EVERY target country counts
- all_countries -> required = number of ACTIVE tracker countries
- otherwise -> done when >= required_dtc DISTINCT countries count
- tab 4: category picks the applicable kinds (card -> sale_card+return_card,
  voucher -> sale_voucher+return_voucher); done = all applicable kinds
  passed or overridden for that row's country
"""
from __future__ import annotations

_CATEGORY_KINDS = {
    "card": ("sale_card", "return_card"),
    "voucher": ("sale_voucher", "return_voucher"),
}


def _key(country: str) -> str:
    return country.strip().casefold()


def build_passed_pairs(rows) -> set[tuple[str, str]]:
    """[(test_case_id, country, status), ...] -> {(test_case_id, country_key)}.
    Distinct by construction — duplicate passed runs collapse into one pair."""
    return {
        (test_id, _key(country))
        for test_id, country, status in rows
        if test_id and country and str(status).strip().casefold() == "passed"
    }


def compute_requirements(requirements: list[dict],
                         targets_by_req: dict[int, list[str]],
                         passed_pairs: set[tuple[str, str]],
                         active_countries: list[str],
                         overrides_by_req: dict[int, list[str]]) -> dict:
    """Completion for tabs 1-3 requirements.

    Returns {"items": [...], "summary": {total, done, open, unresolved}}.
    Each item: requirement fields + required, counted, overridden, targets,
    done, unresolved.
    """
    items = []
    done_n = unresolved_n = 0
    for r in requirements:
        targets = targets_by_req.get(r["id"]) or None
        overridden = sorted(overrides_by_req.get(r["id"], []))
        item = {**r, "targets": targets, "overridden": overridden,
                "counted": [], "required": None, "done": False,
                "progress_count": 0,
                "unresolved": r["test_case_id"] is None}
        if item["unresolved"]:
            unresolved_n += 1
            items.append(item)
            continue

        # counted = passed countries ∪ overridden countries (distinct)
        counted: dict[str, str] = {}          # key -> display name
        for c in active_countries:
            if (r["test_case_id"], _key(c)) in passed_pairs:
                counted[_key(c)] = c
        for c in overridden:
            counted.setdefault(_key(c), c)
        item["counted"] = sorted(counted.values())

        if targets:
            item["required"] = len(targets)
            # progress counts ONLY target countries — a pass elsewhere is real
            # but does not advance this requirement (e.g. Germany vs "UK, IE")
            item["progress_count"] = sum(_key(t) in counted for t in targets)
            item["done"] = item["progress_count"] == len(targets)
        elif r["all_countries"]:
            item["required"] = len(active_countries)
            item["progress_count"] = len(counted)
            item["done"] = len(counted) >= item["required"]
        elif r["required_dtc"] is not None:
            item["required"] = r["required_dtc"]
            item["progress_count"] = len(counted)
            item["done"] = len(counted) >= item["required"]
        else:
            item["progress_count"] = len(counted)
        # required unknown -> stays not done, required None

        done_n += item["done"]
        items.append(item)

    return {"items": items,
            "summary": {"total": len(items), "done": done_n,
                        "open": len(items) - done_n, "unresolved": unresolved_n}}


def compute_cpm(cpm_rows: list[dict],
                tab4_tests: dict[str, str],
                passed_pairs: set[tuple[str, str]],
                checks_by_cpm: dict[int, set[str]]) -> dict:
    """Completion for tab 4 (country x payment method) rows.

    The four fixed tests pass ONCE per country, but a pass cannot say which
    payment methods the run exercised — that is human knowledge. So per
    applicable kind: `passed` = the kind's test is green in that country
    (the hint that checking is now possible), `checked` = a human confirmed
    this METHOD was covered. done = all applicable kinds CHECKED.

    tab4_tests: {test_kind: test_case_id}
    checks_by_cpm: {cpm_id: {test_kind, ...}} — manual confirmations
    Returns {"items": [...], "summary": {total, done, open, ready,
    unknown_category}}. `ready` = not done but every applicable test passed.
    Inactive rows are excluded entirely.
    """
    items = []
    done_n = ready_n = unknown_n = 0
    for row in cpm_rows:
        if not row.get("active", 1):
            continue
        kinds = _CATEGORY_KINDS.get(row["category"] or "")
        item = {**row, "kinds": {}, "done": False, "ready": False,
                "unknown_category": kinds is None}
        if kinds is None:
            unknown_n += 1
            items.append(item)
            continue

        checked_kinds = checks_by_cpm.get(row["id"], set())
        ckey = _key(row["country"])
        for kind in kinds:
            test_id = tab4_tests.get(kind)
            item["kinds"][kind] = {
                "passed": bool(test_id) and (test_id, ckey) in passed_pairs,
                "checked": kind in checked_kinds,
            }
        item["done"] = all(k["checked"] for k in item["kinds"].values())
        item["ready"] = (not item["done"]
                         and all(k["passed"] for k in item["kinds"].values()))
        done_n += item["done"]
        ready_n += item["ready"]
        items.append(item)

    return {"items": items,
            "summary": {"total": len(items), "done": done_n,
                        "open": len(items) - done_n, "ready": ready_n,
                        "unknown_category": unknown_n}}


# ---------------------------------------------------------------------------
# Assembly from the database (no SQL here — everything via db_retail_tracker)
# ---------------------------------------------------------------------------

def compute_from_db(conn) -> dict:
    """Gather inputs and compute everything. Returns
    {"requirements": {...}, "by_area": {area: {...}}, "cpm": {...}}."""
    from app import db_retail_tracker as db

    passed_pairs = build_passed_pairs(db.get_passed_status_rows(conn))
    active = [c["name"] for c in db.list_countries(conn, active_only=True)]
    requirements = db.list_requirements(conn)
    targets = db.get_targets_by_requirement(conn)
    req_overrides = db.get_requirement_overrides(conn)
    result = compute_requirements(requirements, targets, passed_pairs,
                                  active, req_overrides)

    by_area: dict[str, dict] = {}
    for item in result["items"]:
        s = by_area.setdefault(item["area"],
                               {"total": 0, "done": 0, "open": 0, "unresolved": 0})
        s["total"] += 1
        s["done"] += item["done"]
        s["open"] += not item["done"]
        s["unresolved"] += item["unresolved"]

    tab4_tests = {t["test_kind"]: t["test_case_id"]
                  for t in db.list_tab4_tests(conn) if t["test_case_id"]}
    cpm_result = compute_cpm(db.list_cpm(conn), tab4_tests, passed_pairs,
                             db.get_cpm_checks(conn))

    return {"requirements": result, "by_area": by_area, "cpm": cpm_result}
