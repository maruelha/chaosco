"""The docs/claude/ structure is part of the architecture [USER 2026-08-30].

One file per mini app in docs/claude/, one per shared component in
docs/claude/components/, indexed by mini-apps.md. These tests keep that true
instead of trusting everyone to remember:

- every file follows the template (H1, Type line, Purpose, Related)
- the tables / modules / templates / tests a file's header block names really
  exist — a renamed module must not leave a doc pointing at nothing
- every file is listed in the map, and every file the map lists exists
- the two combined docs that were split on 2026-08-30 do not come back
"""
import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent.parent / "docs" / "claude"
ROOT = Path(__file__).resolve().parent.parent
META = {"_template.md", "mini-apps.md"}


def _doc_files():
    return sorted(p for p in DOCS.rglob("*.md") if p.name not in META)


def _known_tables() -> set[str]:
    """Every table any storage module creates (no DB needed)."""
    tables: set[str] = set()
    sources = list((ROOT / "app" / "db").glob("*.py")) + [ROOT / "app" / "db_retail_tracker.py"]
    for src in sources:
        text = src.read_text(encoding="utf-8")
        tables |= set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", text))
    # manual_tests.py builds its two tables from a format string ({vertical}),
    # so the regex above cannot see them
    tables |= {"manual_retail", "manual_ecom"}
    return tables


@pytest.mark.parametrize("path", _doc_files(), ids=lambda p: p.name)
def test_file_follows_the_template(path: Path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# "), "must open with an H1 title"
    for needed in ("**Type:**", "## Purpose", "## Related"):
        assert needed in text, f"missing {needed}"


@pytest.mark.parametrize("path", _doc_files(), ids=lambda p: p.name)
def test_header_block_points_at_things_that_exist(path: Path):
    """Storage tables and code files named above '## Purpose' must be real."""
    head = path.read_text(encoding="utf-8").split("## Purpose")[0]
    tables = _known_tables()
    for table in re.findall(r"→ `([a-z][a-z0-9_]*)`", head):
        assert table in tables, f"unknown table `{table}`"
    for ref in re.findall(r"`(app/[\w/]+\.py|tests/test_\w+\.py|[\w_]+\.html)`", head):
        candidates = [ROOT / ref, ROOT / "app" / "templates" / ref, ROOT / "app" / "static" / ref]
        assert any(c.exists() for c in candidates), f"file not found: {ref}"


def test_map_and_folder_agree():
    map_text = (DOCS / "mini-apps.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"`(components/[\w-]+\.md|[\w-]+\.md)`", map_text))
    on_disk = {p.relative_to(DOCS).as_posix() for p in _doc_files()}
    missing_from_map = on_disk - listed
    assert not missing_from_map, f"not listed in mini-apps.md: {sorted(missing_from_map)}"
    listed_docs = {n for n in listed if (DOCS / n).suffix == ".md"}
    dead_rows = {n for n in listed_docs
                 if not (DOCS / n).exists() and n not in {"CLAUDE.md", "coordination.md",
                                                          "verticals.md"}}
    assert not dead_rows, f"map points at missing files: {sorted(dead_rows)}"


def test_wiki_links_resolve():
    stems = {p.stem for p in DOCS.rglob("*.md")}
    dangling = {}
    for path in _doc_files():
        for link in re.findall(r"\[\[([\w-]+)\]\]", path.read_text(encoding="utf-8")):
            if link not in stems:
                dangling.setdefault(link, []).append(path.name)
    assert not dangling, f"dangling [[links]]: {dangling}"


def test_the_split_docs_do_not_come_back():
    """coordination.md (20 apps) and verticals.md (8 apps) were split on
    2026-08-30 — one file per mini app is the rule now."""
    for gone in ("coordination.md", "verticals.md"):
        assert not (DOCS / gone).exists(), f"{gone} is back — split it again"
