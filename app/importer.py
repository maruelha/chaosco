"""Shared import pipeline — called by both CLI (main.py) and web UI (web.py).

run_import(cfg) runs the full pipeline for all enabled importers and always
returns a result dict; it never calls sys.exit so it is safe to call from a
web request handler.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from app import archiver, database
from app.db import ecom as db_ecom
from app.ecom_importer import parse_ecom
from app.read_defects import ParseError, _find_latest_xlsx, parse_defects
from app.retail_importer import parse_retail
from app.spillover_importer import parse_spillover


def _write_skiplog(skipped_rows: list[dict], skiplog_folder: Path, label: str = "defects") -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = skiplog_folder / f"{ts}_{label}_skipped.csv"
    skiplog_folder.mkdir(parents=True, exist_ok=True)
    sample = skipped_rows[0]
    data_keys = [k for k in sample if k not in ("excel_row", "reason")]
    fieldnames = ["excel_row", "reason"] + data_keys
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(skipped_rows)
    return path


def _resolve_imports(cfg: dict) -> dict:
    """Return the imports config dict.

    Falls back to defects-only if the 'imports' section is absent (old config shape).
    """
    if "imports" in cfg:
        return cfg["imports"]
    return {
        "defects": {
            "enabled": True,
            "sheet_name": cfg.get("defects_sheet_name", "Defects"),
        }
    }


def run_import(cfg: dict) -> dict:
    """Locate + archive file once, then run all enabled importers.  Never raises.

    Result keys:
        ok             : bool  — True if all enabled importers succeeded
        error          : str | None  — set on pre-import failure (file/archive)
        today          : str
        xlsx_path      : str | None
        archive_status : "archived" | "skipped_duplicate" | "disabled"
        archive_path   : str | None
        matched_archive: str | None
        defects        : dict  — per-importer result (see below)
        spillover      : dict  — per-importer result (see below)

    Per-importer result keys:
        enabled        : bool
        ok             : bool
        error          : str | None
        inserted, updated, skiplog_path, ... (importer-specific counts)
    """
    today = date.today().isoformat()
    imports = _resolve_imports(cfg)

    def_cfg  = imports.get("defects",  {})
    spl_cfg  = imports.get("spillover", {})
    ret_cfg  = imports.get("retail",   {})
    eco_cfg  = imports.get("ecom",     {})
    defects_enabled   = def_cfg.get("enabled", True)
    spillover_enabled = spl_cfg.get("enabled", False)
    retail_enabled    = ret_cfg.get("enabled", False)
    ecom_enabled      = eco_cfg.get("enabled", False)

    result: dict = {
        "ok": False,
        "error": None,
        "today": today,
        "xlsx_path": None,
        "archive_status": "disabled",
        "archive_path": None,
        "matched_archive": None,
        "defects": {
            "enabled": defects_enabled,
            "ok": not defects_enabled,   # disabled counts as ok
            "error": None,
            "inserted": 0, "updated": 0,
            "skipped_blank_id": 0, "skipped_duplicate": 0, "ignored_blank": 0,
            "skiplog_path": None,
        },
        "spillover": {
            "enabled": spillover_enabled,
            "ok": not spillover_enabled,  # disabled counts as ok
            "error": None,
            "inserted": 0, "updated": 0,
            "skipped_blank_name": 0,
            "skiplog_path": None,
        },
        "retail": {
            "enabled": retail_enabled,
            "ok": not retail_enabled,     # disabled counts as ok
            "error": None,
            "inserted": 0, "updated": 0,
            "skipped_blank_key": 0,
            "skiplog_path": None,
        },
        "ecom": {
            "enabled": ecom_enabled,
            "ok": not ecom_enabled,       # disabled counts as ok
            "error": None,
            "inserted": 0, "updated": 0,
            "skipped_missing_jira_id": 0,
            "skiplog_path": None,
        },
    }

    # 1. Locate file
    raw_folder = cfg.get("downloads_folder")
    if not raw_folder:
        result["error"] = "downloads_folder is not set in config/settings.yaml — please add your Downloads path."
        return result
    folder = Path(raw_folder)
    stem   = cfg["filename_stem"]
    if not folder.exists():
        result["error"] = f"downloads_folder does not exist: {folder}"
        return result
    xlsx_path = _find_latest_xlsx(folder, stem)
    if xlsx_path is None:
        result["error"] = (
            f"No matching .xlsx file found in {folder}\n"
            f"  Expected name matching: {stem}[optional (n)].xlsx"
        )
        return result
    result["xlsx_path"] = str(xlsx_path)

    # 2. Archive once — abort before any DB writes if this fails
    try:
        ar = archiver.archive_file(xlsx_path, cfg)
    except RuntimeError as exc:
        result["error"] = str(exc)
        return result
    result["archive_status"]  = ar["status"]
    result["archive_path"]    = str(ar["archive_path"]) if ar["archive_path"] else None
    result["matched_archive"] = ar["matched_archive"]

    # 3. Parse all enabled importers (no DB yet — catch parse failures early)
    defects_rows   = None
    spillover_rows = None
    retail_rows    = None

    if defects_enabled:
        defects_parse_cfg = {**cfg, "defects_sheet_name": def_cfg.get("sheet_name", "Defects")}
        try:
            defects_rows = parse_defects(defects_parse_cfg, xlsx_path=xlsx_path)["rows"]
        except ParseError as exc:
            result["defects"]["error"] = str(exc)
            result["defects"]["ok"] = False

    if spillover_enabled:
        spl_parse_cfg = {**cfg, "spillover_sheet_name": spl_cfg.get("sheet_name", "Core South Spillover")}
        try:
            spillover_rows = parse_spillover(spl_parse_cfg, xlsx_path=xlsx_path)["rows"]
        except ParseError as exc:
            result["spillover"]["error"] = str(exc)
            result["spillover"]["ok"] = False

    if retail_enabled:
        ret_parse_cfg = {**cfg, "retail_sheet_name": ret_cfg.get("sheet_name", "Retail")}
        try:
            retail_rows = parse_retail(ret_parse_cfg, xlsx_path=xlsx_path)["rows"]
        except ParseError as exc:
            result["retail"]["error"] = str(exc)
            result["retail"]["ok"] = False

    ecom_rows = None
    if ecom_enabled:
        eco_parse_cfg = {**cfg, "ecom_sheet_name": eco_cfg.get("sheet_name", "ECOM")}
        try:
            ecom_rows = parse_ecom(eco_parse_cfg, xlsx_path=xlsx_path)["rows"]
        except ParseError as exc:
            result["ecom"]["error"] = str(exc)
            result["ecom"]["ok"] = False

    # 4. DB writes — single connection for all importers
    skiplog_folder = Path(cfg["skiplog_folder"])
    db_path = Path(cfg["database_path"])
    if ecom_enabled:
        db_ecom.init_schema(db_path)   # own vertical schema (not in core init_db)
    conn = database.init_db(db_path)
    try:
        if defects_rows is not None:
            try:
                upsert = database.upsert_defects(conn, defects_rows, today)
            except Exception as exc:
                result["defects"]["error"] = f"Database write failed: {exc}"
                result["defects"]["ok"] = False
            else:
                skiplog_path = None
                if upsert["skipped_rows"]:
                    skiplog_path = _write_skiplog(upsert["skipped_rows"], skiplog_folder, "defects")
                result["defects"].update({
                    "ok": True,
                    "inserted":          upsert["inserted"],
                    "updated":           upsert["updated"],
                    "skipped_blank_id":  upsert["skipped_blank_id"],
                    "skipped_duplicate": upsert["skipped_duplicate"],
                    "ignored_blank":     upsert["ignored_blank"],
                    "skiplog_path":      str(skiplog_path) if skiplog_path else None,
                })

        if spillover_rows is not None:
            try:
                upsert = database.upsert_spillover_rows(conn, spillover_rows, today)
            except Exception as exc:
                result["spillover"]["error"] = f"Database write failed: {exc}"
                result["spillover"]["ok"] = False
            else:
                skiplog_path = None
                if upsert["skipped_rows"]:
                    skiplog_path = _write_skiplog(upsert["skipped_rows"], skiplog_folder, "spillover")
                result["spillover"].update({
                    "ok": True,
                    "inserted":           upsert["inserted"],
                    "updated":            upsert["updated"],
                    "skipped_blank_name": upsert["skipped_blank_name"],
                    "skiplog_path":       str(skiplog_path) if skiplog_path else None,
                })

        if retail_rows is not None:
            try:
                upsert = database.upsert_retail_rows(conn, retail_rows, today)
            except Exception as exc:
                result["retail"]["error"] = f"Database write failed: {exc}"
                result["retail"]["ok"] = False
            else:
                skiplog_path = None
                if upsert["skipped_rows"]:
                    skiplog_path = _write_skiplog(upsert["skipped_rows"], skiplog_folder, "retail")
                result["retail"].update({
                    "ok": True,
                    "inserted":         upsert["inserted"],
                    "updated":          upsert["updated"],
                    "skipped_blank_key": upsert["skipped_blank_key"],
                    "skiplog_path":     str(skiplog_path) if skiplog_path else None,
                })

        if ecom_rows is not None:
            try:
                upsert = db_ecom.upsert_ecom_rows(conn, ecom_rows, today)
            except Exception as exc:
                result["ecom"]["error"] = f"Database write failed: {exc}"
                result["ecom"]["ok"] = False
            else:
                skiplog_path = None
                if upsert["skipped_rows"]:
                    skiplog_path = _write_skiplog(upsert["skipped_rows"], skiplog_folder, "ecom")
                result["ecom"].update({
                    "ok": True,
                    "inserted":                upsert["inserted"],
                    "updated":                 upsert["updated"],
                    "skipped_missing_jira_id": upsert["skipped_missing_jira_id"],
                    "skiplog_path":            str(skiplog_path) if skiplog_path else None,
                })
    finally:
        conn.close()

    result["ok"] = (
        result["defects"]["ok"]
        and result["spillover"]["ok"]
        and result["retail"]["ok"]
        and result["ecom"]["ok"]
    )
    return result
