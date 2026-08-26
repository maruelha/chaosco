"""Delegated Testing — bucket logic (2026-08-26).

Pure functions: Jira status + assignee -> the card/report sections. Kept out
of the web layer so the rules are testable and the later backlog items
(counted, not listed) can join the counting without touching routes.

Bucket rules [USER 2026-08-26]:
- Blocked         -> BLOCKED (top; shown ONLY there, wins over everything)
- Open            -> Open
- In Progress     -> "In progress with testing team", unless assigned to
                     Marina -> "Gatekeeper check Marina"
- In Verification -> "Waiting for Settlementfile creation"
- In Validation   -> "In validation with GBS key users"
- In Review       -> "Ready for Sales validations"
- Resolved/Closed/Done -> "Resolved / Closed"
- anything else   -> "Unexpected status" (nothing silently disappears)
"""
from __future__ import annotations

# (key, title, css class on the report section head)
SECTIONS = [
    ("blocked",    "🔴 BLOCKED",                          "sec-blocked"),
    ("open",       "Open",                                "sec-open"),
    ("team",       "In progress with testing team",       "sec-team"),
    ("marina",     "Gatekeeper check Marina",             "sec-marina"),
    ("settlement", "Waiting for Settlementfile creation", "sec-settle"),
    ("gbs",        "In validation with GBS key users",    "sec-gbs"),
    ("sales",      "Ready for Sales validations",         "sec-sales"),
    ("done",       "Resolved / Closed",                   "sec-done"),
    ("unexpected", "Unexpected status",                   "sec-unexpected"),
]

_DONE_STATUSES = {"resolved", "closed", "done"}


def bucket_key(issue: dict, me: str) -> str:
    """Section key for one issue. `me` = jira_gatekeeper_assignee (lowered);
    substring match on the assignee, same rule as the gatekeeper card."""
    status = (issue.get("jira_status") or "").strip().lower()
    assignee = (issue.get("jira_assignee") or "").lower()
    mine = bool(me) and me in assignee
    if status == "blocked":
        return "blocked"
    if status == "open":
        return "open"
    if status == "in progress":
        return "marina" if mine else "team"
    if status == "in verification":
        return "settlement"
    if status == "in validation":
        return "gbs"
    if status == "in review":
        return "sales"
    if status in _DONE_STATUSES:
        return "done"
    return "unexpected"


def bucket_issues(issues: list[dict], me: str) -> list[tuple[str, str, str, list]]:
    """All issues grouped into the ordered sections:
    [(key, title, css, items), ...] — every section present, empty or not."""
    by_key: dict[str, list] = {key: [] for key, _, _ in SECTIONS}
    for issue in issues:
        by_key[bucket_key(issue, me)].append(issue)
    return [(key, title, css, by_key[key]) for key, title, css in SECTIONS]


def bucket_counts(issues: list[dict], me: str) -> list[tuple[str, str, int]]:
    """[(key, title, count), ...] for the numbers report — same rules, the
    future backlog items will be added onto these counts here."""
    return [(key, title, len(items))
            for key, title, _, items in bucket_issues(issues, me)]
