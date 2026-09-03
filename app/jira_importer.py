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
from html.parser import HTMLParser
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


class _ChecklistText(HTMLParser):
    """Visible text out of the checklist plugin's HTML blob [USER 2026-07-18]:
    depending on the export, the checklist markup arrives as TEXT (CDATA), so
    itertext() returns raw <div>/<span>/<svg> noise. This keeps only the
    human-readable text; svg/style/script content is dropped entirely and
    block tags become line breaks."""
    _SKIP = {"svg", "style", "script"}
    _BLOCK = {"div", "p", "li", "tr", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def _checklist_to_text(raw: str) -> str:
    """Markup-tolerant cleanup: plain text passes through unchanged."""
    if "<" in raw:
        parser = _ChecklistText()
        parser.feed(raw)
        raw = "".join(parser.parts)
    lines = [" ".join(l.split()) for l in raw.splitlines()]
    return "\n".join(l for l in lines if l)


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
            out["acceptance_criteria"] = _checklist_to_text(raw) or None
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
# comment bodies are stored as HTML — markup between label and value
# ("Order Number: <b>600…</b>", label and number in separate <p>s) broke the
# regexes, so comment text is flattened first [USER 2026-08-26: "no orders
# were found" on the delegated card, which reads ONLY comments]
import html as _html

_TAG_RE = re.compile(r"<[^>]+>")


def _comment_plain_text(body: str) -> str:
    """HTML comment body -> plain text (tags become spaces, entities decoded)."""
    return _html.unescape(_TAG_RE.sub(" ", body or ""))

# labeled entries like "Omni Order: ANT_ZL_ANLA1O8PUY" / "Return Order :
# 6000084252" / "Order Number - TBY_SS_ADE0006955"; XXXX… = placeholder
_ORDER_LABEL_RE = re.compile(
    r"((?:[A-Za-z][A-Za-z ]* )?Order(?: Number)?)\s*[:\-–]\s*([A-Za-z0-9_/-]+)")
# bare order tokens in free comment text: TBY_SS_ADE0006955 style, and —
# [USER 2026-08-26, delegated tickets] — two more shapes: compact orders
# like ASK0342321 (THREE or FOUR capitals then 6+ digits; test-case ids
# like PCS0001MU01 don't match — digit runs short / mixed with letters)
# and bare SAP numbers starting with 6000 (e.g. 6000084252)
_ORDER_TOKEN_RE = re.compile(
    r"\b(?:[A-Z]{2,5}_[A-Z]{2,5}_[A-Z0-9]{5,}|[A-Z]{3,4}\d{6,12}|6000\d{5,8})\b")


def _is_placeholder(value: str) -> bool:
    return not value or set(value.upper()) <= {"X"}


def _labeled_orders(text: str) -> list[str]:
    out = []
    for label, value in _ORDER_LABEL_RE.findall(text or ""):
        if not _is_placeholder(value):
            out.append(f"{label.strip()}: {value}")
    return out


def extract_ac_order_pairs(acceptance_criteria: str | None) -> list[dict]:
    """Labeled (type, number) pairs from the ACCEPTANCE CRITERIA only —
    feeds the order-details takeover [USER 2026-07-16]. Comments are
    deliberately excluded (unlabeled/noisy); placeholders (XXXX) skipped;
    duplicate numbers deduped keeping the first label."""
    pairs, seen = [], set()
    for label, value in _ORDER_LABEL_RE.findall(acceptance_criteria or ""):
        if _is_placeholder(value) or value.casefold() in seen:
            continue
        seen.add(value.casefold())
        pairs.append({"order_type": label.strip(), "order_number": value})
    return pairs


def extract_order_numbers(acceptance_criteria: str | None,
                          comments: list[dict]) -> dict:
    """[USER 2026-07-11] 1. ALL labeled orders from the acceptance criteria
    (skipping XXXX placeholders); 2. if none there, the LATEST comment that
    carries an order number. Returns {"orders": [...], "source": str|None}."""
    orders = _labeled_orders(acceptance_criteria or "")
    if orders:
        return {"orders": orders, "source": "acceptance criteria"}

    for c in reversed(comments or []):          # newest last in store order
        body = _comment_plain_text(c.get("body"))
        found = _labeled_orders(body)
        if not found:
            found = _ORDER_TOKEN_RE.findall(body)
        if found:
            return {"orders": found, "source": "latest comment"}
    return {"orders": [], "source": None}


def extract_latest_comment_orders(comments: list[dict]) -> dict:
    """Delegated Testing rule [USER 2026-08-26]: order numbers come from the
    COMMENTS only — always the LATEST comment that carries one; the
    acceptance criteria are deliberately ignored (testers post the current
    order numbers as comments over time). Same return shape as
    extract_order_numbers."""
    for c in reversed(comments or []):          # newest last in store order
        body = _comment_plain_text(c.get("body"))
        found = _labeled_orders(body)
        if not found:
            found = _ORDER_TOKEN_RE.findall(body)
        if found:
            return {"orders": found, "source": "latest comment"}
    return {"orders": [], "source": None}


# Issue links (2026-09-03 [USER]: "the defects and tasks show which issues
# they block in the xml"). The RSS export nests them as
#   <issuelinks><issuelinktype><name>Blocks</name>
#     <outwardlinks description="blocks"><issuelink><issuekey>KEY</issuekey>…
#     <inwardlinks description="is blocked by">…
# Only the link type named "Blocks" counts [USER: Cloners etc. ignored].
# Both directions are read so a defect's "blocks S4ECOM-1" and a story's
# "is blocked by S4DEF-1" yield the same pair — the caller pairs them up.
BLOCKS_LINK_TYPE = "blocks"


def _blocks_links(item) -> dict:
    """{"outward": [keys this issue blocks], "inward": [keys blocking it]}
    from the item's <issuelinks>; both lists deduped, order kept."""
    out: dict[str, list[str]] = {"outward": [], "inward": []}
    for lt in item.findall(".//issuelinks/issuelinktype"):
        if (lt.findtext("name") or "").strip().casefold() != BLOCKS_LINK_TYPE:
            continue
        for direction in ("outward", "inward"):
            for k in lt.findall(f"./{direction}links/issuelink/issuekey"):
                key = _text(k)
                if key and key not in out[direction]:
                    out[direction].append(key)
    return out


def blocked_pairs(issues: list[dict]) -> set[tuple[str, str]]:
    """{(blocker_key, blocked_key), …} over a whole export — the union of
    every outward "blocks" link and every inward "is blocked by" link, so
    the pair is found even when only one side of it is in the file."""
    pairs: set[tuple[str, str]] = set()
    for iss in issues:
        links = iss.get("blocks") or {}
        for k in links.get("outward", []):
            pairs.add((iss["jira_key"], k))
        for k in links.get("inward", []):
            pairs.add((k, iss["jira_key"]))
    return pairs


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
        # labels (2026-08-28 [USER], delegated filtering): RSS carries them
        # as <labels><label>x</label>…</labels>; deduped, order kept
        labels: list[str] = []
        for lab in item.findall(".//labels/label"):
            val = _text(lab)
            if val and val not in labels:
                labels.append(val)
        cf = _customfields(item)
        issues.append({
            "blocks": _blocks_links(item),
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
            "labels": labels,
        })
    return issues


def newest_xml(folder: Path) -> Path | None:
    """The newest .xml in the folder (by modification time), None if empty."""
    candidates = sorted(Path(folder).glob("*.xml"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _blocker_type_for(jira_type: str | None) -> str | None:
    """Which blocker type a NON-STORY export issue auto-registers as
    [USER 2026-08-27: "why cant i see all the defects I uploaded in the
    list of blockers?"] — Defect/Bug → defect, Task → task; stories and
    anything else (Epic, …) return None (not auto-registered; the board's
    🛈 hint shows those)."""
    t = (jira_type or "").strip().lower()
    if not t or "story" in t:
        return None
    if "defect" in t or "bug" in t:
        return "defect"
    if "task" in t:
        return "task"
    return None


def run_delegated_import(cfg: dict, xml_path: Path) -> dict:
    """Delegated Testing import (2026-08-26) — the card has its OWN Jira
    export, picked as a file in the browser and saved by the upload route;
    this parses that file. Unlike the unified import there is no filtering:
    the export itself defines the scope, so EVERY ticket in it is accepted
    and tagged seen_in_delegated (shared-store rules apply — status,
    assignee, acceptance criteria refresh; comments replaced wholesale).

    AUTO-REGISTER BLOCKERS (2026-08-27): every Defect/Bug/Task-type issue
    in the export becomes a blocker row automatically (name = summary,
    solman id from the summary prefix) unless its key is already
    registered — the export carries those issues BECAUSE they block
    testing, so they must show on the Blockers page without hand-adding
    [USER]. One normal upload therefore also backfills defects uploaded
    before this existed."""
    result: dict = {"ok": False, "error": None, "xml_path": str(xml_path),
                    "parsed": 0, "inserted": 0, "updated": 0, "comments": 0,
                    "blockers_registered": 0,
                    # "Blocks" links (2026-09-03): new links created from the
                    # export, pairs skipped (target not a story), and the
                    # links the export did NOT confirm ("blocker → ticket")
                    "links_from_jira": 0, "links_skipped": 0,
                    "links_not_in_jira": []}
    try:
        issues = parse_jira_xml(xml_path)
    except ET.ParseError as exc:
        result["error"] = f"XML parse error: {exc}"
        return result
    result["parsed"] = len(issues)
    if not issues:
        result["error"] = "no Jira tickets in that file — is it a Jira XML export?"
        return result

    from app import database
    from app.db import blockers as db_blockers
    db_path = Path(cfg["database_path"])
    db_jira.init_schema(db_path)
    db_blockers.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        counts = db_jira.upsert_jira_issues(conn, issues, seen_in="delegated")
        registered_keys = db_blockers.list_blocker_jira_keys(conn)
        for iss in issues:
            btype = _blocker_type_for(iss.get("type"))
            if btype and iss["jira_key"] not in registered_keys:
                db_blockers.create_blocker(
                    conn, btype, iss.get("summary") or iss["jira_key"],
                    iss["jira_key"], solman_id=iss.get("solman_id"))
                result["blockers_registered"] += 1
        _attach_from_blocks_links(conn, issues, result)
    finally:
        conn.close()
    result.update(counts)
    result["ok"] = True
    return result


def _attach_from_blocks_links(conn, issues: list[dict], result: dict) -> None:
    """AUTO-ATTACH from the export's "Blocks" links (2026-09-03 [USER]:
    "automatically adds the defects to the blocked test cases in the column
    Blockers"). For every (blocker, ticket) pair in the file whose blocker
    is registered and whose ticket is a user story: attach (source 'jira';
    an existing link — manual or jira — is left untouched). Then the
    COMPARISON [USER: "if a blocker is already there that is NOT referenced
    in the xml - it should not overwrite - but comment on it"]: a link whose
    blocker IS in this export but whose pair the export does not carry gets
    the `jira_missing_since` stamp (set once); a pair the export confirms
    has its stamp cleared. Nothing is ever deleted. Blockers absent from
    the export cannot be judged and are left alone."""
    from datetime import datetime
    from app.db import blockers as db_blockers
    from app.db import delegated as db_delegated

    pairs = blocked_pairs(issues)
    export_keys = {iss["jira_key"] for iss in issues}
    by_blocker_key = {b["jira_key"]: b for b in db_blockers.list_blockers(conn)
                      if b.get("jira_key")}
    existing = {(l["blocker_id"], l["jira_key"]) for l in db_blockers.list_blocker_links(conn)}
    now = datetime.now().isoformat(timespec="seconds")

    def _is_story(key: str) -> bool:
        iss = db_jira.get_jira_issue(conn, key)
        return iss is not None and db_delegated.is_story_type(iss.get("type"))

    for blocker_key, ticket_key in sorted(pairs):
        blocker = by_blocker_key.get(blocker_key)
        if blocker is None:
            continue                      # not a registered blocker (e.g. an epic)
        if not _is_story(ticket_key):
            result["links_skipped"] += 1   # blocks a non-story / unknown ticket
            continue
        if (blocker["blocker_id"], ticket_key) not in existing:
            db_blockers.link_blocker(conn, blocker["blocker_id"], ticket_key,
                                     source="jira")
            result["links_from_jira"] += 1

    for link in db_blockers.list_blocker_links(conn):
        bkey = link.get("blocker_key")
        if not bkey or bkey not in export_keys:
            continue                      # blocker not in this file: no verdict
        if (bkey, link["jira_key"]) in pairs:
            db_blockers.set_link_jira_missing(conn, link["blocker_id"],
                                              link["jira_key"], None)
        else:
            db_blockers.set_link_jira_missing(conn, link["blocker_id"],
                                              link["jira_key"], now)
            result["links_not_in_jira"].append(f"{bkey} → {link['jira_key']}")


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
