"""Delegated Testing — bucket rules + latest-comment order extraction."""
from app.delegated_buckets import (SECTIONS, STAGES, blocked_stage,
                                   bucket_counts, bucket_issues, bucket_key,
                                   overview_counts, overview_team_stage,
                                   staged_counts, unexpected_statuses)
from app.jira_importer import extract_latest_comment_orders

ME = "haase"


def _issue(status, assignee="Tester, Tom"):
    return {"jira_status": status, "jira_assignee": assignee}


def test_status_mapping():
    assert bucket_key(_issue("Blocked")) == "blocked"
    assert bucket_key(_issue("Open")) == "open"
    # Reopened is not started again — same bucket as Open [USER 2026-09-01]
    assert bucket_key(_issue("Reopened")) == "open"
    assert bucket_key(_issue("  REOPENED ")) == "open"
    assert bucket_key(_issue("Accepted")) == "accepted"
    assert bucket_key(_issue("In Progress")) == "marina"
    assert bucket_key(_issue("In Verification")) == "settlement"
    assert bucket_key(_issue("In Validation")) == "gbs"
    assert bucket_key(_issue("In Review")) == "sales"
    assert bucket_key(_issue("Resolved")) == "done"
    assert bucket_key(_issue("Closed")) == "done"
    assert bucket_key(_issue("Done")) == "done"


def test_matching_is_case_insensitive_and_tolerates_whitespace():
    assert bucket_key(_issue("  in verification  ")) == "settlement"
    assert bucket_key(_issue("BLOCKED")) == "blocked"


def test_blocked_wins_even_when_assigned_to_marina():
    assert bucket_key(_issue("Blocked", "Haase, Marina")) == "blocked"


def test_unknown_or_missing_status_lands_in_unexpected():
    assert bucket_key(_issue("Ready for Verification")) == "unexpected"
    assert bucket_key(_issue(None)) == "unexpected"
    assert bucket_key(_issue("")) == "unexpected"


def test_assignee_no_longer_decides_a_bucket():
    """[USER 2026-08-31] the testing team's own work carries its own status
    'Accepted' now, so 'In Progress' always means the first check with
    Marina — the sections stay, they are fed by different statuses."""
    assert bucket_key(_issue("In Progress", "Tester, Tom")) == "marina"
    assert bucket_key(_issue("In Progress", "Haase, Marina [External]")) == "marina"
    assert bucket_key(_issue("Accepted", "Haase, Marina")) == "accepted"


def test_bucket_issues_keeps_order_and_covers_all_sections():
    issues = [_issue("Open"), _issue("Blocked"), _issue("In Review")]
    sections = bucket_issues(issues)
    assert [key for key, _, _, _ in sections] == [key for key, _, _ in SECTIONS]
    assert sections[0][0] == "blocked" and len(sections[0][3]) == 1
    counts = dict((k, n) for k, _, n in bucket_counts(issues))
    assert counts == {"blocked": 1, "open": 1, "sales": 1, "accepted": 0,
                      "marina": 0, "settlement": 0, "gbs": 0, "done": 0,
                      "unexpected": 0, "backlog": 0}


def test_backlog_flag_wins_over_every_status():
    parked = {**_issue("Blocked"), "backlog": True}
    assert bucket_key(parked) == "backlog"
    assert bucket_key({**_issue("In Review"), "backlog": True}) == "backlog"
    assert bucket_key(_issue("Blocked")) == "blocked"  # unflagged unchanged


# ---- Management Summary staging (build plan step 10) ----------------------

def test_staged_counts_groups_buckets_into_three_stages():
    issues = [_issue("Blocked"), _issue("Open"), _issue("Accepted"),
             _issue("In Progress"),
             _issue("In Verification"), _issue("In Validation"),
             _issue("In Review"), _issue("Resolved"), _issue("Ready for Verification")]
    stages, unexpected = staged_counts(issues)
    assert [key for key, _l, _t, _r in stages] == [key for key, _l, _b in STAGES]
    blocked = stages[0]
    assert blocked[0] == "blocked" and blocked[2] == 1
    pre = stages[1]
    # open + accepted + marina — Accepted sits BEFORE the gatekeeper check and
    # so does not count toward the weekly goal [USER 2026-08-31]
    assert pre[0] == "pre_gatekeeper" and pre[2] == 3
    post = stages[2]
    assert post[0] == "post_gatekeeper" and post[2] == 4  # settle+gbs+sales+done
    assert unexpected == ("unexpected", "Unexpected status", 1)


def test_staged_counts_all_zero_when_no_issues():
    stages, unexpected = staged_counts([])
    assert all(total == 0 for _k, _l, total, _rows in stages)
    assert unexpected[2] == 0


# ---- latest-comment order extraction (acceptance criteria ignored) ---------

def test_latest_comment_orders_takes_newest_comment_with_orders():
    comments = [
        {"created": "1", "body": "Order Number - TBY_SS_ADE0001111"},
        {"created": "2", "body": "Return Order: 6000084252"},
        {"created": "3", "body": "thanks, retesting now"},   # no orders
    ]
    result = extract_latest_comment_orders(comments)
    assert result["source"] == "latest comment"
    assert result["orders"] == ["Return Order: 6000084252"]


def test_latest_comment_orders_finds_bare_tokens():
    comments = [{"created": "1", "body": "new run: TBY_SS_ADE0006955 done"}]
    assert extract_latest_comment_orders(comments)["orders"] == ["TBY_SS_ADE0006955"]


def test_latest_comment_orders_finds_compact_letter_digit_orders():
    """Delegated order formats [USER 2026-08-26]: three letters + digits,
    or bare numbers starting with 6000."""
    comments = [{"created": "1", "body": "<p>created ASK0342321 for retest</p>"}]
    assert extract_latest_comment_orders(comments)["orders"] == ["ASK0342321"]
    comments = [{"created": "1", "body": "order ASKR0342321 created"}]  # 4 letters
    assert extract_latest_comment_orders(comments)["orders"] == ["ASKR0342321"]
    comments = [{"created": "1", "body": "return created 6000084252 today"}]
    assert extract_latest_comment_orders(comments)["orders"] == ["6000084252"]
    # ticket keys / solman-style ids / short numbers must NOT match
    comments = [{"created": "1",
                 "body": "see S4ECOM-1492 / SM1234 / PCS0001MU01 / row 600012, no order yet"}]
    assert extract_latest_comment_orders(comments)["orders"] == []


def test_latest_comment_orders_survive_html_markup():
    """Comment bodies are stored as HTML [USER 2026-08-26: 'no orders were
    found'] — markup between label and value must not break the regexes."""
    comments = [
        {"created": "1", "body": "<p>Order Number: <b>6000084252</b></p>"},
    ]
    assert extract_latest_comment_orders(comments)["orders"] == [
        "Order Number: 6000084252"]
    # label and value split over elements + &nbsp; entity
    comments = [{"created": "1",
                 "body": "<div>Return Order:&nbsp;</div><div>TBY_SS_ADE0006955</div>"}]
    assert extract_latest_comment_orders(comments)["orders"] == [
        "Return Order: TBY_SS_ADE0006955"]


def test_latest_comment_orders_empty_when_no_comment_carries_one():
    assert extract_latest_comment_orders([]) == {"orders": [], "source": None}
    assert extract_latest_comment_orders(
        [{"created": "1", "body": "no orders here"}])["orders"] == []


# ---------------------------------------------------------------------------
# MB Status expectations (2026-08-28) - ECOM-tab Status vs the bucket

def test_mb_status_state_per_bucket():
    from app.delegated_buckets import mb_status_state
    row = lambda s: {"status": s}
    # only the four buckets carry the column
    assert mb_status_state("open", row("Passed")) == ""
    assert mb_status_state("accepted", None) == ""
    # no ECOM row -> neutral
    assert mb_status_state("gbs", None) == "none"
    # settlement: empty or Not Ready expected
    assert mb_status_state("settlement", row("")) == "ok"
    assert mb_status_state("settlement", row(None)) == "ok"
    assert mb_status_state("settlement", row("Not Ready")) == "ok"
    assert mb_status_state("settlement", row("Passed")) == "mismatch"
    # gbs: In Progress / clarification needed
    assert mb_status_state("gbs", row("In Progress")) == "ok"
    assert mb_status_state("gbs", row("Clarification needed")) == "ok"
    assert mb_status_state("gbs", row("Passed")) == "mismatch"
    # sales: Passed / conditionally passed
    assert mb_status_state("sales", row("Passed")) == "ok"
    assert mb_status_state("sales", row("Conditionally Passed")) == "ok"
    assert mb_status_state("sales", row("In Progress")) == "mismatch"
    # blocked: the two blocked wordings, dash/spacing tolerant
    assert mb_status_state("blocked", row("Blocked - returned to Sales")) == "ok"
    assert mb_status_state("blocked", row("Blocked-returned to sales")) == "ok"
    assert mb_status_state("blocked", row("Blocked DTC")) == "ok"
    assert mb_status_state("blocked", row("")) == "mismatch"
    assert mb_status_state("blocked", row("Passed")) == "mismatch"


# ---------------------------------------------------------------------------
# Delegated Testing Overview (2026-08-31) — pipeline stages + status bar

def _blocked(*teams):
    return {"jira_status": "Blocked",
            "blockers": [{"team": t} for t in teams]}


def test_overview_team_stage_rules():
    assert overview_team_stage("Sales BIZ") == "tech"
    assert overview_team_stage("sales tech") == "tech"      # any "Sales*"
    assert overview_team_stage("omni") == "tech"
    assert overview_team_stage("PDM") == "mb"       # moved from tech [USER 2026-09-01]
    assert overview_team_stage("DTC O2C") == "mb"
    assert overview_team_stage("MB BIZ") == "mb"
    assert overview_team_stage("Kibana") == "bpo"
    assert overview_team_stage("ECOM  BPO") == "bpo"        # whitespace tolerant
    assert overview_team_stage("") is None
    assert overview_team_stage(None) is None
    assert overview_team_stage("Some new team") is None


def test_blocked_ticket_takes_the_earliest_stage_of_its_blocker_teams():
    assert blocked_stage(_blocked("Kibana")) == "bpo"
    assert blocked_stage(_blocked("Kibana", "Sales BIZ")) == "tech"
    assert blocked_stage(_blocked("Kibana", "PDM")) == "mb"
    assert blocked_stage(_blocked("Kibana", "DTC O2C")) == "mb"
    assert blocked_stage(_blocked("Some new team")) is None
    assert blocked_stage({"jira_status": "Blocked"}) is None   # no blockers


def test_overview_counts_pipeline_and_bar_add_up_to_the_total():
    issues = [_issue("Open"), _issue("Open"), _issue("Accepted"),
              _issue("In Progress"), _issue("In Verification"),
              _issue("In Validation"), _issue("In Review"),
              _issue("Resolved"), _issue("Closed"),
              _blocked("Sales BIZ"), _blocked("DTC O2C"), _blocked("Kibana")]
    ctx = overview_counts(issues)
    stages = {s["key"]: s for s in ctx["stages"]}
    assert stages["tech"] == {"key": "tech", "label": "TECH TEST EXECUTION",
                              "owner": "Sales Tech", "in_progress": 3,
                              "blocked": 1, "total": 4}   # 2 open + accepted
    assert stages["mb"]["in_progress"] == 3 and stages["mb"]["blocked"] == 1
    assert stages["bpo"]["in_progress"] == 1 and stages["bpo"]["blocked"] == 1
    assert stages["complete"] == {"key": "complete", "label": "COMPLETE",
                                  "owner": None, "in_progress": 2,
                                  "blocked": 0, "total": 2}
    assert ctx["total"] == 12
    assert (sum(s["total"] for s in ctx["stages"]) + ctx["blocked_unassigned"]
            + ctx["unexpected"]) == ctx["total"]
    bar = {b["key"]: b["count"] for b in ctx["bar"]}
    assert bar == {"passed": 2, "in_progress": 5, "blocked": 3, "not_started": 2}
    assert sum(bar.values()) == ctx["total"]


def test_overview_blocked_without_a_mapped_team_is_reported_not_dropped():
    ctx = overview_counts([_blocked("Some new team"), _blocked()])
    assert ctx["blocked_unassigned"] == 2
    assert all(s["blocked"] == 0 for s in ctx["stages"])
    assert ctx["total"] == 2


def test_overview_unexpected_status_joins_the_bar_only_when_present():
    ctx = overview_counts([_issue("Open")])
    assert [b["key"] for b in ctx["bar"]][-1] == "not_started"
    ctx = overview_counts([_issue("Open"), _issue("Ready for Verification")])
    assert ctx["unexpected"] == 1
    assert ctx["bar"][-1] == {"key": "unexpected", "label": "Unexpected status",
                              "count": 1}
    assert sum(b["count"] for b in ctx["bar"]) == ctx["total"] == 2


def test_overview_excludes_backlog_from_everything():
    parked = {**_issue("Open"), "backlog": True}
    ctx = overview_counts([_issue("Open"), parked])
    assert ctx["total"] == 1
    assert sum(b["count"] for b in ctx["bar"]) == 1


# ---------------------------------------------------------------------------
# Naming the odd statuses (2026-09-01 [USER]) — a report must say WHICH
# status it could not place, so nobody has to go and look it up.

def test_unexpected_statuses_names_and_counts_them():
    issues = [_issue("Open"), _issue("Ready for Verification"),
              _issue("Ready for Verification"), _issue("Waiting on vendor"),
              _issue("Resolved")]
    assert unexpected_statuses(issues) == [("Ready for Verification", 2),
                                           ("Waiting on vendor", 1)]


def test_unexpected_statuses_labels_a_missing_status():
    assert unexpected_statuses([_issue(None), _issue("")]) == [("(no status)", 2)]


def test_unexpected_statuses_empty_when_every_status_is_known():
    assert unexpected_statuses([_issue("Reopened"), _issue("In Review")]) == []


def test_unexpected_statuses_ignores_backlog_tickets():
    parked = {**_issue("Ready for Verification"), "backlog": True}
    assert unexpected_statuses([parked]) == []


def test_overview_counts_carries_the_unexpected_status_names():
    ctx = overview_counts([_issue("Open"), _issue("Ready for Verification")])
    assert ctx["unexpected"] == 1
    assert ctx["unexpected_statuses"] == [("Ready for Verification", 1)]


def test_reopened_lands_on_the_tech_card_and_not_started_bar():
    ctx = overview_counts([_issue("Reopened"), _issue("Open")])
    stages = {s["key"]: s for s in ctx["stages"]}
    assert stages["tech"]["in_progress"] == 2
    bar = {b["key"]: b["count"] for b in ctx["bar"]}
    assert bar["not_started"] == 2 and bar["in_progress"] == 0
