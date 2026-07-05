"""Load settings.yaml, with settings.local.yaml MERGED on top (local wins).

Since 2026-07-05 the local file no longer replaces the base file — it only
overrides the keys it contains. New settings added to settings.yaml are
therefore picked up everywhere without copying them into the local file.
"""
from pathlib import Path
import yaml

_REQUIRED = (
    "filename_stem",
    "database_path",
    "skiplog_folder",
)

_CONFIG_DIR    = Path(__file__).parent.parent / "config"
_DEFAULT_CONFIG = _CONFIG_DIR / "settings.yaml"
_LOCAL_CONFIG   = _CONFIG_DIR / "settings.local.yaml"


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(path: Path | None = None) -> dict:
    if path:                               # explicit path wins outright (tests, CLI)
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        cfg = _read(config_path)
    else:
        if not _DEFAULT_CONFIG.exists():
            raise FileNotFoundError(f"Config file not found: {_DEFAULT_CONFIG}")
        cfg = _read(_DEFAULT_CONFIG)
        if _LOCAL_CONFIG.exists():
            cfg.update(_read(_LOCAL_CONFIG))   # local overrides, base fills gaps

    missing = [k for k in _REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")
    return cfg
