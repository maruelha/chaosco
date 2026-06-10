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

    if r["error"]:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"File        : {r['xlsx_path']}")
    print(f"Database    : {Path(cfg['database_path']).resolve()}")
    print(f"Date        : {r['today']}")

    if r["archive_status"] == "archived":
        print(f"Archived    : {r['archive_path']}")
    elif r["archive_status"] == "skipped_duplicate":
        print(f"Archived    : skipped — identical file already archived as {r['matched_archive']}")
    else:
        print("Archived    : skipped — archiving disabled in config")

    d = r["defects"]
    print()
    if not d["enabled"]:
        print("Defects     : disabled")
    elif d["error"]:
        print(f"Defects     : ERROR — {d['error']}", file=sys.stderr)
    else:
        print(f"Defects     : {d['inserted']} inserted, {d['updated']} updated"
              f"  |  {d['skipped_blank_id']} blank id, {d['skipped_duplicate']} duplicate skipped"
              f"  |  {d['ignored_blank']} blank rows ignored")
        if d["skiplog_path"]:
            print(f"  Skip log  : {d['skiplog_path']}")

    s = r["spillover"]
    if not s["enabled"]:
        print("Spillover   : disabled")
    elif s["error"]:
        print(f"Spillover   : ERROR — {s['error']}", file=sys.stderr)
    else:
        print(f"Spillover   : {s['inserted']} inserted, {s['updated']} updated"
              f"  |  {s['skipped_blank_name']} blank name skipped")
        if s["skiplog_path"]:
            print(f"  Skip log  : {s['skiplog_path']}")

    if not r["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Defects sheet into SQLite.")
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
