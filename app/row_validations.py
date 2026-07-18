"""Row validations — registry of per-row data-quality checks (2026-07-18).

Flags rows whose imported Excel data doesn't line up (first case: status
"conditionally passed" needs "Reason for pass with reservation" filled).
The boards show a small red ⚠ button on flagged rows; clicking it opens
the shared dialog (_row_validation_dialog.html) with the finding texts.

ADDING A VALIDATION = write one check function (row dict -> problem text
or None) and append one Rule to RULES with the verticals it applies to.
Nothing else: the web layer and the dialog are generic. Pure logic — no
SQL, no Flask, no I/O here (mirrors issue_messages.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Rule:
    key: str                              # stable id, may appear in tests/docs
    verticals: tuple[str, ...]            # boards it runs on: "retail", "ecom", …
    check: Callable[[dict], str | None]   # row -> problem text, or None if fine


def _blank(row: dict, field: str) -> bool:
    return not (row.get(field) or "").strip()


def _reason_for_conditional_pass(row: dict) -> str | None:
    status = (row.get("status") or "").strip().lower()
    if status == "conditionally passed" and _blank(row, "reason_for_pass_with_reservation"):
        return ('Status is "conditionally passed" but "Reason for pass with '
                'reservation" is empty — fill the reason in the tracking Excel.')
    return None


RULES: list[Rule] = [
    Rule("reason_for_conditional_pass", ("retail", "ecom"),
         _reason_for_conditional_pass),
]


def validate_row(vertical: str, row: dict) -> list[str]:
    """All problem texts for one row (empty list = row is fine)."""
    findings = []
    for rule in RULES:
        if vertical in rule.verticals:
            msg = rule.check(row)
            if msg:
                findings.append(msg)
    return findings


def validate_rows(vertical: str, rows: list[dict], id_field: str) -> dict:
    """{row[id_field]: [problem texts]} — only rows with findings appear."""
    out = {}
    for row in rows:
        findings = validate_row(vertical, row)
        if findings:
            out[row[id_field]] = findings
    return out
