# chaosco

A personal toolkit for the chaos coordinator — tools for managing tasks, planning, and keeping the juggling act together.

---

## Step 1 — Read Defects tab

Finds the latest Excel export, parses the **Defects** sheet, and prints the rows to the screen.  
Nothing is written; the source file is never modified.

### Requirements

```
pip install pandas openpyxl pyyaml
```

### Configuration

Edit `config/settings.yaml`:

```yaml
downloads_folder: "C:/Users/YourName/Downloads"   # folder containing the Excel export
filename_stem:    "DTC_UAT_testtracking_ROE"       # matches stem.xlsx and stem(n).xlsx
defects_sheet_name: "Defects"                      # sheet name inside the workbook
```

### Run

```
# from the repo root
python -m app.read_defects

# with a custom config file
python -m app.read_defects --config path/to/other_settings.yaml
```

### Output shape

```
Read: C:/Users/.../Downloads/DTC_UAT_testtracking_ROE(2).xlsx
Defects sheet: 42 data rows

row    2 | defect_id='DEF-001' | solman_status='Open' | country='DE' | ...
row    3 | defect_id='DEF-002' | solman_status='Closed' | ...
...

Unmapped headers found in sheet : ['Some Unknown Column']
Recognised but ignored headers  : ['Comment', 'Defect Status']
Expected headers not found      : (none)
```

### Header mapping

All header matching is case-insensitive and whitespace-insensitive (spaces, tabs, newlines are collapsed).  
The mapping lives in a single dict `_HEADER_MAP` at the top of `app/read_defects.py` — adjust it there if column names in the real file differ.
