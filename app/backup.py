"""DB + uploads backup to a configured folder [USER 2026-07-18].

One-click backup to `backup_folder` (machine-specific — set it in
settings.local.yaml, e.g. the external drive). Two things are saved:

1. The SQLite DB, via sqlite3's backup API (NOT a raw file copy — the
   snapshot is consistent even if the app is writing at that moment):
       overwrite -> chaosco_backup.db          (fixed name, replaced)
       dated     -> chaosco_backup_<ts>.db     (new copy every time)
2. The attachments in data/uploads (screenshots, PDFs …the DB only stores
   their filenames!) — mirrored INCREMENTALLY to <backup_folder>/uploads/
   in both modes: upload files never change after creation, so only
   missing files are copied; one shared mirror serves every DB snapshot.
   Files deleted in the app linger in the mirror (deliberate — it's a
   backup, not a sync).

last_backup() feeds the dashboard "Last backup: …" reminder line.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

_FIXED_NAME = "chaosco_backup.db"


def run_backup(cfg: dict, mode: str, uploads_dir: Path | None = None) -> dict:
    """Backup DB + uploads into cfg['backup_folder'].
    Returns {ok, path, uploads_new, uploads_total} or {ok: False, error}."""
    folder = (cfg.get("backup_folder") or "").strip()
    if not folder:
        return {"ok": False, "error": "backup_folder is not configured — "
                "set it in settings.local.yaml (e.g. E:\\chaosco_backups)."}
    if mode not in ("overwrite", "dated"):
        return {"ok": False, "error": f"unknown backup mode: {mode}"}
    dest_dir = Path(folder)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"cannot create {dest_dir}: {exc}"}

    if mode == "overwrite":
        dest = dest_dir / _FIXED_NAME
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        dest = dest_dir / f"chaosco_backup_{ts}.db"

    try:
        src = sqlite3.connect(cfg["database_path"])
        try:
            dst = sqlite3.connect(dest)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"backup failed: {exc}"}

    new_files = total = 0
    if uploads_dir is not None and Path(uploads_dir).is_dir():
        mirror = dest_dir / "uploads"
        mirror.mkdir(exist_ok=True)
        for f in Path(uploads_dir).iterdir():
            if not f.is_file():
                continue
            total += 1
            target = mirror / f.name
            if not target.exists():
                shutil.copy2(f, target)
                new_files += 1
    return {"ok": True, "path": str(dest),
            "uploads_new": new_files, "uploads_total": total}


def last_backup(cfg: dict) -> dict | None:
    """Newest chaosco_backup*.db in the backup folder → {path, date,
    days_ago}; None when unconfigured, missing, or empty."""
    folder = (cfg.get("backup_folder") or "").strip()
    if not folder or not Path(folder).is_dir():
        return None
    backups = list(Path(folder).glob("chaosco_backup*.db"))
    if not backups:
        return None
    newest = max(backups, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(newest.stat().st_mtime)
    return {"path": str(newest),
            "date": mtime.strftime("%Y-%m-%d %H:%M"),
            "days_ago": (datetime.now().date() - mtime.date()).days}
