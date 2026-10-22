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


@pytest.fixture(autouse=True)
def no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLET_TIMER_CONFIG", raising=False)


def test_config_path_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("FLET_TIMER_CONFIG", str(tmp_path / "dev.toml"))
    assert config_path() == tmp_path / "dev.toml"


def test_config_path_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "flet-timer" / "config.toml"


def test_config_path_falls_back_to_dot_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config_path() == Path.home() / ".config" / "flet-timer" / "config.toml"


def test_log_folder_defaults_to_xdg_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert load_config(tmp_path / "nope.toml").log_folder == tmp_path / "flet-timer" / "log"


def test_log_folder_relative_to_config_file(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[log]\nfolder = "logs"\n'))
    assert config.log_folder == tmp_path / "logs"


def test_log_folder_expands_home(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[log]\nfolder = "~/wiki/log"\n'))
    assert config.log_folder == Path.home() / "wiki" / "log"


@pytest.mark.parametrize("value", ['""', "5"])
def test_rejects_invalid_log_folder(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"log\.folder"):
        load_config(write(tmp_path, f"[log]\nfolder = {value}\n"))


def test_log_file_and_date_format_default(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.toml")
    assert (config.log_file, config.log_date_format) == ("{date}.log", "YYYY-MM-DD")


def test_reads_log_file_and_date_format(tmp_path: Path) -> None:
    config = load_config(
        write(tmp_path, '[log]\nfile = "flet-{date}.md"\ndate_format = "YYYYMMDD"\n')
    )
    assert (config.log_file, config.log_date_format) == ("flet-{date}.md", "YYYYMMDD")


@pytest.mark.parametrize("value", ['""', '"logs/{date}.md"', "5"])
def test_rejects_invalid_log_file(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"log\.file"):
        load_config(write(tmp_path, f"[log]\nfile = {value}\n"))


def test_rejects_unknown_placeholder(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"log\.file: unknown placeholder \{dat\}"):
        load_config(write(tmp_path, '[log]\nfile = "flet-{dat}.md"\n'))


def test_line_format_default(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.toml")
    assert config.log_line_format == "{time}  {mode:<9}  {event:<6}  {elapsed}"


def test_reads_line_format(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[log]\nline_format = " - {time} {event}"\n'))
    assert config.log_line_format == " - {time} {event}"


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ('"{state}"', r"unknown placeholder \{state\}"),
        ('"{time"', "expected '}'"),
        ("5", "must be a string"),
    ],
)
def test_rejects_invalid_line_format(tmp_path: Path, value: str, error: str) -> None:
    with pytest.raises(ConfigError, match=rf"log\.line_format.*{error}"):
        load_config(write(tmp_path, f"[log]\nline_format = {value}\n"))


@pytest.mark.parametrize("value", ['""', '"YYYY/MM-DD"', "5"])
def test_rejects_invalid_date_format(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"log\.date_format"):
        load_config(write(tmp_path, f"[log]\ndate_format = {value}\n"))
