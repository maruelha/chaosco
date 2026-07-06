"""Retail report computation layer — separate from the importer.

Handoff principle 4: reporting queries only, never imports.
All SQL goes through database.py; this module only applies bucket logic.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_DEFAULT_MAPPINGS = Path(__file__).parent.parent / "config" / "status_mappings.yaml"


def load_status_mappings(path: Path | None = None) -> dict:
    p = path or _DEFAULT_MAPPINGS
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def passed_family(mappings: dict) -> list[str]:
    """The report's ONE definition of 'passed' (bucket passed_with_dtc) —
    reused by the impacted-defects counting so there is no second opinion."""
    return mappings["buckets"]["passed_with_dtc"]["statuses"]


def compute_impacted_totals(defects: list[dict]) -> dict:
    """Totals over get_retail_defects_impacted rows. MB = the defect's manual
    DTC O2C flag; a defect nobody decided on counts as Sales (kept
    deliberately — 'undecided' lists them for the diagnostics note)."""
    return {
        "mb":     sum(d["impacted_tc_count"] for d in defects if d["dtco2c"]),
        "sales":  sum(d["impacted_tc_count"] for d in defects if not d["dtco2c"]),
        "total":  sum(d["impacted_tc_count"] for d in defects),
        "passed": sum(d["passed_tc_count"] for d in defects),
        "undecided": [d for d in defects if d["dtco2c_unset"]],
    }


def compute_retail_report(status_counts: dict[str, int], mappings: dict) -> dict:
    """Apply bucket config to a {status: count} dict. Returns a report dict.

    status_counts is produced by database.get_retail_status_counts() — kept
    separate so a future step can persist it before calling this function.
    """
    buckets_cfg    = mappings["buckets"]
    known_statuses = set(mappings["known_statuses"])
    known_unmapped = set(mappings["known_unmapped"])

    def _count(key: str) -> int:
        return sum(status_counts.get(s, 0) for s in buckets_cfg[key]["statuses"])

    back_with_sales    = _count("back_with_sales")
    with_dtc           = _count("with_dtc")
    in_progress_dtc    = _count("in_progress_with_dtc")
    passed_dtc         = _count("passed_with_dtc")
    incoming_gk        = _count("incoming_gatekeeper")
    ready_val          = _count("ready_for_validation")
    in_progress        = _count("in_progress")
    in_clarification   = _count("in_clarification")
    blocked            = _count("blocked")

    # Identity: In Progress with DTC + Passed with DTC must equal With DTC
    identity_lhs = in_progress_dtc + passed_dtc
    identity_ok  = identity_lhs == with_dtc

    # All statuses that count toward any bucket
    bucketed: set[str] = set()
    for bkt in buckets_cfg.values():
        bucketed.update(bkt["statuses"])

    # Diagnostics: statuses not in any bucket
    unmapped_known: dict[str, int] = {}
    unknown: dict[str, int] = {}
    leftover_count = 0
    for status, count in status_counts.items():
        if status in bucketed:
            continue
        leftover_count += count
        label = status if status else "(blank)"
        if status in known_unmapped:
            unmapped_known[label] = count
        elif status not in known_statuses:
            unknown[label] = count
        else:
            unmapped_known[label] = count  # in master list but no bucket

    return {
        "buckets": {
            "back_with_sales":      back_with_sales,
            "with_dtc":             with_dtc,
            "in_progress_with_dtc": in_progress_dtc,
            "passed_with_dtc":      passed_dtc,
            "incoming_gatekeeper":  incoming_gk,
            "ready_for_validation": ready_val,
            "in_progress":          in_progress,
            "in_clarification":     in_clarification,
            "blocked":              blocked,
        },
        "sanity": {
            "identity_ok":          identity_ok,
            "in_progress_with_dtc": in_progress_dtc,
            "passed_with_dtc":      passed_dtc,
            "with_dtc":             with_dtc,
            "lhs":                  identity_lhs,
        },
        "diagnostics": {
            "unmapped_known": unmapped_known,
            "unknown":        unknown,
            "leftover_count": leftover_count,
        },
        "total_rows": sum(status_counts.values()),
    }
