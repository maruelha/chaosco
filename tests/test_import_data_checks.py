"""Import-time data checks [USER 2026-08-05].

"conditionally passed" without a reason in "Reason for pass with
reservation" must surface on the IMPORT REPORT — for Retail, ECOM AND the
two manual verticals (same rule registry as the boards' ⚠ buttons).
Findings never block the import; skiplogged rows are excluded (they have
their own report line).
"""
from app.importer import data_check_rows
from app.row_validations import RULES


def _row(vertical, status, reason, skip=""):
    row = {"status": status, "reason_for_pass_with_reservation": reason,
           "test_case_id": "TC1", "country": "Germany",
           "excel_row": 7, "_skip_reason": skip}
    if vertical in ("ecom", "manual_ecom"):
        row["jira_id"] = "S4ECOM-1"
    return row


def test_rule_covers_all_four_verticals():
    rule = next(r for r in RULES if r.key == "reason_for_conditional_pass")
    assert set(rule.verticals) == {"retail", "ecom", "manual_retail", "manual_ecom"}


def test_conditionally_passed_without_reason_is_flagged():
    for vertical in ("retail", "ecom", "manual_retail", "manual_ecom"):
        checks = data_check_rows(vertical, [
            _row(vertical, "conditionally passed", ""),        # -> finding
            _row(vertical, "Conditionally Passed", "  "),      # case + blank -> finding
            _row(vertical, "conditionally passed", "waiting for fix DEF-1"),
            _row(vertical, "Passed", ""),
        ])
        assert len(checks) == 2, vertical
        assert checks[0]["excel_row"] == 7
        assert "Reason for pass with" in checks[0]["problems"][0]


def test_labels_and_skiplogged_rows():
    checks = data_check_rows("retail", [_row("retail", "conditionally passed", "")])
    assert checks[0]["label"] == "TC1 / Germany"
    checks = data_check_rows("ecom", [_row("ecom", "conditionally passed", "")])
    assert checks[0]["label"] == "S4ECOM-1 / TC1 / Germany"
    # a row already going to the skiplog is not double-reported
    checks = data_check_rows("retail", [
        _row("retail", "conditionally passed", "", skip="incomplete key")])
    assert checks == []
