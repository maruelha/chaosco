"""Delegated Testing — bucket logic (2026-08-26).

Pure functions: Jira status -> the card/report sections. Kept out
of the web layer so the rules are testable and the later backlog items
(counted, not listed) can join the counting without touching routes.

Bucket rules — the workflow wording agreed [USER 2026-08-31]:
- Blocked         -> "Blocker" (top; shown ONLY there, wins over everything)
- Open, Reopened  -> "Not started yet" (Reopened added 2026-09-01 [USER]:
                     "to be treated exactly the same as opened")
- Accepted        -> "Testing team creating order"
- In Progress     -> "Marina gatekeeper check"
- In Verification -> "Settlement file to be created"
- In Validation   -> "With GBS key users"
- In Review       -> "ECOM BPO test"
- Resolved/Closed/Done -> "Test case completed"
- anything else   -> "Unexpected status" (nothing silently disappears)

The assignee no longer decides anything [USER 2026-08-31]: until today
"In Progress" split into testing team / Marina by assignee; the team's
work now carries its own status "Accepted", so In Progress always means
"Marina gatekeeper check" and the old `team` bucket is gone.
"""
from __future__ import annotations

# (key, title, css class on the report section head)
SECTIONS = [
    ("blocked",    "🔴 Blocker",                          "sec-blocked"),
    ("open",       "Not started yet",                     "sec-open"),
    ("accepted",   "Testing team creating order",         "sec-accepted"),
    ("marina",     "Marina gatekeeper check",             "sec-marina"),
    ("settlement", "Settlement file to be created",       "sec-settle"),
    ("gbs",        "With GBS key users",                  "sec-gbs"),
    ("sales",      "ECOM BPO test",                       "sec-sales"),
    ("done",       "Test case completed",                 "sec-done"),
    ("unexpected", "Unexpected status",                   "sec-unexpected"),
    # per-ticket authored flag [USER 2026-08-27]: parked work — own section
    # at the bottom, EXCLUDED from the Management Summary (numbers_context
    # filters backlog issues out before staged_counts/goal/total)
    ("backlog",    "📦 Backlog",                          "sec-backlog"),
]

_DONE_STATUSES = {"resolved", "closed", "done"}
# "Reopened" is not started again, exactly like Open [USER 2026-09-01]
_OPEN_STATUSES = {"open", "reopened"}

# board section colors — style.css ui-section modifiers (a bare rt-section
# summary is WHITE text without one, i.e. invisible on the white box)
BOARD_CSS = {
    "blocked":    "ui-section--red",
    "open":       "ui-section--slate",
    "accepted":   "ui-section--teal",
    "marina":     "ui-section--amber",
    "settlement": "ui-section--purple",
    "gbs":        "ui-section--blue",
    "sales":      "ui-section--green",
    "done":       "ui-section--gray",
    "unexpected": "ui-section--gray",
    "backlog":    "ui-section--gray",
}


def bucket_key(issue: dict) -> str:
    """Section key for one issue — purely by Jira status since 2026-08-31.
    The authored backlog flag wins over EVERYTHING (even Blocked) — a
    parked ticket is out of the active workflow [USER 2026-08-27]."""
    if issue.get("backlog"):
        return "backlog"
    status = (issue.get("jira_status") or "").strip().lower()
    if status == "blocked":
        return "blocked"
    if status in _OPEN_STATUSES:
        return "open"
    if status == "accepted":
        return "accepted"
    if status == "in progress":
        return "marina"
    if status == "in verification":
        return "settlement"
    if status == "in validation":
        return "gbs"
    if status == "in review":
        return "sales"
    if status in _DONE_STATUSES:
        return "done"
    return "unexpected"


def bucket_issues(issues: list[dict]) -> list[tuple[str, str, str, list]]:
    """All issues grouped into the ordered sections:
    [(key, title, css, items), ...] — every section present, empty or not."""
    by_key: dict[str, list] = {key: [] for key, _, _ in SECTIONS}
    for issue in issues:
        by_key[bucket_key(issue)].append(issue)
    return [(key, title, css, by_key[key]) for key, title, css in SECTIONS]


def unexpected_statuses(issues: list[dict]) -> list[tuple[str, int]]:
    """[(status, count), …] of everything in the "Unexpected status" bucket,
    most frequent first — so a report can NAME what it could not place
    [USER 2026-09-01: "when there is an unexpected Jira status mention what
    the status is so one does not need to research"]. A missing/blank status
    is reported as "(no status)" rather than as an empty label."""
    counts: dict[str, int] = {}
    for issue in issues:
        if bucket_key(issue) == "unexpected":
            key = (issue.get("jira_status") or "").strip() or "(no status)"
            counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def bucket_counts(issues: list[dict]) -> list[tuple[str, str, int]]:
    """[(key, title, count), ...] for the numbers report — same rules, the
    future backlog items will be added onto these counts here."""
    return [(key, title, len(items))
            for key, title, _, items in bucket_issues(issues)]


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
    "gbs":        {"in progress", "clarification needed",
                   # [USER 2026-08-28] "Ready for Validation is perfectly ok"
                   "ready for validation"},
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
    ("pre_gatekeeper",  "Until Gatekeeper Check",    ("open", "accepted", "marina")),
    ("post_gatekeeper", "Past Gatekeeper Check",     ("settlement", "gbs", "sales", "done")),
]


def staged_counts(issues: list[dict]):
    """(stages, unexpected) — stages: [(key, label, stage_total,
    [(bucket_key, bucket_title, count), ...]), ...]; unexpected:
    (bucket_key, bucket_title, count)."""
    counts = {key: count for key, _title, count in bucket_counts(issues)}
    titles = {key: title for key, title, _css in SECTIONS}
    stages = []
    for skey, slabel, bucket_keys in STAGES:
        rows = [(k, titles[k], counts[k]) for k in bucket_keys]
        stages.append((skey, slabel, sum(c for _k, _t, c in rows), rows))
    unexpected = ("unexpected", titles["unexpected"], counts["unexpected"])
    return stages, unexpected


# ---------------------------------------------------------------------------
# Delegated Testing Overview (2026-08-31) — the management report.
#
# A SECOND grouping of the same buckets, on top of STAGES: four pipeline
# stages named for who holds the ball, each shown with two lines —
# "In progress" (by Jira status) and "Blocked" (by the responsible TEAM of
# the ticket's blocker, because a blocked ticket's status says nothing
# about who has to move) [USER 2026-08-31].

# (key, card label, owner shown under it, bucket keys on the In-progress line)
OVERVIEW_STAGES = [
    ("tech",     "TECH TEST EXECUTION",         "Sales Tech", ("open", "accepted")),
    ("mb",       "MB EXECUTION & VERIFICATION", "MB",         ("marina", "settlement", "gbs")),
    ("bpo",      "ECOM BPO VERIFICATION",       "ECOM BPO",   ("sales",)),
    ("complete", "COMPLETE",                    None,         ("done",)),
]

# blocker team -> stage [USER 2026-08-31]. Everything starting with "Sales"
# plus Omni is Tech; PDM [USER 2026-09-01], DTC O2C and MB BIZ are MB;
# Kibana and ECOM BPO are the BPO stage. A blocked ticket whose blockers
# carry no mapped team is reported on its own line rather than silently
# dropped.
_TEAM_STAGES = {"omni": "tech",
                "pdm": "mb", "dtc o2c": "mb", "mb biz": "mb",
                "kibana": "bpo", "ecom bpo": "bpo"}

# the stacked status bar [USER 2026-08-31] — the four groups management asked
# for; "Unexpected status" joins as a fifth segment only when non-empty, so
# the bar always adds up to the report total.
BAR_GROUPS = [
    ("passed",      "Passed",      ("done",)),
    ("in_progress", "In Progress", ("accepted", "marina", "settlement", "gbs", "sales")),
    ("blocked",     "Blocked",     ("blocked",)),
    ("not_started", "Not Started", ("open",)),
]


def overview_team_stage(team) -> str | None:
    """Pipeline stage for a blocker's responsible team, None if unmapped."""
    import re
    t = re.sub(r"\s+", " ", str(team or "")).strip().casefold()
    if not t:
        return None
    if t.startswith("sales"):
        return "tech"
    return _TEAM_STAGES.get(t)


def blocked_stage(issue: dict) -> str | None:
    """Stage of a BLOCKED ticket = the EARLIEST stage among the teams of its
    blockers [USER 2026-08-31] — a ticket blocked by two teams must still be
    counted exactly once or the pipeline stops adding up to the total."""
    stages = {overview_team_stage(b.get("team"))
              for b in (issue.get("blockers") or [])}
    for key, _label, _owner, _buckets in OVERVIEW_STAGES:
        if key in stages:
            return key
    return None


def overview_counts(issues: list[dict]) -> dict:
    """Everything the Overview report shows. Issues must carry `blockers`
    (list of blocker dicts with a `team`); backlog issues are expected to be
    filtered out by the caller, and are excluded from the total regardless.

    stages[] + blocked_unassigned + unexpected == total == sum(bar counts).
    """
    by_key: dict[str, list] = {key: [] for key, _t, _c in SECTIONS}
    for issue in issues:
        by_key[bucket_key(issue)].append(issue)

    blocked_by_stage = {key: 0 for key, _l, _o, _b in OVERVIEW_STAGES}
    blocked_unassigned = 0
    for issue in by_key["blocked"]:
        key = blocked_stage(issue)
        if key:
            blocked_by_stage[key] += 1
        else:
            blocked_unassigned += 1

    stages = []
    for key, label, owner, bucket_keys in OVERVIEW_STAGES:
        in_progress = sum(len(by_key[b]) for b in bucket_keys)
        blocked = blocked_by_stage[key]
        stages.append({"key": key, "label": label, "owner": owner,
                       "in_progress": in_progress, "blocked": blocked,
                       "total": in_progress + blocked})

    bar = [{"key": key, "label": label,
            "count": sum(len(by_key[b]) for b in bucket_keys)}
           for key, label, bucket_keys in BAR_GROUPS]
    unexpected = len(by_key["unexpected"])
    if unexpected:
        bar.append({"key": "unexpected", "label": "Unexpected status",
                    "count": unexpected})

    total = sum(len(items) for key, items in by_key.items() if key != "backlog")
    return {"stages": stages, "blocked_unassigned": blocked_unassigned,
            "unexpected": unexpected,
            # name them, so nobody has to go and look them up [USER 2026-09-01]
            "unexpected_statuses": unexpected_statuses(issues),
            "bar": bar, "total": total}
