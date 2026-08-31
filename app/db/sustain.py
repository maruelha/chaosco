"""Core South Sustainphase Monitoring (planning chat 2026-08-27).

Imported from the daily GBS Operations checklist workbook
(`…DTC_GBS Operations_checklist.xlsx`, one tab per stream per day —
see docs/claude/sustain.md). sustain_tasks / sustain_task_details is a
1:n import pair, replaced per (day, stream) tab on each upload so
consecutive files with different date windows accumulate history.
Never holds user-authored data.

Workbook layout changed 2026-08-31: the header row moved 6 -> 5 and a
free-text column M "Comments/Observations" was added (stored in
`comments`, shown in the day report and the summary, but deliberately NOT
part of any status — the workbook's own Task Overall ignores it too).
The summary row also changed its definitions and `summary_counts` follows
it: DUE = OK + Pending + Review (a due task whose Overall is N/A is no
longer part of the due population), COMPLETED = OK only.

The workbook's summary row and the parent rollup cells are cached
formula values that are only right after a save ("Save file to check"),
so ALL aggregation is recomputed here from the raw cells:
`derive_country_cell` mirrors the parent H–K rollup formula,
`derive_overall` mirrors the Task Overall (L) formula, both with
COUNTIF's case-insensitive matching. On top of the Excel-faithful
values, `task_status` adds the one deliberate deviation: a free-text
result (an issue note typed into a cell) always classifies the task as
"attention", even where Excel's L would let it fall through to
Pending/OK.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db.core import get_connection

STREAM_RETAIL = "Retail"
STREAM_ECOM = "eCom"

# country → its result column, in workbook column order H..K
COUNTRY_COLUMNS = [
    ("France", "result_fr"),
    ("Italy", "result_it"),
    ("Portugal", "result_pt"),
    ("Spain", "result_es"),
]

# result-cell vocabulary; anything else non-blank is free text (an issue
# note typed by the team — the discussion-point signal)
_VOCAB = {"ok", "pending", "not due", "n/a", "review", "no occurrence"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sustain_tasks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    day       TEXT NOT NULL,
    stream    TEXT NOT NULL,
    excel_row INTEGER,
    task_id   TEXT,
    taxonomy  TEXT,
    process   TEXT,
    cadence   TEXT,
    due_today TEXT,
    country   TEXT,
    provider  TEXT,
    result_fr TEXT,
    result_it TEXT,
    result_pt TEXT,
    result_es TEXT,
    overall   TEXT,
    comments  TEXT
);
CREATE INDEX IF NOT EXISTS ix_sustain_tasks_tab ON sustain_tasks(day, stream);

CREATE TABLE IF NOT EXISTS sustain_task_details (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_pk   INTEGER NOT NULL REFERENCES sustain_tasks(id),
    excel_row INTEGER,
    cadence   TEXT,
    due_today TEXT,
    country   TEXT,
    provider  TEXT,
    result_fr TEXT,
    result_it TEXT,
    result_pt TEXT,
    result_es TEXT,
    overall   TEXT,
    comments  TEXT
);
CREATE INDEX IF NOT EXISTS ix_sustain_details_task
    ON sustain_task_details(task_pk);
"""


# additive migrations, safe to re-run (see CLAUDE.md)
_MIGRATIONS = [
    "ALTER TABLE sustain_tasks ADD COLUMN comments TEXT",
    "ALTER TABLE sustain_task_details ADD COLUMN comments TEXT",
]


def init_schema(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        for statement in _MIGRATIONS:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass          # column already there
        conn.commit()
    finally:
        conn.close()


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# --- classification (pure, Excel-faithful) ------------------------------

def _norm(value) -> str:
    return str(value).strip().casefold() if value is not None else ""


def is_free_text(value) -> bool:
    """Non-blank and outside the OK/Pending/Not due/N/A/Review vocabulary
    — i.e. an issue note the team typed directly into a result cell."""
    n = _norm(value)
    return bool(n) and n not in _VOCAB


def detail_result(detail: dict):
    """A detail row's entry lives in its own country's column."""
    for country, col in COUNTRY_COLUMNS:
        if _norm(detail.get("country")) == country.casefold():
            return detail.get(col)
    return None


def derive_country_cell(details: list[dict], country: str) -> str:
    """Mirror of the parent H–K rollup formula over that country's due
    detail rows: none due → N/A, any blank → Pending, any value that is
    neither OK nor N/A (free text!) → Review, else OK."""
    due = [d for d in details
           if _norm(d.get("country")) == country.casefold()
           and _norm(d.get("due_today")) == "yes"]
    if not due:
        return "N/A"
    values = [_norm(detail_result(d)) for d in due]
    if any(not v for v in values):
        return "Pending"
    if any(v not in ("ok", "n/a") for v in values):
        return "Review"
    return "OK"


def derive_cells(task: dict) -> list[str]:
    """The four country cells FR/IT/PT/ES for a parent task — rolled up
    from its detail rows if it has any, its own literal cells otherwise."""
    details = task.get("details") or []
    if details:
        return [derive_country_cell(details, country)
                for country, _col in COUNTRY_COLUMNS]
    return [task.get(col) for _country, col in COUNTRY_COLUMNS]


def derive_overall(due_today, cells: list) -> str:
    """Mirror of the Task Overall (L) formula, case-insensitive like
    COUNTIF. `cells` are the four FR/IT/PT/ES values."""
    due = _norm(due_today)
    values = [_norm(c) for c in cells]
    if due == "no":
        return "Not due"
    if due == "on occurrence":
        if all(not v for v in values):
            return "No occurrence"
        if "review" in values:
            return "Review"
        if any(not v for v in values):
            return "Pending"
        return "OK"
    if "review" in values:
        return "Review"
    if "pending" in values:
        return "Pending"
    if "ok" in values:
        return "OK"
    if values.count("n/a") == 4:
        return "N/A"
    return "Pending"


def task_status(task: dict) -> str:
    """done | pending | attention | not_due for one parent task (with its
    'details' attached). Excel-faithful except: any free-text result cell
    (parent literal or due detail entry) forces "attention" — those issue
    notes must never hide behind an OK elsewhere in the row."""
    details = task.get("details") or []
    cells = derive_cells(task)
    overall = derive_overall(task.get("due_today"), cells)
    free_text = any(is_free_text(c) for c in cells) or any(
        is_free_text(detail_result(d)) for d in details
        if _norm(d.get("due_today")) == "yes")
    if overall == "Review" or free_text:
        return "attention"
    if overall in ("OK", "N/A"):
        return "done"
    if overall in ("Not due", "No occurrence"):
        return "not_due"
    return "pending"


# --- storage ------------------------------------------------------------

def task_count(conn: sqlite3.Connection) -> int:
    """Total imported parent tasks (all tabs) — dashboard card badge.
    Tolerant of the table not existing yet (partial-init test fixtures)."""
    try:
        return conn.execute("SELECT COUNT(*) FROM sustain_tasks").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def replace_day_stream(conn: sqlite3.Connection, day: str, stream: str,
                       tasks: list[dict]) -> dict:
    """Replace one (day, stream) tab: delete its rows, insert fresh.

    `tasks` are parent-task dicts (excel_row, task_id, taxonomy, process,
    cadence, due_today, country, provider, result_fr/it/pt/es, overall),
    each with a 'details' key holding its detail-row dicts (same fields
    minus task_id/taxonomy/process). Returns {'tasks': n, 'details': n}.
    """
    n_tasks = 0
    n_details = 0
    with conn:
        conn.execute(
            "DELETE FROM sustain_task_details WHERE task_pk IN"
            " (SELECT id FROM sustain_tasks WHERE day = ? AND stream = ?)",
            (day, stream))
        conn.execute("DELETE FROM sustain_tasks WHERE day = ? AND stream = ?",
                     (day, stream))
        for t in tasks:
            cur = conn.execute(
                "INSERT INTO sustain_tasks"
                " (day, stream, excel_row, task_id, taxonomy, process,"
                "  cadence, due_today, country, provider,"
                "  result_fr, result_it, result_pt, result_es, overall,"
                "  comments)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (day, stream, t.get("excel_row"), t.get("task_id"),
                 t.get("taxonomy"), t.get("process"), t.get("cadence"),
                 t.get("due_today"), t.get("country"), t.get("provider"),
                 t.get("result_fr"), t.get("result_it"), t.get("result_pt"),
                 t.get("result_es"), t.get("overall"), t.get("comments")))
            task_pk = cur.lastrowid
            n_tasks += 1
            for d in t.get("details", []):
                conn.execute(
                    "INSERT INTO sustain_task_details"
                    " (task_pk, excel_row, cadence, due_today, country,"
                    "  provider, result_fr, result_it, result_pt, result_es,"
                    "  overall, comments)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (task_pk, d.get("excel_row"), d.get("cadence"),
                     d.get("due_today"), d.get("country"), d.get("provider"),
                     d.get("result_fr"), d.get("result_it"),
                     d.get("result_pt"), d.get("result_es"), d.get("overall"),
                     d.get("comments")))
                n_details += 1
    return {"tasks": n_tasks, "details": n_details}


def list_tabs(conn: sqlite3.Connection) -> list[dict]:
    """Imported (day, stream) tabs with parent-task counts, ordered by
    day then stream — drives the day picker."""
    try:
        return _rows_to_dicts(conn.execute(
            "SELECT day, stream, COUNT(*) AS task_count FROM sustain_tasks"
            " GROUP BY day, stream ORDER BY day, stream"))
    except sqlite3.OperationalError:
        return []


def list_tasks(conn: sqlite3.Connection, day: str, stream: str) -> list[dict]:
    """Parent tasks of one tab in workbook order, each with its 'details'
    list attached (also in workbook order)."""
    try:
        tasks = _rows_to_dicts(conn.execute(
            "SELECT * FROM sustain_tasks WHERE day = ? AND stream = ?"
            " ORDER BY excel_row", (day, stream)))
    except sqlite3.OperationalError:
        return []
    if not tasks:
        return []
    ids = [t["id"] for t in tasks]
    placeholders = ",".join("?" for _ in ids)
    details_by_task: dict[int, list[dict]] = {pk: [] for pk in ids}
    for d in _rows_to_dicts(conn.execute(
            f"SELECT * FROM sustain_task_details"
            f" WHERE task_pk IN ({placeholders}) ORDER BY excel_row", ids)):
        details_by_task[d["task_pk"]].append(d)
    for t in tasks:
        t["details"] = details_by_task[t["id"]]
    return tasks


def attention_items(conn: sqlite3.Connection, day: str,
                    stream: str) -> list[dict]:
    """The discussion agenda for one tab: every result cell that is
    neither OK/Pending/N-A/blank — i.e. free-text issue notes plus literal
    'Review' marks — with the verbatim text. Parent literal cells for
    simple tasks, due detail entries for tasks with details; not-due
    detail rows are skipped (their notes aren't today's business)."""
    items: list[dict] = []
    for task in list_tasks(conn, day, stream):
        base = {"task_id": task.get("task_id"),
                "process": task.get("process"),
                "taxonomy": task.get("taxonomy"),
                "excel_row": task.get("excel_row")}
        details = task.get("details") or []
        if details:
            for d in details:
                if _norm(d.get("due_today")) != "yes":
                    continue
                entry = detail_result(d)
                if is_free_text(entry) or _norm(entry) == "review":
                    items.append({**base, "country": d.get("country"),
                                  "provider": d.get("provider"),
                                  "text": str(entry).strip()})
        else:
            for country, col in COUNTRY_COLUMNS:
                value = task.get(col)
                if is_free_text(value) or _norm(value) == "review":
                    items.append({**base, "country": country,
                                  "provider": task.get("provider"),
                                  "text": str(value).strip()})
    return items


def overview(conn: sqlite3.Connection) -> list[dict]:
    """summary_counts for every imported tab, in list_tabs order —
    drives the management summary's headline grid and day-over-day
    trend."""
    return [{"day": t["day"], "stream": t["stream"],
             "task_count": t["task_count"],
             "counts": summary_counts(conn, t["day"], t["stream"])}
            for t in list_tabs(conn)]


def repeat_offenders(conn: sqlite3.Connection) -> list[dict]:
    """Attention items recurring on 2+ days for the same
    (stream, task, country, provider) — a one-day issue is noise, a
    multi-day one is a topic. Returns dicts with the sorted 'days' and
    the deduped verbatim 'texts' (first-seen order)."""
    grouped: dict[tuple, dict] = {}
    for tab in list_tabs(conn):
        for item in attention_items(conn, tab["day"], tab["stream"]):
            key = (tab["stream"], item.get("task_id"), item.get("country"),
                   item.get("provider"))
            entry = grouped.setdefault(key, {
                "stream": tab["stream"], "task_id": item.get("task_id"),
                "process": item.get("process"),
                "taxonomy": item.get("taxonomy"),
                "country": item.get("country"),
                "provider": item.get("provider"),
                "days": [], "texts": []})
            if tab["day"] not in entry["days"]:
                entry["days"].append(tab["day"])
            if item["text"] not in entry["texts"]:
                entry["texts"].append(item["text"])
    offenders = [e for e in grouped.values() if len(e["days"]) >= 2]
    for e in offenders:
        e["days"].sort()
    offenders.sort(key=lambda e: (-len(e["days"]), e["stream"],
                                  str(e["task_id"])))
    return offenders


# Overall values that make a due task part of the workbook's DUE
# population (its summary row computes DUE as OK + Pending + Review, so a
# due task whose Overall is N/A drops out entirely) [2026-08-31].
_DUE_OVERALLS = ("ok", "pending", "review")


def summary_counts(conn: sqlite3.Connection, day: str, stream: str) -> dict:
    """Recomputed due/completed/pending/attention for one tab (never the
    workbook's cached summary row).

    Mirrors the workbook's own definitions as of the 2026-08-31 file:
    DUE = due tasks whose Overall is OK/Pending/Review (N/A drops out),
    COMPLETED = Overall OK, PENDING = Overall Pending. The one deliberate
    deviation stands: a task flagged "attention" (literal Review or a
    free-text issue note) is counted in neither completed nor pending, and
    attention counts over ALL parents — an on-occurrence issue must
    surface too, even though the workbook now restricts its REVIEW count
    to due tasks."""
    counts = {"due": 0, "completed": 0, "pending": 0, "attention": 0}
    for task in list_tasks(conn, day, stream):
        status = task_status(task)
        overall = _norm(derive_overall(task.get("due_today"),
                                       derive_cells(task)))
        if _norm(task.get("due_today")) == "yes" and overall in _DUE_OVERALLS:
            counts["due"] += 1
            if status == "attention":
                pass                       # neither completed nor pending
            elif overall == "ok":
                counts["completed"] += 1
            elif overall == "pending":
                counts["pending"] += 1
        if status == "attention":
            counts["attention"] += 1
    return counts


def comment_items(conn: sqlite3.Connection, day: str,
                  stream: str) -> list[dict]:
    """Every non-blank Comments/Observations entry (column M, new in the
    2026-08-31 workbook) of one tab, parent rows and detail rows alike.
    Purely informational — comments never change a status, exactly as the
    workbook's Task Overall ignores column M."""
    items: list[dict] = []
    for task in list_tasks(conn, day, stream):
        base = {"task_id": task.get("task_id"),
                "process": task.get("process"),
                "taxonomy": task.get("taxonomy")}
        if task.get("comments"):
            items.append({**base, "country": task.get("country"),
                          "provider": task.get("provider"),
                          "text": str(task["comments"]).strip()})
        for d in task.get("details") or []:
            if d.get("comments"):
                items.append({**base, "country": d.get("country"),
                              "provider": d.get("provider"),
                              "text": str(d["comments"]).strip()})
    return items
