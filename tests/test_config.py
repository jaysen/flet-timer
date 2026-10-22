from pathlib import Path

import pytest

from tokolog_flet.config import (
    DEFAULT_MINUTES,
    SETTINGS,
    Config,
    ConfigError,
    Profile,
    add_profile,
    apply_settings,
    config_path,
    dumps_toml,
    load_config,
    parse_config,
    profile_names,
    read_settings,
    remove_profile,
    save_settings,
    setting_key,
    setting_text,
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_missing_file_uses_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.toml") == Config()
    assert Config().default_minutes == DEFAULT_MINUTES


def test_missing_key_uses_default(tmp_path: Path) -> None:
    assert load_config(write(tmp_path, "[profiles.default]\n")) == Config()


def test_reads_default_minutes(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, "[profiles.default]\ndefault_minutes = 25\n"))
    assert config.default_minutes == 25
    assert config.default_seconds == 1500


def test_accepts_fractional_minutes(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, "[profiles.default]\ndefault_minutes = 1.5\n"))
    assert config.default_seconds == 90


@pytest.mark.parametrize("value", ["0", "-1", '"25"', "true"])
def test_rejects_invalid_minutes(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.default_minutes"):
        load_config(write(tmp_path, f"[profiles.default]\ndefault_minutes = {value}\n"))


def test_rejects_malformed_toml(tmp_path: Path) -> None:
    path = write(tmp_path, "[timer\n")
    with pytest.raises(ConfigError, match=str(path)):
        load_config(path)


@pytest.fixture(autouse=True)
def no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKOLOG_FLET_CONFIG", raising=False)


def test_config_path_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("TOKOLOG_FLET_CONFIG", str(tmp_path / "dev.toml"))
    assert config_path() == tmp_path / "dev.toml"


def test_config_path_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "tokolog-flet" / "config.toml"


def test_config_path_falls_back_to_dot_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config_path() == Path.home() / ".config" / "tokolog-flet" / "config.toml"


def test_log_folder_defaults_to_xdg_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert load_config(tmp_path / "nope.toml").log_folder == tmp_path / "tokolog-flet" / "log"


def test_log_folder_relative_to_config_file(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[profiles.default]\nfolder = "logs"\n'))
    assert config.log_folder == tmp_path / "logs"


def test_log_folder_expands_home(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[profiles.default]\nfolder = "~/wiki/log"\n'))
    assert config.log_folder == Path.home() / "wiki" / "log"


@pytest.mark.parametrize("value", ['""', "5"])
def test_rejects_invalid_log_folder(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.folder"):
        load_config(write(tmp_path, f"[profiles.default]\nfolder = {value}\n"))


def test_log_file_and_date_format_default(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.toml")
    assert (config.log_file, config.log_date_format) == ("{date}.log", "YYYY-MM-DD")


def test_reads_log_file_and_date_format(tmp_path: Path) -> None:
    config = load_config(
        write(tmp_path, '[profiles.default]\nfile = "flet-{date}.md"\ndate_format = "YYYYMMDD"\n')
    )
    assert (config.log_file, config.log_date_format) == ("flet-{date}.md", "YYYYMMDD")


@pytest.mark.parametrize("value", ['""', '"logs/{date}.md"', "5"])
def test_rejects_invalid_log_file(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.file"):
        load_config(write(tmp_path, f"[profiles.default]\nfile = {value}\n"))


def test_rejects_unknown_placeholder(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.file: unknown placeholder \{dat\}"):
        load_config(write(tmp_path, '[profiles.default]\nfile = "flet-{dat}.md"\n'))


def test_line_format_default(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.toml")
    assert config.log_line_format == "{time}  {mode:<9}  {event:<6}  {elapsed}"


def test_accepts_label_placeholder(tmp_path: Path) -> None:
    config = load_config(
        write(tmp_path, '[profiles.default]\nfile = "{date}-{label}.md"\nline_format = "{label}"\n')
    )
    assert (config.log_file, config.log_line_format) == ("{date}-{label}.md", "{label}")


def test_reads_line_format(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[profiles.default]\nline_format = " - {time} {event}"\n'))
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
    with pytest.raises(ConfigError, match=rf"profiles\.default\.line_format.*{error}"):
        load_config(write(tmp_path, f"[profiles.default]\nline_format = {value}\n"))


@pytest.mark.parametrize("value", ['""', '"YYYY/MM-DD"', "5"])
def test_rejects_invalid_date_format(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.date_format"):
        load_config(write(tmp_path, f"[profiles.default]\ndate_format = {value}\n"))


def test_time_format_default(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.toml").log_time_format == "HH:mm:ss"


def test_reads_time_format(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[profiles.default]\ntime_format = "hh:mm AM"\n'))
    assert config.log_time_format == "hh:mm AM"


@pytest.mark.parametrize("value", ['""', "5"])
def test_rejects_invalid_time_format(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.time_format"):
        load_config(write(tmp_path, f"[profiles.default]\ntime_format = {value}\n"))


def test_read_settings_missing_file_is_empty(tmp_path: Path) -> None:
    assert read_settings(tmp_path / "nope.toml") == {}


def test_setting_text_blank_when_unset() -> None:
    minutes = SETTINGS[0]
    assert setting_text({}, minutes) == ""
    assert setting_text({"profiles": {"default": {"default_minutes": 25}}}, minutes) == "25"


def test_apply_settings_sets_and_clears() -> None:
    data = {"top": 1, "profiles": {"default": {"default_minutes": 25, "file": "a.md", "x": 1}}}
    values = {"default_minutes": " ", "file": "b.md", "folder": "logs"}
    assert apply_settings(data, values) == {
        "top": 1,
        "profiles": {"default": {"file": "b.md", "x": 1, "folder": "logs"}},
    }
    assert data["profiles"]["default"]["file"] == "a.md"  # input untouched


def test_apply_settings_minutes_become_numbers() -> None:
    assert apply_settings({}, {"default_minutes": "25"}) == {
        "profiles": {"default": {"default_minutes": 25}}
    }
    assert apply_settings({}, {"default_minutes": "1.5"}) == {
        "profiles": {"default": {"default_minutes": 1.5}}
    }
    with pytest.raises(ConfigError, match=r"profiles\.default\.default_minutes"):
        apply_settings({}, {"default_minutes": "abc"})


def test_apply_settings_keeps_spaces() -> None:
    values = {"line_format": " - {time} ", "default_minutes": " 25 "}
    assert apply_settings({}, values) == {
        "profiles": {"default": {"default_minutes": 25, "line_format": " - {time} "}}
    }


def test_apply_settings_all_blank_is_empty() -> None:
    assert apply_settings({"profiles": {"default": {"default_minutes": 3}}}, {}) == {}


def test_parse_config_validates_in_memory(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.default\.file"):
        parse_config({"profiles": {"default": {"file": "a/b"}}}, tmp_path / "config.toml")


def test_save_round_trips(tmp_path: Path) -> None:
    data = {
        "top": "x",
        "profiles": {
            "default": {"default_minutes": 1.5, "line_format": '{time} "q" \\ é'},
            "a b": {"file": "{date}.md", "tags": ["a", "b"]},
        },
        "deep": {"a": {"b": True}},
    }
    path = tmp_path / "sub" / "config.toml"
    save_settings(path, data)
    assert read_settings(path) == data
    assert not path.with_name("config.toml.tmp").exists()


def test_dumps_empty_is_empty() -> None:
    assert dumps_toml({}) == ""


def test_dumps_rejects_unwritable_value() -> None:
    with pytest.raises(ConfigError, match="cannot write"):
        dumps_toml({"a": None})


def test_no_profiles_by_default(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.toml")
    assert config.profiles == {}
    assert config.profile("default") is config


def test_profile_overrides_default(tmp_path: Path) -> None:
    config = load_config(
        write(
            tmp_path,
            "[profiles.default]\ndefault_minutes = 25\n"
            'file = "{date}.md"\nline_format = "- {time} {event}"\n'
            '[profiles.work]\ndefault_minutes = 50\nfolder = "work"\nfile = "work-{date}.csv"\n',
        )
    )
    work = config.profile("work")
    assert (work.default_minutes, work.log_folder, work.log_file) == (
        50,
        tmp_path / "work",
        "work-{date}.csv",
    )
    # What the profile leaves out comes from the default profile, not the built-in values.
    assert work.log_line_format == "- {time} {event}"
    assert config.profile("missing") is config


def test_empty_profile_matches_default(tmp_path: Path) -> None:
    config = load_config(
        write(tmp_path, '[profiles.default]\nfile = "{date}.md"\n[profiles.focus]\n')
    )
    assert config.profile("focus") == Profile(log_file="{date}.md")


def test_profile_error_names_profile_key(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.work\.line_format: unknown placeholder"):
        load_config(write(tmp_path, '[profiles.work]\nline_format = "{nope}"\n'))
    with pytest.raises(ConfigError, match=r"profiles\.work\.default_minutes"):
        load_config(write(tmp_path, "[profiles.work]\ndefault_minutes = 0\n"))


@pytest.mark.parametrize("text", ["profiles = 1\n", "[profiles]\nwork = 1\n"])
def test_rejects_non_table_profiles(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError, match=r"\[profiles"):
        load_config(write(tmp_path, text))


def test_rejects_default_as_profile_name(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"profiles\.Default: the default profile"):
        load_config(write(tmp_path, "[profiles.Default]\n"))


def test_setting_text_for_profile() -> None:
    file = next(s for s in SETTINGS if s.name == "file")
    data = {"profiles": {"default": {"file": "a.md"}, "work": {"file": "w.md"}, "focus": {}}}
    assert setting_text(data, file) == "a.md"
    assert setting_text(data, file, "work") == "w.md"
    assert setting_text(data, file, "focus") == ""
    assert setting_text(data, file, "missing") == ""


def test_apply_settings_to_profile() -> None:
    data = {"profiles": {"default": {"file": "a.md"}, "work": {"file": "w.md", "extra": 1}}}
    values = {"file": "", "line_format": "{event}", "default_minutes": "50"}
    assert apply_settings(data, values, "work") == {
        "profiles": {
            "default": {"file": "a.md"},
            "work": {"extra": 1, "line_format": "{event}", "default_minutes": 50},
        }
    }
    assert data["profiles"]["work"]["file"] == "w.md"  # input untouched


def test_apply_settings_keeps_empty_profile() -> None:
    assert apply_settings({}, {}, "focus") == {"profiles": {"focus": {}}}


def test_apply_settings_profile_error_names_profile() -> None:
    with pytest.raises(ConfigError, match=r"profiles\.work\.default_minutes"):
        apply_settings({}, {"default_minutes": "abc"}, "work")


def test_add_and_remove_profile() -> None:
    default = {"profiles": {"default": {"file": "a.md"}}}
    data = add_profile(default, " work ")
    assert data == {"profiles": {"default": {"file": "a.md"}, "work": {}}}
    assert profile_names(add_profile(data, "focus")) == ["work", "focus"]
    assert remove_profile(data, "work") == default
    assert remove_profile(add_profile({}, "work"), "work") == {}


@pytest.mark.parametrize("name", ["", "  ", "work", "Default"])
def test_add_profile_rejects_taken_or_blank_name(name: str) -> None:
    with pytest.raises(ConfigError):
        add_profile({"profiles": {"work": {}}}, name)


def test_setting_key() -> None:
    file = next(s for s in SETTINGS if s.name == "file")
    assert setting_key(file) == "profiles.default.file"
    assert setting_key(file, "work") == "profiles.work.file"


def test_default_label(tmp_path: Path) -> None:
    config = load_config(
        write(tmp_path, '[profiles.default]\ndefault_label = " journal "\n[profiles.work]\n')
    )
    assert config.default_label == "journal"
    assert config.profile("work").default_label == "journal"
    assert Config().default_label == ""
    with pytest.raises(ConfigError, match=r"profiles\.default\.default_label"):
        load_config(write(tmp_path, "[profiles.default]\ndefault_label = 5\n"))
