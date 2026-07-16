"""Issue-message templates — pure data + assembly, no I/O (2026-07-16).

The SPECIAL TEXTS are deliberately FIXED here (not DB-editable — [USER]:
"editable might be a bit brittle"). Placeholders:
    {message}  -> the chosen message type name (message_types table)
    {orders}   -> the highlighted order number(s), comma-joined
Templates that speak of "above orders" refer to the context header, which
always leads the message: "<identifier> — orders: <all order numbers>".

Adding/changing a template = edit SPECIAL_TEXTS below (key stays stable,
it may end up in saved note headings).
"""
from __future__ import annotations

SPECIAL_TEXTS = [
    {"key": "check_tibco", "label": "Check in TIBCO",
     "text": "please check if the {message} message for the {orders} has reached tibco"},
    {"key": "gatekeeper_s4", "label": "Gatekeeper check in S4",
     "text": "please check orders."},
    {"key": "sd_check_s4", "label": "SD team to check in S4",
     "text": "please check why {message} message not created in s4 for {orders}"},
    {"key": "request_payloads", "label": "Request payloads",
     "text": "There is an issue for {message} message for the following order {orders}. "
             "Could we please have the payloads for this."},
    {"key": "inform_issue", "label": "Inform about issue",
     "text": "Just FYI there is an issue with the {message} {orders}. "
             "We are checking with DTC Tech Team and will get back with feedback."},
    {"key": "discuss_clarify", "label": "To discuss / clarify",
     "text": "there is an issue with the {message} {orders}"},
    {"key": "settlement_files", "label": "Settlement files creation",
     "text": "Could you please create settlement files for above orders"},
    {"key": "clearing_missing", "label": "Clearing not happening",
     "text": "Clearing did not happen for above orders - could you check please?"},
]


def build_message(identifier: str, all_orders: list[str], template_text: str,
                  message_type: str, highlighted: list[str],
                  tibco_api: str | None = None, iib_api: str | None = None) -> str:
    """Assemble the full message. Mirrored by the client-side preview in
    _issue_message.html — keep both in sync. No highlighted orders ->
    the full order list stands in."""
    orders = ", ".join(highlighted or all_orders) or "—"
    header = identifier
    if all_orders:
        header += " — orders: " + ", ".join(all_orders)
    body = template_text.replace("{message}", message_type).replace("{orders}", orders)
    lines = [header, "", body]
    apis = " · ".join(x for x in (f"TIBCO: {tibco_api}" if tibco_api else "",
                                  f"IIB: {iib_api}" if iib_api else "") if x)
    if apis:
        lines += ["", apis]
    return "\n".join(lines)
