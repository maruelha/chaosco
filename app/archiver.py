"""Archive the source Excel file — read/copy only, never modifies the source.

Config keys (all optional):
    archive_enabled : bool  — default True
    archive_mode    : str   — "once_per_file" | "always"  — default "once_per_file"
    archive_folder  : str   — default "archive"

once_per_file: archives the file only if its SHA-256 content hash has not been seen
before in archive_folder. Repeated runs on the same unchanged download → archived once.
A genuinely new daily export → archived again.

always: archives on every run with a fresh timestamp.

Raises RuntimeError if archive_enabled is True and the copy fails.
Caller (main.py) must treat this as fatal and stop before any DB write.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

_DEFAULT_MODE = "once_per_file"
_DEFAULT_FOLDER = "archive"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _timestamped_name(xlsx_path: Path) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    return f"{ts}_{xlsx_path.name}"


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
            for existing in sorted(archive_folder.glob("*.xlsx")):
                if _sha256(existing) == source_hash:
                    return {
                        "status": "skipped_duplicate",
                        "archive_path": None,
                        "matched_archive": existing.name,
                    }

        dest = archive_folder / _timestamped_name(xlsx_path)
        shutil.copy2(str(xlsx_path), str(dest))

        return {"status": "archived", "archive_path": dest, "matched_archive": None}

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Archiving failed: {exc}") from exc
