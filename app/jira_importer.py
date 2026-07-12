"""Jira XML importer — newest .xml per configured folder into the shared store.

Source rule [USER 2026-07-06]: two configured FOLDERS
(`jira_gatekeeper_folder` = "assigned to Marina" exports,
`jira_ecom_folder` = ECOM open-issues exports) — the importer always takes
the NEWEST .xml in the folder; filenames don't matter.

Parser notes (verified against the real export, Jira DC 10.3, planning chat
2026-07-05):
- Jira RSS format: rss/channel/item, one item per issue.
- Bare `&` can appear un-escaped in summaries/descriptions — a pre-pass
  escapes any `&` that does not start a valid entity, otherwise
  ElementTree refuses the file.
- description / comment bodies are HTML (stored as-is, rendered read-only).
- comments carry only JIRAUSER keys as authors — authors are dropped.
- solman_id convention: the summary up to the first "_" (NULL when the
  summary has no underscore).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.db import jira as db_jira

# any & not followed by a valid entity (&amp; &#123; &#x1f;) gets escaped
_BARE_AMP = re.compile(r"&(?!(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);)")


def _escape_bare_ampersands(text: str) -> str:
    return _BARE_AMP.sub("&amp;", text)


def _text(elem) -> str:
    """All inner text of an element (tolerates stray nested markup)."""
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def _split_solman_id(summary: str) -> str | None:
    """'SM1234_Blind Return' -> 'SM1234'; no underscore -> None."""
    if "_" not in summary:
        return None
    head = summary.split("_", 1)[0].strip()
    return head or None


def _customfields(item) -> dict:
    """{'epic': ..., 'markets': ..., 'acceptance_criteria': ...} from the
    customfields block, matched by field NAME (ids differ per Jira instance;
    names are stable enough). Acceptance Criteria is a checklist-plugin
    field (okapya) whose content sits as HTML inside <customfieldvalues> —
    itertext catches it regardless of nesting."""
    out = {"epic": None, "markets": None, "acceptance_criteria": None}
    for cf in item.findall(".//customfield"):
        name = (cf.findtext("customfieldname") or "").strip().lower()
        if name == "acceptance criteria":
            vals = cf.find("customfieldvalues")
            raw = "".join(vals.itertext()) if vals is not None else ""
            lines = [" ".join(l.split()) for l in raw.splitlines()]
            text = "\n".join(l for l in lines if l)
            out["acceptance_criteria"] = text or None
            continue
        values = [_text(v) for v in cf.findall(".//customfieldvalue")]
        values = [v for v in values if v]
        if not values:
            continue
        if name == "epic link" or (name.startswith("epic") and not out["epic"]):
            out["epic"] = values[0]
        elif "market" in name and not out["markets"]:
            out["markets"] = ", ".join(values)
    return out


# --- order-number extraction (report on the gatekeeper page) ---------------
# labeled entries like "Omni Order: ANT_ZL_ANLA1O8PUY" / "Return Order :
# 6000084252" / "Order Number - TBY_SS_ADE0006955"; XXXX… = placeholder
_ORDER_LABEL_RE = re.compile(
    r"((?:[A-Za-z][A-Za-z ]* )?Order(?: Number)?)\s*[:\-–]\s*([A-Za-z0-9_/-]+)")
# bare order tokens in free comment text, e.g. TBY_SS_ADE0006955
_ORDER_TOKEN_RE = re.compile(r"\b[A-Z]{2,5}_[A-Z]{2,5}_[A-Z0-9]{5,}\b")


def _is_placeholder(value: str) -> bool:
    return not value or set(value.upper()) <= {"X"}


def _labeled_orders(text: str) -> list[str]:
    out = []
    for label, value in _ORDER_LABEL_RE.findall(text or ""):
        if not _is_placeholder(value):
            out.append(f"{label.strip()}: {value}")
    return out


def extract_order_numbers(acceptance_criteria: str | None,
                          comments: list[dict]) -> dict:
    """[USER 2026-07-11] 1. ALL labeled orders from the acceptance criteria
    (skipping XXXX placeholders); 2. if none there, the LATEST comment that
    carries an order number. Returns {"orders": [...], "source": str|None}."""
    orders = _labeled_orders(acceptance_criteria or "")
    if orders:
        return {"orders": orders, "source": "acceptance criteria"}

    for c in reversed(comments or []):          # newest last in store order
        body = c.get("body") or ""
        found = _labeled_orders(body)
        if not found:
            found = _ORDER_TOKEN_RE.findall(body)
        if found:
            return {"orders": found, "source": "latest comment"}
    return {"orders": [], "source": None}


def parse_jira_xml(path: Path) -> list[dict]:
    """Parse a Jira RSS XML export into issue dicts (incl. comments)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(_escape_bare_ampersands(text))

    issues: list[dict] = []
    for item in root.iter("item"):
        key = (item.findtext("key") or "").strip()
        if not key:
            continue
        summary = (item.findtext("summary") or "").strip()
        assignee_el = item.find("assignee")
        assignee = _text(assignee_el) or (
            assignee_el.get("username", "") if assignee_el is not None else "")
        reporter_el = item.find("reporter")
        reporter = _text(reporter_el) or (
            reporter_el.get("username", "") if reporter_el is not None else "")
        comments = [{
            "created": (c.get("created") or "").strip() or None,
            "body": _text(c),
        } for c in item.findall(".//comments/comment")]
        cf = _customfields(item)
        issues.append({
            "jira_key": key,
            "solman_id": _split_solman_id(summary),
            "summary": summary,
            "epic": cf["epic"],
            "markets": cf["markets"],
            "acceptance_criteria": cf["acceptance_criteria"],
            "jira_status": (item.findtext("status") or "").strip() or None,
            "jira_assignee": assignee.strip() or None,
            "reporter": reporter.strip() or None,
            "type": (item.findtext("type") or "").strip() or None,
            "priority": (item.findtext("priority") or "").strip() or None,
            "description": _text(item.find("description")) or None,
            "link": (item.findtext("link") or "").strip() or None,
            "created": (item.findtext("created") or "").strip() or None,
            "updated": (item.findtext("updated") or "").strip() or None,
            "comments": comments,
        })
    return issues


def newest_xml(folder: Path) -> Path | None:
    """The newest .xml in the folder (by modification time), None if empty."""
    candidates = sorted(Path(folder).glob("*.xml"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def run_jira_import(cfg: dict) -> dict:
    """ONE unified import [USER 2026-07-12] — newest .xml in `jira_folder`
    (fallback: `jira_gatekeeper_folder`); the Jira search can be as
    broad/lazy as convenient (e.g. `assignee WAS currentUser()` + the board
    epics). Per ticket:

    - already in the store           -> REFRESH (tracked forever — keeps
      "Back with Sales" current even when no longer assigned to me)
    - new + assigned to me           -> enter (the gatekeeper sense check;
      `jira_gatekeeper_assignee` in settings, substring match)
    - new + key on the ECOM board    -> enter (board rows that never passed
      gatekeeping still get their Jira data)
    - anything else                  -> ignored (counted)

    Accepted tickets get source tags refreshed: assigned-to-me -> gatekeeper,
    on-board -> ecom (set, never cleared).
    """
    result: dict = {"ok": False, "error": None,
                    "xml_path": None, "parsed": 0,
                    "refreshed": 0, "new_gatekeeper": 0, "new_board": 0,
                    "ignored": 0,
                    "inserted": 0, "updated": 0, "comments": 0}
    folder = Path(cfg.get("jira_folder") or cfg.get("jira_gatekeeper_folder", ""))
    if not folder.is_dir():
        result["error"] = f"folder not found: {folder} (jira_folder in settings)"
        return result
    xml_path = newest_xml(folder)
    if xml_path is None:
        result["error"] = f"no .xml file in {folder}"
        return result
    result["xml_path"] = str(xml_path)

    try:
        issues = parse_jira_xml(xml_path)
    except ET.ParseError as exc:
        result["error"] = f"XML parse error: {exc}"
        return result
    result["parsed"] = len(issues)

    from app import database
    from app.db import ecom as db_ecom
    db_path = Path(cfg["database_path"])
    db_jira.init_schema(db_path)
    db_ecom.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        in_store = {k for (k,) in conn.execute("SELECT jira_key FROM jira_issues")}
        board = {k.strip().lower() for (k,) in conn.execute(
            "SELECT jira_id FROM ecom WHERE jira_id IS NOT NULL")}
        me = (cfg.get("jira_gatekeeper_assignee") or "").strip().lower()

        def _mine(iss) -> bool:
            return bool(me) and me in (iss.get("jira_assignee") or "").lower()

        def _on_board(iss) -> bool:
            return iss["jira_key"].strip().lower() in board

        accepted = []
        for iss in issues:
            if iss["jira_key"] in in_store:
                accepted.append(iss)
                result["refreshed"] += 1
            elif _mine(iss):
                accepted.append(iss)
                result["new_gatekeeper"] += 1
            elif _on_board(iss):
                accepted.append(iss)
                result["new_board"] += 1
            else:
                result["ignored"] += 1

        counts = db_jira.upsert_jira_issues(conn, accepted)
        # source tags reflect CURRENT membership (set, never cleared)
        with conn:
            for iss in accepted:
                if _mine(iss):
                    conn.execute("UPDATE jira_issues SET seen_in_gatekeeper=1"
                                 " WHERE jira_key=?", (iss["jira_key"],))
                if _on_board(iss):
                    conn.execute("UPDATE jira_issues SET seen_in_ecom=1"
                                 " WHERE jira_key=?", (iss["jira_key"],))
    finally:
        conn.close()
    result.update(counts)
    result["ok"] = True
    return result
