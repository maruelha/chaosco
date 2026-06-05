# chaosco

A personal toolkit for the chaos coordinator — tools for managing tasks, planning, and keeping the juggling act together.

---

## Requirements

```
pip install pandas openpyxl pyyaml
```

---

## Configuration

Edit `config/settings.yaml`:

```yaml
downloads_folder:   'C:\path\to\your\Downloads'   # folder containing the Excel export
filename_stem:      "DTC_UAT_testtracking_ROE"     # matches stem.xlsx and stem(n).xlsx
defects_sheet_name: "Defects"

database_path:  'data/test_coordination.db'  # SQLite file (created on first run)
skiplog_folder: 'output/skiplog'             # per-run skip-log CSVs go here
```

> **YAML tip:** use single quotes `'...'` for Windows paths — backslashes in double-quoted YAML strings are treated as escape characters.

---

## Step 1 — Read Defects tab (diagnostic)

Finds the latest Excel export, parses the Defects sheet, and prints rows to the screen.
Nothing is written; the source file is never modified.

```
python -m app.read_defects
python -m app.read_defects --config path/to/other_settings.yaml
```

Output shape:
```
Read: C:/…/DTC_UAT_testtracking_ROE.xlsx
Defects sheet: 42 data rows

row    2 | channel='Retail' | solman_status='Open' | defect_id='DEF-001' | …
…

Unmapped headers found in sheet : ['Some Unknown Column']
Recognised but ignored headers  : ['Comment', 'Defect Status']
Expected headers not found      : (none)
```

---

## Step 2 — Import Defects into SQLite

Parses the sheet and upserts rows into `data/test_coordination.db`.

```
python -m app.main
python -m app.main --config path/to/other_settings.yaml
```

Or double-click **`read_defects.bat`** (runs `app.main` and keeps the window open).

### What gets stored

| Table | Written by importer? |
|---|---|
| `defects` | Yes — upserted every run |
| `defect_annotations` | No — yours to fill in |
| `defect_notes` | No — yours to fill in |

### Upsert rules

- **New defect_id** → INSERT; `first_seen` = `last_seen` = today.
- **Existing defect_id** → UPDATE all columns; `last_seen` = today; `first_seen` unchanged.
- **Never deletes** — defects absent from the current export are left untouched.

### Skip / ignore rules (per row, in sheet order)

| Condition | Action |
|---|---|
| Every field is blank | Ignored silently (not logged) |
| Has content but blank `defect_id` | Skipped + written to skip-log CSV |
| `defect_id` duplicated within this import | First kept, subsequent skipped + logged |

Skip-log files are written to `output/skiplog/YYYY-MM-DD_HHMM_defects_skipped.csv`.
No file is created if nothing was skipped.

### Sample output

```
File        : C:\…\DTC_UAT_testtracking_ROE.xlsx
Database    : C:\…\data\test_coordination.db
Date        : 2026-06-05

  Inserted  : 3
  Updated   : 0
  Skipped   : 1 blank defect_id  |  1 duplicate defect_id
  Ignored   : 1 fully blank rows

Skip log    : output\skiplog\2026-06-05_1430_defects_skipped.csv
```

---

## Inspecting the database

Open `data/test_coordination.db` in **DB Browser for SQLite** (already in your Downloads folder).

### Confirm data was stored

```sql
SELECT defect_id, solman_status, excel_row, first_seen, last_seen
FROM defects
ORDER BY excel_row;
```

### Confirm idempotency

Run `python -m app.main` twice on the same file. Then:

```sql
SELECT defect_id, first_seen, last_seen FROM defects;
```

`first_seen` must stay the same on both runs. `last_seen` will equal today's date after both runs.
`Inserted` will be > 0 on the first run and 0 on the second (all `Updated`).

---

## Testing with synthetic data

`make_test_file.py` creates a test Excel file in your `downloads_folder` that contains
all edge cases: a blank `defect_id`, a duplicate `defect_id`, and a fully blank row.

```
python make_test_file.py
python -m app.main
```

Expected result: 3 inserted, 1 blank_defect_id skip, 1 duplicate skip, 1 ignored.

---

## Header mapping

All header matching is case-insensitive and whitespace-insensitive (spaces, tabs, newlines collapsed).
The mapping dict `_HEADER_MAP` lives at the top of `app/read_defects.py` — adjust it there if column
names in the real file differ from what's expected.
