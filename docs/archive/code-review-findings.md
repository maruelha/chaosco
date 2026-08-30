# Code Review Findings — ARCHIVED (all findings resolved)

> **Status 2026-07-04:** every finding below is resolved. #1 (connection
> leaks) — routes use try/finally. #2 (silent empty-note no-op) — the generic
> note routes re-render with an error. #3 (init_db per request) — init_db runs
> once at startup, routes use get_connection. #4 (hardcoded URLs) — templates
> are url_for-based. #5 (inline datetime imports) — module-level. #6 (Excel
> opened twice) — pd.ExcelFile single open. #7 (archive re-hashing) —
> archive/hashes.txt manifest. #8 (duplicate note templates) — one
> note_form.html with mode flag. #9 (repeated 404 guards) — generic notes
> routes abort(404) centrally. Kept for historical reference only; the
> current review lives in docs/project_review_2026-07-04.md.

Initial review of the chaosco codebase after Passes A, B, and C.
Tracked in GitHub issue #10.

---

## Finding 1 — Connection leaks on exception

**File:** `app/web.py` — every route

**What it is**

Every route in `web.py` follows this pattern:

```python
conn = _get_conn()          # open connection
...do work...
conn.close()                # close it
return render_template(...)
```

The problem: if anything between `_get_conn()` and `conn.close()` throws an
exception — a bug, a bad database call, anything — Python jumps straight to
the error handler and `conn.close()` is never executed. The connection is left
open and forgotten.

**Why it matters**

SQLite allows only one writer at a time. If a connection is left open holding
a lock, the next write will either wait or fail. In Python the garbage
collector will eventually clean it up, but "eventually" is not a guarantee —
especially in a long-running web server process. It is also just wrong: you
opened a resource, you should close it.

**The fix**

Use `try/finally` so the close always happens regardless of what goes wrong:

```python
conn = _get_conn()
try:
    ...do work...
    return render_template(...)
finally:
    conn.close()
```

Or the cleaner Flask pattern: open the connection once per request using
Flask's `g` object and register a teardown function that closes it
automatically at the end of every request, success or failure.

---

## Finding 2 — Silent no-op on empty note

**File:** `app/web.py` — `note_add` route

**What it is**

The `note_add` route does this:

```python
if note_text:
    database.add_note(conn, defect_id, heading, note_text)
conn.close()
return redirect(url_for("defects_list", note_added="1"))
```

If the user submits the form with an empty note field, `note_text` is `None`,
the `if` is skipped, nothing is saved — but the code still redirects with
`note_added=1`, which displays the green "Note added." banner.

**Why it matters**

It is a lie to the user. They think their note was saved. It was not. In a
tool specifically for capturing information during testing, this is a
meaningful data-loss risk.

**The fix**

Check whether the required field was filled, and if not, re-render the form
with an error message instead of redirecting:

```python
if not note_text:
    return render_template("note_add.html", defect=defect,
                           return_to=return_to, error="Note text is required.")
```

Then show `{{ error }}` near the submit button in the template.

---

## Finding 3 — `init_db()` runs DDL on every web request

**File:** `app/web.py` — `_get_conn()`, `app/database.py` — `init_db()`

**What it is**

`_get_conn()` calls `database.init_db()` on every route:

```python
def _get_conn():
    return database.init_db(Path(_cfg["database_path"]))
```

And `init_db()` runs three `CREATE TABLE IF NOT EXISTS` DDL statements every
time it is called — once per page load.

**Why it matters**

"Initialise the database" is a startup operation, not a per-request one. The
name `init_db` promises something it only delivers once (tables already exist
after the first run), but it is called as if it is `get_connection`. The
misleading name makes the code harder to read. If you ever switched to
PostgreSQL or added real connection pooling this pattern would break badly.

**The fix**

Split into two functions:

```python
def init_db(db_path):
    """Run once at startup to create schema."""
    conn = _open(db_path)
    conn.executescript("CREATE TABLE IF NOT EXISTS ...")
    conn.close()

def get_connection(db_path):
    """Open and return a connection. Schema assumed to already exist."""
    return _open(db_path)
```

Call `init_db` once when the app starts. Call `get_connection` in routes.

---

## Finding 4 — Hardcoded URLs in templates

**Files:** `app/templates/defect_detail.html`, `note_add.html`,
`note_edit.html`, `note_confirm_delete.html`, `defects.html`

**What it is**

Templates write URLs as raw strings:

```html
<a href="/defects/{{ defect.defect_id }}/notes/{{ n.id }}/edit">Edit</a>
<form method="post" action="/defects/{{ defect.defect_id }}/notes">
```

Flask has a built-in function called `url_for` that generates URLs from route
names. The `web.py` redirects already use `url_for` correctly. The templates
do not.

**Why it matters**

If you rename or restructure a URL, you have to find every hardcoded
occurrence in every template and update it manually. With `url_for` you change
the route decorator in `web.py` once and every link updates automatically.
This is especially easy to miss in Jinja templates because there is no
compiler to catch dead links.

**The fix**

Replace all `href="/defects/..."` and `action="/defects/..."` in templates
with `url_for('route_name', ...)`. The route names are the function names in
`web.py`: `defects_list`, `defect_detail`, `note_add_form`, `note_edit`,
`note_delete`.

---

## Finding 5 — `datetime` imported inside function bodies

**File:** `app/database.py` — `upsert_defect_annotation()`, `add_note()`

**What it is**

Two functions import `datetime` inside the function body:

```python
def upsert_defect_annotation(...):
    from datetime import datetime   # inside the function
    now = datetime.now().isoformat(timespec="seconds")
```

The standard place for imports is at the top of the file.

**Why it matters**

Python caches module imports so there is no real performance cost after the
first call. But it is non-standard: readers expect imports at the top of the
file. When they see an import inside a function body they start wondering why
— is it to avoid a circular import? Is it lazy-loaded for a reason? In this
case the answer is "no reason", which is confusing noise. It also makes it
harder to audit the file's dependencies at a glance.

**The fix**

Move `from datetime import datetime` to the top of `database.py` with the
other imports. A two-second change.

---

## Finding 6 — Excel file opened twice in `parse_defects()`

**File:** `app/read_defects.py` — `parse_defects()`

**What it is**

The function opens the Excel file twice:

```python
# First time — with openpyxl directly, just to check sheet names
wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
available_sheets = wb.sheetnames
wb.close()

# Second time — pandas opens it again internally
df = pd.read_excel(xlsx_path, sheet_name=sheet_name, ...)
```

**Why it matters**

On a local machine it is barely noticeable. But two separate opens means two
separate file-lock windows. If the file is large, you are parsing the ZIP
container twice. The two opens are not atomic — in theory the file could
change between them (unlikely but not impossible on a shared drive).

**The fix**

Use `pd.ExcelFile` which lets you inspect sheet names from the same open
handle before reading data:

```python
with pd.ExcelFile(xlsx_path) as xf:
    if sheet_name not in xf.sheet_names:
        raise ParseError(...)
    df = xf.parse(sheet_name, header=0, dtype=str)
```

One open, one close.

---

## Finding 7 — Archive re-hashes all files on every import

**File:** `app/archiver.py` — `archive_file()`

**What it is**

In `once_per_file` mode, every import re-reads and re-hashes every file in
the archive folder:

```python
source_hash = _sha256(xlsx_path)
for existing in archive_folder.glob("*.xlsx"):
    if _sha256(existing) == source_hash:   # hashes every archived file
        return {"status": "skipped_duplicate", ...}
```

**Why it matters**

Right now there may be 5–10 files in the archive. A year from now, running
imports daily, there could be 250+ files. Each import would then read 250
Excel files off disk before doing anything else. Excel files are not small
and this will become noticeably slow.

**The fix**

Keep a manifest file in the archive folder — a simple text file with one hash
per line:

```
a3f2c8...  2026-01-15_0900_DTC_UAT_testtracking_ROE.xlsx
b7d91e...  2026-01-16_0900_DTC_UAT_testtracking_ROE.xlsx
```

On each run, load the manifest (fast, small file), check if the source hash
is in it. Only if the file is new, copy it and append to the manifest.

---

## Finding 8 — `note_add.html` and `note_edit.html` are near-identical

**Files:** `app/templates/note_add.html`, `app/templates/note_edit.html`

**What it is**

Both templates contain the same form: heading input, note textarea, cancel
button, submit button, breadcrumb, page header. The differences are small:
title, form action URL, pre-populated values, submit label, and whether the
footer shows `created_at`. The two files share roughly 85% of their lines.

**Why it matters**

When the form changes — say you add a "Category" field — you have to
remember to update both files. You will forget one of them at some point.
Bugs from this kind of drift are subtle because the two pages look similar
enough that you do not immediately notice the discrepancy.

**The fix**

One template with a `mode` variable passed from the route:

```html
{% if mode == "edit" %}
  <h1>Edit note</h1>
  ...pre-populate values...
{% else %}
  <h1>Add note</h1>
{% endif %}
```

The form fields themselves are identical — only the surrounding context
changes.

---

## Finding 9 — 404 guard repeated across 5 routes

**File:** `app/web.py` — `defect_detail`, `note_add_form`, `note_add`,
`note_edit`, `note_delete`

**What it is**

This block appears in five separate route functions:

```python
if defect is None:
    conn.close()
    return render_template("404.html", defect_id=defect_id), 404
```

**Why it matters**

It is easy to forget when adding a new route. It also mixes two concerns in
each route function: "does this resource exist?" and "do the actual work."
The `conn.close()` inside each guard is also a variation of the connection
leak problem from Finding 1 — if you refactor the guard you have to touch
five places.

**The fix**

A small helper that raises an exception on not-found, letting a registered
Flask error handler deal with the response:

```python
def _get_defect_or_404(conn, defect_id):
    defect = database.get_defect(conn, defect_id)
    if defect is None:
        abort(404)
    return defect
```

Flask's `abort(404)` triggers the registered 404 handler. Every route then
calls `_get_defect_or_404` — one line instead of three, and the 404 logic
lives in one place.

---

## Priority order

| Priority | Finding | Reason |
|----------|---------|--------|
| 1 | #2 — Silent no-op on empty note | User-facing data loss |
| 2 | #1 — Connection leaks | Correctness under errors |
| 3 | #3 — `init_db` per request | Semantic correctness |
| 4 | #5 — `datetime` imports inside functions | Trivial, one-minute fix |
| 5 | #4 — Hardcoded URLs in templates | Maintainability |
| 6 | #6 — Excel opened twice | Minor correctness |
| 7 | #8 — Duplicate note templates | When form gains a new field |
| 8 | #9 — Repeated 404 guard | When adding new routes |
| 9 | #7 — Archive re-hashing | Long-term performance |
