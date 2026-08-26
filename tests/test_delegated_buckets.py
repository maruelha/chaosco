"""Delegated Testing — bucket rules + latest-comment order extraction."""
from app.delegated_buckets import SECTIONS, bucket_counts, bucket_issues, bucket_key
from app.jira_importer import extract_latest_comment_orders

ME = "haase"


def _issue(status, assignee="Tester, Tom"):
    return {"jira_status": status, "jira_assignee": assignee}


def test_status_mapping():
    assert bucket_key(_issue("Blocked"), ME) == "blocked"
    assert bucket_key(_issue("Open"), ME) == "open"
    assert bucket_key(_issue("In Progress"), ME) == "team"
    assert bucket_key(_issue("In Progress", "Haase, Marina [External]"), ME) == "marina"
    assert bucket_key(_issue("In Verification"), ME) == "settlement"
    assert bucket_key(_issue("In Validation"), ME) == "gbs"
    assert bucket_key(_issue("In Review"), ME) == "sales"
    assert bucket_key(_issue("Resolved"), ME) == "done"
    assert bucket_key(_issue("Closed"), ME) == "done"
    assert bucket_key(_issue("Done"), ME) == "done"


def test_matching_is_case_insensitive_and_tolerates_whitespace():
    assert bucket_key(_issue("  in verification  "), ME) == "settlement"
    assert bucket_key(_issue("BLOCKED"), ME) == "blocked"


def test_blocked_wins_even_when_assigned_to_marina():
    assert bucket_key(_issue("Blocked", "Haase, Marina"), ME) == "blocked"


def test_unknown_or_missing_status_lands_in_unexpected():
    assert bucket_key(_issue("Ready for Verification"), ME) == "unexpected"
    assert bucket_key(_issue(None), ME) == "unexpected"
    assert bucket_key(_issue(""), ME) == "unexpected"


def test_no_assignee_config_never_buckets_to_marina():
    assert bucket_key(_issue("In Progress", "Haase, Marina"), "") == "team"


def test_bucket_issues_keeps_order_and_covers_all_sections():
    issues = [_issue("Open"), _issue("Blocked"), _issue("In Review")]
    sections = bucket_issues(issues, ME)
    assert [key for key, _, _, _ in sections] == [key for key, _, _ in SECTIONS]
    assert sections[0][0] == "blocked" and len(sections[0][3]) == 1
    counts = dict((k, n) for k, _, n in bucket_counts(issues, ME))
    assert counts == {"blocked": 1, "open": 1, "sales": 1, "team": 0,
                      "marina": 0, "settlement": 0, "gbs": 0, "done": 0,
                      "unexpected": 0}


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
