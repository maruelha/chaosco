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


def test_docs_map_lists_every_doc():
    """docs/docs_map.html is GENERATED (tools/gen_docs_map.py) — the docs
    index [USER 2026-09-01]. Adding or removing any doc without regenerating
    fails here. Only NAMES are compared; last-touched dates go stale between
    runs on purpose."""
    docs_dir = ROOT / "docs"
    map_html = (docs_dir / "docs_map.html").read_text(encoding="utf-8")
    listed = set(re.findall(r'href="([^"]+)"', map_html))

    expected = {p.name for p in docs_dir.iterdir()
                if p.is_file() and p.suffix in (".md", ".html")}
    expected |= {p.relative_to(docs_dir).as_posix()
                 for p in (docs_dir / "claude").rglob("*.md")}
    missing = expected - listed
    assert not missing, (
        f"docs missing from docs_map.html: {sorted(missing)} — "
        "rerun tools/gen_docs_map.py (add a registry entry if it asks)")

    for href in listed:
        assert (docs_dir / href).exists(), (
            f"docs_map.html links to {href} which does not exist — "
            "rerun tools/gen_docs_map.py")


# ---------------------------------------------------------------------------
# Facts coverage [USER 2026-09-01, docs cleanup step 2]: hand-written docs
# must not fall behind the code on FACTS. Each rule carries its exceptions
# explicitly, with a reason — a deliberate "needs no doc" is a visible
# one-liner here, never a silent omission.
# ---------------------------------------------------------------------------

_SQL_KEYWORDS = {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"}

# legacy tables that exist only for the migration record — no living doc
# claims them and none should
_LEGACY_TABLES = {
    "defect_notes",  # pre-unified-notes table; see scripts/migrate_notes.py
}

# GET routes without placeholders that are data endpoints, not screens
_NON_SCREEN_ROUTES: dict[str, str] = {
    # path: reason   (paths ending in .json are exempt automatically)
}


def _storage_sources():
    return list((ROOT / "app" / "db").glob("*.py")) + [ROOT / "app" / "db_retail_tracker.py"]


def _columns_of(body: str) -> set[str]:
    """First word of each comma-separated definition, comments stripped,
    constraint keywords filtered."""
    body = re.sub(r"--[^\n]*", "", body)
    cols, depth, cur, parts = set(), 0, [], []
    for ch in body:
        if ch == "(":
            depth += 1
        if ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    for part in parts:
        words = part.strip().split()
        if not words:
            continue
        name = words[0].strip('"').split("(")[0]
        if not name or name.upper() in _SQL_KEYWORDS or name.startswith("{"):
            continue
        cols.add(name)
    return cols


def _created_tables_with_columns() -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for src in _storage_sources():
        text = src.read_text(encoding="utf-8")
        for m in re.finditer(
            r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\)\s*(?:\"\"\"|'''|;)", text, re.S
        ):
            tables.setdefault(m.group(1), set()).update(_columns_of(m.group(2)))
        for m in re.finditer(r"ALTER TABLE (\w+) ADD COLUMN (\w+)", text):
            tables.setdefault(m.group(1), set()).add(m.group(2))
    # manual_tests.py builds its pair from a format string
    mt = (ROOT / "app" / "db" / "manual_tests.py").read_text(encoding="utf-8")
    fm = re.search(r"CREATE TABLE IF NOT EXISTS \{\w+\}\s*\((.*?)\)\s*(?:\"\"\"|''')", mt, re.S)
    if fm:
        for t in ("manual_retail", "manual_ecom"):
            tables.setdefault(t, set()).update(_columns_of(fm.group(1)))
    return tables


def test_every_table_and_column_reaches_the_schema_page():
    """database_schema.html is the LEDGER: every table gets a card, every
    column (CREATE or ALTER) appears on its table's card. This is the test
    that would have caught email_lists.subject/body going undocumented."""
    schema = (ROOT / "docs" / "database_schema.html").read_text(encoding="utf-8")
    cards: dict[str, str] = {}
    for m in re.finditer(r'<div class="table-card" id="([^"]+)"', schema):
        nxt = schema.find('<div class="table-card"', m.end())
        cards[m.group(1)] = schema[m.end(): nxt if nxt != -1 else len(schema)]

    problems = []
    for table, cols in _created_tables_with_columns().items():
        if table not in cards:
            problems.append(f"table `{table}` has no card on database_schema.html")
            continue
        for col in sorted(cols):
            if not re.search(r"\b" + re.escape(col) + r"\b", cards[table]):
                problems.append(f"column `{table}.{col}` missing from its card")
    assert not problems, "\n".join(problems)


def _docs_corpus() -> str:
    import html as _html

    parts = [
        (ROOT / "docs" / "screens.html").read_text(encoding="utf-8"),
        (ROOT / "docs" / "dashboard_cards.html").read_text(encoding="utf-8"),
    ]
    parts += [p.read_text(encoding="utf-8") for p in DOCS.rglob("*.md")]
    return _html.unescape("\n".join(parts))


def test_every_screen_and_namespace_reaches_the_docs():
    """Two altitudes, deliberately not one per route: every user-facing GET
    page (no placeholders) must appear in the docs literally, and every
    top-level URL namespace must appear somewhere — but the Nth per-row CRUD
    sub-route is prose ("add / edit / delete"), never a doc bullet each."""
    from app.web import app

    corpus = _docs_corpus()
    problems = []
    namespaces = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = rule.rule
        seg = path.strip("/").split("/")[0]
        if seg and "<" not in seg:
            namespaces.add("/" + seg)
        if "GET" in (rule.methods or set()) and "<" not in path:
            if path.endswith(".json") or path in _NON_SCREEN_ROUTES:
                continue
            if path not in corpus and path.rstrip("/") not in corpus:
                problems.append(
                    f"screen {path} not in screens.html / dashboard_cards.html / docs/claude"
                )
    for ns in sorted(namespaces):
        if ns not in corpus:
            problems.append(f"namespace {ns} appears in no doc at all")
    assert not problems, "\n".join(problems)


def _card_titles(text: str) -> set[str]:
    import html as _html

    out = set()
    for m in re.finditer(r"<h2>(.*?)</h2>", text, re.S):
        t = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", "", m.group(1), flags=re.S)
        t = re.sub(r"<[^>]+>.*?</[^>]+>|<[^>]+>", "", t, flags=re.S)
        t = _html.unescape(t)
        t = "".join(ch for ch in t if ch.isalnum() or ch.isspace() or ch in "&—-")
        t = " ".join(t.split()).strip()
        if t:
            out.add(t)
    return out


def test_dashboard_cards_match_the_dashboard():
    """dashboard_cards.html is the MENU: exactly the cards the dashboard
    template shows, no more, no less [USER 2026-09-01]."""
    on_dashboard = _card_titles(
        (ROOT / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    )
    in_doc = _card_titles(
        (ROOT / "docs" / "dashboard_cards.html").read_text(encoding="utf-8")
    )
    assert on_dashboard - in_doc == set(), f"cards missing from the doc: {sorted(on_dashboard - in_doc)}"
    assert in_doc - on_dashboard == set(), f"doc lists cards that are gone: {sorted(in_doc - on_dashboard)}"


def test_every_table_is_claimed_by_a_doc_header():
    """No orphan tables: every table some storage module creates is named in
    at least ONE doc's header block. (Per-doc completeness is deliberately
    NOT required — core.py and planning.py are shared schema modules.)"""
    claimed = set()
    for doc in DOCS.rglob("*.md"):
        text = doc.read_text(encoding="utf-8")
        head = text.split("## Purpose")[0] if "## Purpose" in text else text
        claimed |= set(re.findall(r"`([a-z][a-z0-9_]*)`", head))
    orphans = set(_created_tables_with_columns()) - claimed - _LEGACY_TABLES
    assert not orphans, (
        f"tables no doc header claims: {sorted(orphans)} — add each to its "
        "mini app's Storage line (or to _LEGACY_TABLES with a reason)"
    )
