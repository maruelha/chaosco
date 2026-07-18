"""DB + uploads backup (2026-07-18) — app/backup.py + POST /backup.

What must hold:
- overwrite mode writes/replaces chaosco_backup.db; dated mode a new
  timestamped copy each run
- the copy is a REAL consistent SQLite snapshot (data readable)
- uploads (screenshots/files — the DB only stores filenames!) are
  mirrored incrementally to <backup_folder>/uploads in both modes:
  missing files copied, existing skipped, deleted-in-app files linger
- last_backup() feeds the dashboard reminder (newest backup, days ago)
- unconfigured backup_folder or unknown mode -> ok:False with a message
"""
import sqlite3
from pathlib import Path

import pytest

from app import database
from app.backup import last_backup, run_backup
import app.web_home as web_home
from app.web import app


@pytest.fixture()
def cfg(tmp_path):
    db_path = tmp_path / "src.db"
    database.init_db(db_path).close()
    conn = database.get_connection(db_path)
    try:
        database.add_note(conn, "input", "inbox", "backup me", "content")
    finally:
        conn.close()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "shot1.png").write_bytes(b"png1")
    c = {"database_path": str(db_path), "backup_folder": str(tmp_path / "ext")}
    c["_uploads"] = uploads
    return c


def test_modes_snapshot_and_uploads_mirror(cfg):
    d = run_backup(cfg, "overwrite", uploads_dir=cfg["_uploads"])
    assert d["ok"] and d["path"].endswith("chaosco_backup.db")
    assert d["uploads_new"] == 1 and d["uploads_total"] == 1
    assert (Path(cfg["backup_folder"]) / "uploads" / "shot1.png").exists()

    # snapshot is a real DB with the data
    check = sqlite3.connect(d["path"])
    try:
        assert check.execute("SELECT heading FROM notes").fetchone()[0] == "backup me"
    finally:
        check.close()

    # incremental: existing file skipped, new file copied; overwrite reuses name
    (cfg["_uploads"] / "shot2.pdf").write_bytes(b"pdf")
    d2 = run_backup(cfg, "overwrite", uploads_dir=cfg["_uploads"])
    assert d2["path"] == d["path"]
    assert d2["uploads_new"] == 1 and d2["uploads_total"] == 2

    # deleted-in-app files linger in the mirror (backup, not sync)
    (cfg["_uploads"] / "shot1.png").unlink()
    d3 = run_backup(cfg, "dated", uploads_dir=cfg["_uploads"])
    assert d3["ok"] and "chaosco_backup_" in d3["path"]
    assert (Path(cfg["backup_folder"]) / "uploads" / "shot1.png").exists()

    backups = list(Path(cfg["backup_folder"]).glob("chaosco_backup*.db"))
    assert len(backups) == 2                      # fixed + one dated


def test_last_backup_reminder(cfg):
    assert last_backup(cfg) is None               # folder not created yet
    run_backup(cfg, "overwrite", uploads_dir=cfg["_uploads"])
    info = last_backup(cfg)
    assert info["days_ago"] == 0
    assert info["path"].endswith("chaosco_backup.db")
    assert last_backup({**cfg, "backup_folder": ""}) is None


def test_unconfigured_and_bad_mode(cfg):
    assert "not configured" in run_backup({**cfg, "backup_folder": ""}, "dated")["error"]
    assert "unknown backup mode" in run_backup(cfg, "wat")["error"]


def test_route_uses_config(cfg, monkeypatch):
    monkeypatch.setitem(web_home._cfg, "database_path", cfg["database_path"])
    monkeypatch.setitem(web_home._cfg, "backup_folder", cfg["backup_folder"])
    monkeypatch.setattr(web_home, "_UPLOAD_FOLDER", cfg["_uploads"])
    d = app.test_client().post("/backup", data={"mode": "dated"}).get_json()
    assert d["ok"] and "chaosco_backup_" in d["path"]
    assert d["uploads_total"] == 1
