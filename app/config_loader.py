"""Load and validate settings.yaml (or settings.local.yaml if present)."""
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


def load_config(path: Path | None = None) -> dict:
    # Explicit path wins; otherwise prefer local override if it exists.
    config_path = Path(path) if path else (_LOCAL_CONFIG if _LOCAL_CONFIG.exists() else _DEFAULT_CONFIG)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    missing = [k for k in _REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")
    return cfg
