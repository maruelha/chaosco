"""Archive the source Excel file — read/copy only, never modifies the source.

Config keys (all optional):
    archive_enabled : bool  — default True
    archive_mode    : str   — "once_per_file" | "always"  — default "once_per_file"
    archive_folder  : str   — default "archive"

once_per_file: archives the file only if its SHA-256 content hash has not been seen
before. A manifest file (archive_folder/hashes.txt) stores one hash+filename per line
so existing archives are never re-read on subsequent runs.

always: archives on every run with a fresh timestamp.

Raises RuntimeError if archive_enabled is True and the copy fails.
Caller (importer.py) treats this as fatal and stops before any DB write.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

_DEFAULT_MODE = "once_per_file"
_DEFAULT_FOLDER = "archive"
_MANIFEST = "hashes.txt"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _timestamped_name(xlsx_path: Path) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    return f"{ts}_{xlsx_path.name}"


def _load_manifest(archive_folder: Path) -> dict[str, str]:
    """Return {hash: filename} from hashes.txt, or empty dict if it doesn't exist."""
    manifest_path = archive_folder / _MANIFEST
    if not manifest_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            parts = line.split(None, 1)
            if len(parts) == 2:
                result[parts[0]] = parts[1]
    return result


def _append_manifest(archive_folder: Path, file_hash: str, filename: str) -> None:
    manifest_path = archive_folder / _MANIFEST
    with manifest_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{file_hash}  {filename}\n")


def archive_file(xlsx_path: Path, cfg: dict) -> dict:
    """Copy xlsx_path to the archive folder according to config.

    Returns:
        {
            "status":          "archived" | "skipped_duplicate" | "disabled",
            "archive_path":    Path | None,   # set when status == "archived"
            "matched_archive": str  | None,   # set when status == "skipped_duplicate"
        }

    Raises RuntimeError if archive_enabled is True and archiving fails.
    """
    if not cfg.get("archive_enabled", True):
        return {"status": "disabled", "archive_path": None, "matched_archive": None}

    mode = cfg.get("archive_mode", _DEFAULT_MODE)
    archive_folder = Path(cfg.get("archive_folder", _DEFAULT_FOLDER))

    try:
        archive_folder.mkdir(parents=True, exist_ok=True)

        if mode == "once_per_file":
            source_hash = _sha256(xlsx_path)
            manifest = _load_manifest(archive_folder)
            if source_hash in manifest:
                return {
                    "status": "skipped_duplicate",
                    "archive_path": None,
                    "matched_archive": manifest[source_hash],
                }

        dest_name = _timestamped_name(xlsx_path)
        dest = archive_folder / dest_name
        shutil.copy2(str(xlsx_path), str(dest))

        if mode == "once_per_file":
            _append_manifest(archive_folder, source_hash, dest_name)

        return {"status": "archived", "archive_path": dest, "matched_archive": None}

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Archiving failed: {exc}") from exc
