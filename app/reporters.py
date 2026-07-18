"""Reporter helpers [USER 2026-07-18].

ECOM tickets are raised by a FIXED expected set of reporters (config key
`ecom_reporters`, default Phalk + Calvin). Jira exports carry the reporter
as "Lastname, Firstname" — matching is a case-insensitive substring test
on the short name, so "Jindal, Phalk" matches "Phalk". Pure logic, no I/O.
"""
from __future__ import annotations

_DEFAULT_REPORTERS = ["Phalk", "Calvin"]


def expected_reporters(cfg: dict) -> list[str]:
    return cfg.get("ecom_reporters", _DEFAULT_REPORTERS)


def short_reporter(raw: str | None, expected: list[str]) -> str | None:
    """The expected short name contained in the raw Jira reporter, or None."""
    low = (raw or "").lower()
    if not low.strip():
        return None
    for name in expected:
        if name.lower() in low:
            return name
    return None
