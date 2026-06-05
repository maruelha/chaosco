# chaosco

A personal toolkit for the chaos coordinator — tools for managing tasks, planning, and keeping the juggling act together.

---

## Requirements

```
pip install pandas openpyxl pyyaml
```

---

## Quick start — double-click launcher

Double-click **`run.bat`** in the repo root. It runs the full pipeline
(parse → archive → import → summary) and keeps the window open so you can read the result.

Equivalent command line:
```
python -m app.main
python -m app.main --config path/to/settings.yaml
```

---

## Configuration

Edit `config/settings.yaml`. All settings across Steps 1–3:

```yaml
# --- Step 1: file location ---
downloads_folder:   'C:\path\to\Downloads'       # folder containing the Excel export
filename_stem:      "DTC_UAT_testtracking_ROE"   # matches stem.xlsx and stem(n).xlsx
defects_sheet_name: "Defects"

# --- Step 2: database + skip log ---
database_path:  'data/test_coordination.db'      # SQLite file (created on first run)
skiplog_folder: 'output/skiplog'                 # per-run skip-log CSVs go here

# --- Step 3: archiving ---
archive_enabled: true                            # set false to disable archiving
archive_mode:    "once_per_file"                 # or "always"
archive_folder:  'archive'                       # where archived copies go
```

> **YAML tip:** use single quotes `'...'` for Windows paths — backslashes in double-quoted
> strings are treated as escape characters.

---

## Full pipeline — what happens on each run

1. **Parse** — finds the newest matching `.xlsx` in `downloads_folder`, reads the Defects sheet
2. **Archive** — copies the file to `archive_folder` (see rules below); fatal if this fails
3. **Import** — upserts rows into SQLite; records `first_seen` / `last_seen`
4. **Skip log** — writes a CSV for any skipped rows (blank id, duplicate id)
5. **Summary** — prints counts + archive + skip-log status

---

## Archiving

| Setting | Behaviour |
|---|---|
| `archive_enabled: false` | Archiving skipped entirely; import still runs normally |
| `archive_mode: once_per_file` | Archives only if the file's **SHA-256 content hash** hasn't been seen before in `archive_folder`. Repeated runs on the same download → archived once. A fresh daily export → archived again. |
| `archive_mode: always` | Archives on every run with a fresh timestamp |

Archived files are named `YYYY-MM-DD_HHMM_<originalfilename>.xlsx`.

If archiving is **enabled and fails** (e.g. folder not writable), the run aborts before
touching the database — so data is never imported without a successful archive.

---

## Step 1 — Read Defects tab (diagnostic only)

Prints parsed rows to screen without writing anything.

```
python -m app.read_defects
```

---

## Import rules

### Upsert

| Condition | Action |
|---|---|
| New `defect_id` | INSERT; `first_seen` = `last_seen` = today |
| Existing `defect_id` | UPDATE all columns; `last_seen` = today; `first_seen` unchanged |
| Absent from this export | Left untouched (never deleted) |

### Skip / ignore (per row, in sheet order)

| Condition | Action |
|---|---|
| Every field blank | Ignored silently |
| Has content but blank `defect_id` | Skipped + written to skip-log CSV |
| Duplicate `defect_id` within this import | First kept, rest skipped + logged |

---

## Inspecting the database

Open `data/test_coordination.db` in **DB Browser for SQLite**.

```sql
-- See all defects
SELECT defect_id, solman_status, excel_row, first_seen, last_seen
FROM defects
ORDER BY excel_row;
```

### Confirm idempotency

Run `python -m app.main` twice on the same file:

```sql
SELECT defect_id, first_seen, last_seen FROM defects;
```

`first_seen` stays the same. `last_seen` = today after both runs.
First run: `Inserted > 0`. Second run: `Inserted = 0`, `Updated > 0`.

---

## Testing with synthetic data

`make_test_file.py` writes a test Excel to `test_data/` (never `downloads_folder`) with a
`_TEST` suffix — it cannot overwrite real data.

```
python make_test_file.py
python -m app.main --config config/settings_test.yaml
```

The test config sets `archive_enabled: false` so test runs don't create archives.

Expected: 3 inserted, 1 blank_defect_id skip, 1 duplicate skip, 1 ignored.

---

## Header mapping

All header matching is case-insensitive and whitespace-insensitive.
The mapping dict `_HEADER_MAP` is at the top of `app/read_defects.py` — adjust it there
if column names in the real file differ.
