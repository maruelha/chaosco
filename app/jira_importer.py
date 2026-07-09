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
    """{'epic': ..., 'markets': ...} from the customfields block, matched by
    field NAME (ids differ per Jira instance; names are stable enough)."""
    out = {"epic": None, "markets": None}
    for cf in item.findall(".//customfield"):
        name = (cf.findtext("customfieldname") or "").strip().lower()
        values = [_text(v) for v in cf.findall(".//customfieldvalue")]
        values = [v for v in values if v]
        if not values:
            continue
        if "epic" in name and not out["epic"]:
            out["epic"] = values[0]
        elif "market" in name and not out["markets"]:
            out["markets"] = ", ".join(values)
    return out


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
            "jira_status": (item.findtext("status") or "").strip() or None,
            "jira_assignee": assignee.strip() or None,
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


_SOURCES = {"gatekeeper": "jira_gatekeeper_folder", "ecom": "jira_ecom_folder"}


def run_jira_import(cfg: dict, source: str) -> dict:
    """Parse the newest XML of one source folder + upsert into the shared
    store. Returns a result dict for the import screen (step 3)."""
    result: dict = {"ok": False, "error": None, "source": source,
                    "xml_path": None, "parsed": 0,
                    "inserted": 0, "updated": 0, "comments": 0}
    folder_key = _SOURCES.get(source)
    if folder_key is None:
        result["error"] = f"unknown source {source!r} (use 'gatekeeper' or 'ecom')"
        return result
    folder = Path(cfg.get(folder_key, ""))
    if not folder.is_dir():
        result["error"] = f"folder not found: {folder} ({folder_key} in settings)"
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
    db_path = Path(cfg["database_path"])
    db_jira.init_schema(db_path)
    conn = database.get_connection(db_path)
    try:
        counts = db_jira.upsert_jira_issues(conn, issues)
    finally:
        conn.close()
    result.update(counts)
    result["ok"] = True
    return result
