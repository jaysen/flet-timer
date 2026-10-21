from pathlib import Path

import pytest

from flet_timer.config import DEFAULT_MINUTES, Config, ConfigError, config_path, load_config


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_missing_file_uses_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.toml") == Config()
    assert Config().default_minutes == DEFAULT_MINUTES


def test_missing_key_uses_default(tmp_path: Path) -> None:
    assert load_config(write(tmp_path, "[timer]\n")) == Config()


def test_reads_default_minutes(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, "[timer]\ndefault_minutes = 25\n"))
    assert config.default_minutes == 25
    assert config.default_seconds == 1500


def test_accepts_fractional_minutes(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, "[timer]\ndefault_minutes = 1.5\n"))
    assert config.default_seconds == 90


@pytest.mark.parametrize("value", ["0", "-1", '"25"', "true"])
def test_rejects_invalid_minutes(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match="default_minutes"):
        load_config(write(tmp_path, f"[timer]\ndefault_minutes = {value}\n"))


def test_rejects_non_table_section(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"\[timer\]"):
        load_config(write(tmp_path, "timer = 5\n"))


def test_rejects_malformed_toml(tmp_path: Path) -> None:
    path = write(tmp_path, "[timer\n")
    with pytest.raises(ConfigError, match=str(path)):
        load_config(path)


def test_config_path_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "flet-timer" / "config.toml"


def test_config_path_falls_back_to_dot_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config_path() == Path.home() / ".config" / "flet-timer" / "config.toml"
