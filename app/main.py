"""CLI entry point: parse → archive → store → summary.

Usage:
    python -m app.main
    python -m app.main --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config_loader import load_config
from app.importer import run_import


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    r = run_import(cfg)

    if not r["ok"]:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"File        : {r['xlsx_path']}")
    print(f"Database    : {Path(cfg['database_path']).resolve()}")
    print(f"Date        : {r['today']}")
    print()
    print(f"  Inserted  : {r['inserted']}")
    print(f"  Updated   : {r['updated']}")
    print(f"  Skipped   : {r['skipped_blank_id']} blank defect_id"
          f"  |  {r['skipped_duplicate']} duplicate defect_id")
    print(f"  Ignored   : {r['ignored_blank']} fully blank rows")
    print(f"\nSkip log    : {r['skiplog_path'] or '(none — no rows skipped)'}")

    if r["archive_status"] == "archived":
        print(f"Archived    : {r['archive_path']}")
    elif r["archive_status"] == "skipped_duplicate":
        print(f"Archived    : skipped — identical file already archived as {r['matched_archive']}")
    else:
        print("Archived    : skipped — archiving disabled in config")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Defects sheet into SQLite.")
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
