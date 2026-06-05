"""Shared import pipeline — called by both CLI (main.py) and web UI (web.py).

run_import(cfg) runs the full pipeline and always returns a result dict;
it never calls sys.exit so it is safe to call from a web request handler.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from app import archiver, database
from app.read_defects import ParseError, parse_defects


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


def run_import(cfg: dict) -> dict:
    """Parse → archive → upsert → skip-log.  Returns a result dict, never raises.

    Result keys:
        ok                : bool
        error             : str | None
        today             : str  (ISO date)
        xlsx_path         : str | None
        archive_status    : "archived" | "skipped_duplicate" | "disabled"
        archive_path      : str | None
        matched_archive   : str | None
        inserted          : int
        updated           : int
        skipped_blank_id  : int
        skipped_duplicate : int
        ignored_blank     : int
        skiplog_path      : str | None
    """
    today = date.today().isoformat()
    result: dict = {
        "ok": False,
        "error": None,
        "today": today,
        "xlsx_path": None,
        "archive_status": "disabled",
        "archive_path": None,
        "matched_archive": None,
        "inserted": 0,
        "updated": 0,
        "skipped_blank_id": 0,
        "skipped_duplicate": 0,
        "ignored_blank": 0,
        "skiplog_path": None,
    }

    # 1. Parse
    try:
        parse_result = parse_defects(cfg)
    except ParseError as exc:
        result["error"] = str(exc)
        return result

    xlsx_path = parse_result["xlsx_path"]
    rows = parse_result["rows"]
    result["xlsx_path"] = str(xlsx_path)

    # 2. Archive (abort before DB write if this fails)
    try:
        ar = archiver.archive_file(xlsx_path, cfg)
    except RuntimeError as exc:
        result["error"] = str(exc)
        return result

    result["archive_status"] = ar["status"]
    result["archive_path"] = str(ar["archive_path"]) if ar["archive_path"] else None
    result["matched_archive"] = ar["matched_archive"]

    # 3. Store
    db_path = Path(cfg["database_path"])
    conn = database.init_db(db_path)
    try:
        upsert = database.upsert_defects(conn, rows, today)
    except Exception as exc:
        conn.close()
        result["error"] = f"Database write failed: {exc}"
        return result
    conn.close()

    # 4. Skip log
    skiplog_path = None
    if upsert["skipped_rows"]:
        skiplog_path = _write_skiplog(upsert["skipped_rows"], Path(cfg["skiplog_folder"]))

    result.update({
        "ok": True,
        "inserted": upsert["inserted"],
        "updated": upsert["updated"],
        "skipped_blank_id": upsert["skipped_blank_id"],
        "skipped_duplicate": upsert["skipped_duplicate"],
        "ignored_blank": upsert["ignored_blank"],
        "skiplog_path": str(skiplog_path) if skiplog_path else None,
    })
    return result
