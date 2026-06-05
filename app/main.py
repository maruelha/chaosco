"""Entry point: parse Defects sheet → archive source → store in SQLite → summary.

Usage:
    python -m app.main
    python -m app.main --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from app.config_loader import load_config
from app import archiver, database
from app.read_defects import parse_defects


def _write_skiplog(skipped_rows: list[dict], skiplog_folder: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = skiplog_folder / f"{ts}_defects_skipped.csv"
    skiplog_folder.mkdir(parents=True, exist_ok=True)

    sample = skipped_rows[0]
    data_keys = [k for k in sample if k not in ("excel_row", "reason")]
    fieldnames = ["excel_row", "reason"] + data_keys

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(skipped_rows)
    return path


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    today = date.today().isoformat()

    # --- 1. Parse ---
    result = parse_defects(cfg)
    xlsx_path = result["xlsx_path"]
    rows = result["rows"]

    # --- 2. Archive (fatal if enabled and fails — happens BEFORE any DB write) ---
    try:
        archive_result = archiver.archive_file(xlsx_path, cfg)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Import aborted — database was not modified.", file=sys.stderr)
        sys.exit(1)

    # --- 3. Store ---
    db_path = Path(cfg["database_path"])
    conn = database.init_db(db_path)
    try:
        upsert = database.upsert_defects(conn, rows, today)
    except Exception as exc:
        conn.close()
        print(f"ERROR: database write failed — {exc}", file=sys.stderr)
        sys.exit(1)
    conn.close()

    # --- 4. Skip log ---
    skiplog_path = None
    if upsert["skipped_rows"]:
        skiplog_folder = Path(cfg["skiplog_folder"])
        skiplog_path = _write_skiplog(upsert["skipped_rows"], skiplog_folder)

    # --- 5. Summary ---
    print(f"File        : {xlsx_path}")
    print(f"Database    : {db_path.resolve()}")
    print(f"Date        : {today}")
    print()
    print(f"  Inserted  : {upsert['inserted']}")
    print(f"  Updated   : {upsert['updated']}")
    print(f"  Skipped   : {upsert['skipped_blank_id']} blank defect_id"
          f"  |  {upsert['skipped_duplicate']} duplicate defect_id")
    print(f"  Ignored   : {upsert['ignored_blank']} fully blank rows")

    if skiplog_path:
        print(f"\nSkip log    : {skiplog_path}")
    else:
        print("\nSkip log    : (none — no rows skipped)")

    status = archive_result["status"]
    if status == "archived":
        print(f"Archived    : {archive_result['archive_path']}")
    elif status == "skipped_duplicate":
        print(f"Archived    : skipped — identical file already archived as"
              f" {archive_result['matched_archive']}")
    else:
        print("Archived    : skipped — archiving disabled in config")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Defects sheet into SQLite.")
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
