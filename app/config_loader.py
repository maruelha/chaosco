"""Load and validate settings.yaml."""
from pathlib import Path
import yaml

_REQUIRED = (
    "downloads_folder",
    "filename_stem",
    "database_path",
    "skiplog_folder",
)

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_config(path: Path | None = None) -> dict:
    config_path = Path(path) if path else _DEFAULT_CONFIG
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    missing = [k for k in _REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")
    return cfg
