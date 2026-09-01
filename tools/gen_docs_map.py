"""Generate docs/docs_map.html — the documentation index.

One row per doc: what it is FOR, when it gets updated, what enforces that,
and when it was last touched (from git). The one-line "job" texts are
hand-written HERE (this registry is their single home); the file list and
the dates are read from the filesystem and git, so they cannot drift.

Run it whenever docs are added/removed (the wrap-up skill does):

    .venv\\Scripts\\python tools\\gen_docs_map.py

`tests/test_docs_structure.py::test_docs_map_lists_every_doc` fails the
suite when a doc exists that this page does not list (or vice versa), so a
forgotten regeneration cannot be committed. Dates are only as fresh as the
last run — that is fine, the parity test deliberately ignores them.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = DOCS / "docs_map.html"

# ---------------------------------------------------------------------------
# The hand-written part: one job line per top-level doc.
# (docs/claude/ files are NOT described here — their one-liners live in
# docs/claude/mini-apps.md, and a fact is described at ONE altitude only.)
# ---------------------------------------------------------------------------

TOP_LEVEL = {
    # filename: (job, update when, enforced by)
    "docs_map.html": (
        "This index — every doc, its job, its update trigger, its enforcement",
        "docs added/removed → regenerate via <code>tools/gen_docs_map.py</code>",
        "parity test (suite fails when a doc is missing here)",
    ),
    "screens.html": (
        "The MANUAL — every screen, what it shows and does, feature by feature",
        "any screen changes",
        "screen + namespace coverage test (test_docs_structure.py)",
    ),
    "database_schema.html": (
        "The LEDGER — every table, column, constraint and relation",
        "a table or column changes",
        "table + column coverage test (test_docs_structure.py)",
    ),
    "architecture.html": (
        "The BLUEPRINT — layers, data flow, what each layer may and may not "
        "do; instance-free, so it stays flat as the app grows",
        "structural change only (new layer/pattern)",
        "flat by design; paired with CLAUDE.md's terse map",
    ),
    "dashboard_cards.html": (
        "The MENU — what each dashboard card is FOR, nothing more "
        "[USER 2026-09-01]",
        "a card is added/removed/renamed",
        "card-parity test against the dashboard template",
    ),
    "build_plan.md": (
        "The DIARY — what to build next, per module, and what was just built",
        "per task; finished sections MOVE to docs/archive/ — when something "
        "is added, something goes [USER 2026-09-01]",
        "wrap-up skill",
    ),
    "coding_guidelines.md": (
        "HOW code is written, wherever it lives — the code-review checklist. "
        "Complement of architecture.html (WHERE code lives)",
        "a review finds a recurring pattern (filled in review round 2)",
        "greppable rules become tests (review round 2)",
    ),
    "lessons_learned.md": (
        "The STORIES behind the rules — what broke technically, what it "
        "cost, what we do now (rules live in CLAUDE.md / "
        "coding_guidelines.md and are pointed at, never restated)",
        "the wrap-up skill's promote-lessons step finds one worth keeping",
        "wrap-up skill (story → rule → test)",
    ),
    "ways_of_working.md": (
        "The WHY of how Marina and Claude collaborate — lessons about the "
        "working method itself",
        "a collaboration lesson is learned",
        "wrap-up skill",
    ),
    "why_step_by_step.md": (
        "Deep dive behind the step-by-step rule in ways_of_working.md",
        "rarely",
        "stable",
    ),
    "tech_backlog.md": (
        "Known technical debt and deferred work",
        "debt is found or paid off",
        "wrap-up skill",
    ),
    "dev_tools.md": (
        "The tools/ helpers for working ON chaosco (never part of the app)",
        "a tool is added or changed",
        "rule in dev_tools.md itself",
    ),
    "teams_review_concept.md": (
        "Concept note — moves to docs/archive/ once built",
        "—",
        "archive rule",
    ),
    "windows_terminal_tabs.html": (
        "Terminal setup notes for this machine",
        "rarely",
        "stable",
    ),
}

FOLDERS = [
    (
        "claude/",
        "The MECHANIC'S NOTES, for Claude — one file per mini app, one per "
        "shared component, indexed by <code>claude/mini-apps.md</code> (the "
        "map, which holds the one-liner per app — deliberately not repeated "
        "here)",
        "the app/component it describes changes",
        "tests/test_docs_structure.py (template, header facts, map parity, "
        "links)",
    ),
    (
        "marina_notes/",
        "Marina's material — SessionTest click-through checklists and "
        "MarinaCheckSoon.html (open decisions, phrased as questions)",
        "per session (wrap-up skill)",
        "wrap-up skill",
    ),
    (
        "archive/",
        "Frozen history — executed plans, finished concepts, session "
        "write-ups. Never updated, never quoted as current",
        "never (things only move IN)",
        "archive rule in CLAUDE.md",
    ),
]


def _last_touched(path: Path) -> str:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%ad", "--date=short", "--", str(path.relative_to(ROOT))],
        capture_output=True, text=True, cwd=ROOT,
    ).stdout.strip()
    return out or date.today().isoformat()  # new file, committed today


def _esc(s: str) -> str:  # only for filenames; job lines may carry <code>
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _row(name: str, link: str, job: str, when: str, enforced: str, touched: str) -> str:
    return (
        f'    <tr><td class="doc"><a href="{link}">{_esc(name)}</a></td>'
        f"<td>{job}</td><td>{when}</td><td>{enforced}</td>"
        f'<td class="date">{touched}</td></tr>\n'
    )


def build() -> str:
    top_files = sorted(
        [p for p in DOCS.iterdir() if p.is_file() and p.suffix in (".md", ".html")],
        key=lambda p: p.name,
    )
    known = [p for p in top_files if p.name in TOP_LEVEL]
    unknown = [p.name for p in top_files if p.name not in TOP_LEVEL and p.name != OUT.name]
    if unknown:
        sys.exit(
            "gen_docs_map: no registry entry for: " + ", ".join(unknown)
            + "\nAdd a job line to TOP_LEVEL in tools/gen_docs_map.py first."
        )

    top_rows = ""
    order = list(TOP_LEVEL)  # registry order = reading order
    for name in order:
        p = DOCS / name
        if not p.exists() and name == "docs_map.html":
            p = OUT  # first run: the file is being created right now
        job, when, enforced = TOP_LEVEL[name]
        top_rows += _row(name, name, job, when, enforced,
                         _last_touched(p) if p.exists() else date.today().isoformat())

    folder_rows = ""
    for name, job, when, enforced in FOLDERS:
        n = len([f for f in (DOCS / name.rstrip("/")).rglob("*") if f.is_file()])
        folder_rows += _row(f"{name} ({n} files)", name, job, when, enforced, "—")

    claude_root = sorted((DOCS / "claude").glob("*.md"), key=lambda p: p.name)
    claude_comp = sorted((DOCS / "claude" / "components").glob("*.md"), key=lambda p: p.name)
    claude_rows = ""
    for group, files in (("mini apps + map", claude_root), ("components", claude_comp)):
        claude_rows += (
            f'    <tr class="group"><td colspan="3">{group} — {len(files)} files</td></tr>\n'
        )
        for p in files:
            rel = p.relative_to(DOCS).as_posix()
            claude_rows += (
                f'    <tr><td class="doc"><a href="{rel}">{_esc(p.name)}</a></td>'
                f'<td class="hint">described in <a href="claude/mini-apps.md">mini-apps.md</a></td>'
                f'<td class="date">{_last_touched(p)}</td></tr>\n'
            )

    today = date.today().isoformat()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>chaosco — Documentation Map</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color:#1d1d1f;
         background:#f8f9fa; max-width: 72rem; margin: 2rem auto; padding: 0 1.2rem; line-height: 1.5; }}
  h1 {{ font-size: 1.45rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.05rem; margin: 1.8rem 0 0.5rem; }}
  .subtitle {{ color:#6c757d; font-size:0.88rem; margin-bottom: 1.4rem; }}
  .concept {{ background:#fff; border:1px solid #dee2e6; border-left:4px solid #2b6cb0;
              border-radius:8px; padding:0.9rem 1.1rem; font-size:0.9rem; margin-bottom:1.4rem; }}
  .concept p {{ margin:0.4rem 0; }}
  table {{ border-collapse:collapse; width:100%; background:#fff; font-size:0.85rem;
           border:1px solid #dee2e6; border-radius:8px; }}
  th, td {{ border-bottom:1px solid #e9ecef; padding:0.45rem 0.7rem; text-align:left;
            vertical-align:top; }}
  th {{ background:#f1f3f5; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.03em; }}
  td.doc {{ white-space:nowrap; font-weight:600; }}
  td.date {{ white-space:nowrap; color:#6c757d; font-size:0.8rem; }}
  td.hint {{ color:#6c757d; }}
  tr.group td {{ background:#f8f9fa; font-weight:700; font-size:0.8rem; color:#475569; }}
  a {{ color:#2b6cb0; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  code {{ background:#f1f3f5; border-radius:3px; padding:0 4px; font-size:0.9em; }}
  .footer {{ color:#6c757d; font-size:0.8rem; margin-top:1.4rem; }}
</style>
</head>
<body>

<h1>Documentation Map</h1>
<p class="subtitle">Every doc, its job, its update trigger, its enforcement.
<strong>Generated {today}</strong> by <code>tools/gen_docs_map.py</code> — the job lines are
hand-written in that script's registry, the file list and dates come from the
filesystem and git. Regenerate after adding or removing a doc (the suite
fails until you do).</p>

<div class="concept">
  <p><strong>The concept</strong> [agreed 2026-09-01]:</p>
  <p><strong>1. Every doc has ONE job.</strong> A fact is <em>described</em> at exactly one
  altitude; other docs may name it, never re-describe it. When you cannot tell two docs
  apart, one of them has stopped doing its job.</p>
  <p><strong>2. Facts are generated or tested, meaning is hand-written.</strong> Anything a
  script can derive from the code (routes, tables, columns, dates) must not depend on
  someone remembering to type it. Only the WHY is written by hand — a script can never
  know why.</p>
  <p><strong>3. story &rarr; rule &rarr; test.</strong> A lesson
  (<code>lessons_learned.md</code> / <code>ways_of_working.md</code>) that keeps mattering
  becomes a guideline (<code>coding_guidelines.md</code>); a guideline a machine can check
  becomes a test. Every promotion makes the next review shorter.</p>
</div>

<h2>Whole-project docs (docs/)</h2>
<table>
  <thead><tr><th>Doc</th><th>Job</th><th>Update when</th><th>Enforced by</th><th>Last touched</th></tr></thead>
  <tbody>
{top_rows}  </tbody>
</table>

<h2>Folders</h2>
<table>
  <thead><tr><th>Folder</th><th>Job</th><th>Update when</th><th>Enforced by</th><th></th></tr></thead>
  <tbody>
{folder_rows}  </tbody>
</table>

<h2>Per-app deep dives (docs/claude/)</h2>
<table>
  <thead><tr><th>Doc</th><th>What it is</th><th>Last touched</th></tr></thead>
  <tbody>
{claude_rows}  </tbody>
</table>

<div class="footer">Companion docs outside docs/: <code>CLAUDE.md</code> (the terse
always-loaded map + non-negotiable rules) &middot; <code>tools/README.md</code> &middot;
<code>docs/archive/README.md</code>. Dates are as of generation, not live.</div>

</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
