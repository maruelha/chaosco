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
    # per-ticket authored flag [USER 2026-08-27]: parked work — own section
    # at the bottom, EXCLUDED from the Management Summary (numbers_context
    # filters backlog issues out before staged_counts/goal/total)
    ("backlog",    "📦 Backlog",                          "sec-backlog"),
]

_DONE_STATUSES = {"resolved", "closed", "done"}

# board section colors — style.css ui-section modifiers (a bare rt-section
# summary is WHITE text without one, i.e. invisible on the white box)
BOARD_CSS = {
    "blocked":    "ui-section--red",
    "open":       "ui-section--slate",
    "team":       "ui-section--teal",
    "marina":     "ui-section--amber",
    "settlement": "ui-section--purple",
    "gbs":        "ui-section--blue",
    "sales":      "ui-section--green",
    "done":       "ui-section--gray",
    "unexpected": "ui-section--gray",
    "backlog":    "ui-section--gray",
}


def bucket_key(issue: dict, me: str) -> str:
    """Section key for one issue. `me` = jira_gatekeeper_assignee (lowered);
    substring match on the assignee, same rule as the gatekeeper card.
    The authored backlog flag wins over EVERYTHING (even Blocked) — a
    parked ticket is out of the active workflow [USER 2026-08-27]."""
    if issue.get("backlog"):
        return "backlog"
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


# MB Status expectations per bucket [USER 2026-08-28] — the ECOM tab's
# Status (column A) joined by Jira ID; only these four buckets show the
# MB Status column, and a value outside the expected set gets the
# mismatch color on the board. Matching is normalized (casefold,
# collapsed whitespace, en/em dashes unified) so "Blocked – returned to
# Sales" still matches. The literal wordings come from Marina — adjust
# HERE if her workbook spells them differently.
MB_EXPECTED = {
    "blocked":    {"blocked - returned to sales", "blocked dtc"},
    "settlement": {"", "not ready"},
    "gbs":        {"in progress", "clarification needed"},
    "sales":      {"passed", "conditionally passed"},
}


def _norm_mb(status) -> str:
    import re
    s = str(status or "").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*-\s*", " - ", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def mb_status_state(bucket: str, ecom_row: dict | None) -> str:
    """'' = this bucket has no MB Status column; 'none' = no ECOM-tab row
    for the ticket (neutral — not tracked is not wrong); 'ok' /
    'mismatch' = the row's Status against MB_EXPECTED."""
    expected = MB_EXPECTED.get(bucket)
    if expected is None:
        return ""
    if ecom_row is None:
        return "none"
    return "ok" if _norm_mb(ecom_row.get("status")) in expected else "mismatch"


# Management Summary staging (build plan step 10, 2026-08-27) — the same
# buckets grouped into 3 review stages [USER 2026-08-27]. "unexpected"
# belongs to no stage and is reported separately so nothing silently
# disappears (same rule as the buckets themselves).
STAGES = [
    ("blocked",        "Blocked",                   ("blocked",)),
    ("pre_gatekeeper",  "Until Gatekeeper Check",    ("open", "team", "marina")),
    ("post_gatekeeper", "Past Gatekeeper Check",     ("settlement", "gbs", "sales", "done")),
]


def staged_counts(issues: list[dict], me: str):
    """(stages, unexpected) — stages: [(key, label, stage_total,
    [(bucket_key, bucket_title, count), ...]), ...]; unexpected:
    (bucket_key, bucket_title, count)."""
    counts = {key: count for key, _title, count in bucket_counts(issues, me)}
    titles = {key: title for key, title, _css in SECTIONS}
    stages = []
    for skey, slabel, bucket_keys in STAGES:
        rows = [(k, titles[k], counts[k]) for k in bucket_keys]
        stages.append((skey, slabel, sum(c for _k, _t, c in rows), rows))
    unexpected = ("unexpected", titles["unexpected"], counts["unexpected"])
    return stages, unexpected
