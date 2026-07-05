"""Config loading: settings.local.yaml MERGES over settings.yaml (local wins,
base fills the gaps) — the old replace-behavior meant every new setting had
to be copied into the local file by hand."""
import pytest

from app import config_loader


@pytest.fixture()
def cfg_dir(tmp_path, monkeypatch):
    base = tmp_path / "settings.yaml"
    local = tmp_path / "settings.local.yaml"
    base.write_text(
        "filename_stem: stem\ndatabase_path: data/x.db\nskiplog_folder: out\n"
        "new_feature_key: from_base\nshared_key: base_value\n", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_DEFAULT_CONFIG", base)
    monkeypatch.setattr(config_loader, "_LOCAL_CONFIG", local)
    return base, local


def test_base_only(cfg_dir):
    cfg = config_loader.load_config()
    assert cfg["new_feature_key"] == "from_base"


def test_local_merges_over_base(cfg_dir):
    _, local = cfg_dir
    local.write_text("shared_key: local_wins\nonly_local: yes\n", encoding="utf-8")
    cfg = config_loader.load_config()
    assert cfg["shared_key"] == "local_wins"       # local overrides
    assert cfg["new_feature_key"] == "from_base"   # base still visible (the fix)
    assert cfg["only_local"] is True     # YAML parses bare `yes` as boolean
    assert cfg["filename_stem"] == "stem"          # required keys from base suffice


def test_explicit_path_bypasses_merge(cfg_dir, tmp_path):
    other = tmp_path / "other.yaml"
    other.write_text(
        "filename_stem: o\ndatabase_path: o.db\nskiplog_folder: o\n", encoding="utf-8")
    assert config_loader.load_config(other)["filename_stem"] == "o"
