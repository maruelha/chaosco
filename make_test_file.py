"""Create a synthetic Defects Excel file for testing Step 2 edge cases.

Places the file in the configured downloads_folder so you can run
  python -m app.main
immediately after.

Rows produced:
  row 2  DEF-001  normal row
  row 3  DEF-002  normal row
  row 4  (blank defect_id, other content)  -> skipped: blank_defect_id
  row 5  DEF-001  duplicate of row 2       -> skipped: duplicate_defect_id
  row 6  (entirely blank)                  -> ignored silently
  row 7  DEF-003  normal row

Expected import result: 3 inserted, 1 blank_defect_id skip, 1 duplicate skip, 1 ignored.
"""
import sys
from pathlib import Path

import pandas as pd
import yaml

config_path = Path("config/settings.yaml")
if not config_path.exists():
    print("Run this script from the repo root.", file=sys.stderr)
    sys.exit(1)

cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
folder = Path(cfg["downloads_folder"])
stem = cfg["filename_stem"]
out_path = folder / f"{stem}.xlsx"

headers = [
    "ECOM/\nRETAIL", "SOLMAN STATUS", "Defect ID", "Solman name",
    "Comment", "Defect Status",
    "raised by", "order number", "Date Reported", "Date Closed",
    "Priority", "Assigned to", "Tech Team", "Country", "Scenario",
    "affected testcases", "Retest Dependency", "Does it block execution",
    "Exists in production (yes/no)", "Defect reason",
]

rows = [
    # row 2 — normal
    ["Retail", "Open",        "DEF-001", "Login fails",     "c1", "InProgress",
     "Alice", "ORD-001", "2026-05-01", "",           "High",   "Bob",   "Backend",  "UK", "Login",    "TC-01",       "no",  "yes", "no",  "Code bug"],
    # row 3 — normal
    ["Retail", "In Progress", "DEF-002", "Timeout on pay",  "c2", "InProgress",
     "Carol", "ORD-002", "2026-05-10", "",           "Medium", "Dave",  "Frontend", "DE", "Checkout", "TC-02 TC-03", "yes", "no",  "no",  "Config"],
    # row 4 — blank defect_id (has other content)
    ["Retail", "New",         "",        "Missing mapping",  "c3", "New",
     "Eve",   "",        "2026-05-12", "",           "Low",    "Frank", "Backend",  "AT", "Returns",  "",            "no",  "no",  "no",  "Data issue"],
    # row 5 — duplicate defect_id (same as row 2)
    ["Retail", "Closed",      "DEF-001", "Login fails v2",  "c4", "Closed",
     "Alice", "ORD-001", "2026-05-01", "2026-05-20", "High",   "Bob",   "Backend",  "UK", "Login",    "TC-01",       "no",  "no",  "no",  "Fixed"],
    # row 6 — entirely blank
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    # row 7 — normal
    ["ECOM",   "New",         "DEF-003", "VAT not applied", "c5", "New",
     "Grace", "",        "2026-06-02", "",           "Medium", "Harry", "Backend",  "UK", "GKPM0016", "TC-04",       "yes", "yes", "no",  "Article setup"],
]

df = pd.DataFrame(rows, columns=headers)
folder.mkdir(parents=True, exist_ok=True)
df.to_excel(out_path, sheet_name="Defects", index=False)
print(f"Written: {out_path}")
print()
print("Expected import result:")
print("  Inserted : 3  (DEF-001, DEF-002, DEF-003)")
print("  Skipped  : 1 blank_defect_id (row 4)  |  1 duplicate_defect_id (row 5)")
print("  Ignored  : 1 fully blank row (row 6)")
