"""User settings, read from a TOML file.

The file lives at ``$XDG_CONFIG_HOME/tokolog-flet/config.toml`` (``~/.config`` if unset).
``$TOKOLOG_FLET_CONFIG`` overrides that path, e.g. to use a local file while developing.
It is optional: a missing file or missing keys fall back to the defaults below.
"""

import json
import os
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from tokolog_flet.log import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_FILE,
    DEFAULT_LINE_FORMAT,
    DEFAULT_TIME_FORMAT,
    FILE_PLACEHOLDERS,
    LINE_PLACEHOLDERS,
    template_error,
)

DEFAULT_MINUTES = 25


class ConfigError(Exception):
    """The config file exists but cannot be used."""


def default_log_folder() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "tokolog-flet" / "log"


@dataclass(frozen=True)
class Profile:
    """Timer default and log settings: what a profile can set."""

    default_minutes: float = DEFAULT_MINUTES
    log_folder: Path = field(default_factory=default_log_folder)
    log_file: str = DEFAULT_FILE
    log_date_format: str = DEFAULT_DATE_FORMAT
    log_time_format: str = DEFAULT_TIME_FORMAT
    log_line_format: str = DEFAULT_LINE_FORMAT

    @property
    def default_seconds(self) -> float:
        return self.default_minutes * 60


DEFAULT_PROFILE = "default"


@dataclass(frozen=True)
class Config(Profile):
    """The default profile (``[timer]`` and ``[log]``) plus the named ones."""

    profiles: dict[str, Profile] = field(default_factory=dict, hash=False)

    def profile(self, name: str) -> Profile:
        """The named profile; the default one for ``default`` or a name not in the file."""
        return self.profiles.get(name, self)


def config_path() -> Path:
    if override := os.environ.get("TOKOLOG_FLET_CONFIG"):
        return Path(override)
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "tokolog-flet" / "config.toml"


def read_settings(path: Path) -> dict[str, Any]:
    """The file's raw contents; empty if it does not exist."""
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    return parse_config(read_settings(path), path)


def parse_config(data: dict[str, Any], path: Path) -> Config:
    """Validate raw settings; ``path`` is only used for messages and relative folders."""
    timer = _section(data, "timer", path)
    log = _section(data, "log", path)
    default = _parse_profile(timer, log, Profile(), "timer.", "log.", path)

    profiles: dict[str, Profile] = {}
    for name, table in _section(data, "profiles", path).items():
        if name.strip().lower() == DEFAULT_PROFILE:
            raise ConfigError(f"{path}: profiles.{name}: that name is the built-in profile")
        if not isinstance(table, dict):
            raise ConfigError(f"{path}: [profiles.{name}] must be a table")
        # A profile's keys sit together in one table and override the default's.
        prefix = f"profiles.{name}."
        profiles[name] = _parse_profile(table, table, default, prefix, prefix, path)
    return Config(**vars(default), profiles=profiles)


def _parse_profile(
    timer: dict[str, Any],
    log: dict[str, Any],
    base: Profile,
    timer_key: str,
    log_key: str,
    path: Path,
) -> Profile:
    """``base`` with whatever ``timer`` and ``log`` set; keys in messages get the prefixes."""
    minutes = timer.get("default_minutes", base.default_minutes)
    # bool is an int subclass, so `true` would otherwise pass as 1 minute.
    if isinstance(minutes, bool) or not isinstance(minutes, int | float) or minutes <= 0:
        raise ConfigError(f"{path}: {timer_key}default_minutes must be a positive number")

    folder = log.get("folder")
    if folder is None:
        log_folder = base.log_folder
    elif isinstance(folder, str) and folder:
        # Relative paths are taken from the config file's folder, not wherever the app runs.
        log_folder = path.parent / Path(folder).expanduser()
    else:
        raise ConfigError(f"{path}: {log_key}folder must be a non-empty string")

    file = log.get("file", base.log_file)
    if not _is_filename(file):
        raise ConfigError(f"{path}: {log_key}file must be a non-empty file name, without folders")
    _check_template(file, f"{log_key}file", FILE_PLACEHOLDERS, path)
    # The date ends up in the file name, so it follows the same rules.
    date_format = log.get("date_format", base.log_date_format)
    if not _is_filename(date_format):
        raise ConfigError(
            f"{path}: {log_key}date_format must be a non-empty string, without / or \\"
        )

    time_format = log.get("time_format", base.log_time_format)
    if not isinstance(time_format, str) or not time_format:
        raise ConfigError(f"{path}: {log_key}time_format must be a non-empty string")

    line_format = log.get("line_format", base.log_line_format)
    if not isinstance(line_format, str):
        raise ConfigError(f"{path}: {log_key}line_format must be a string")
    _check_template(line_format, f"{log_key}line_format", LINE_PLACEHOLDERS, path)

    return Profile(
        default_minutes=minutes,
        log_folder=log_folder,
        log_file=file,
        log_date_format=date_format,
        log_time_format=time_format,
        log_line_format=line_format,
    )


def _check_template(template: str, key: str, placeholders: tuple[str, ...], path: Path) -> None:
    if error := template_error(template, placeholders):
        known = ", ".join(f"{{{name}}}" for name in placeholders)
        raise ConfigError(f"{path}: {key}: {error} (available: {known})")


def _is_filename(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not any(c in value for c in "/\\")


def _section(data: dict[str, Any], name: str, path: Path) -> dict[str, Any]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{path}: [{name}] must be a table")
    return section


@dataclass(frozen=True)
class Setting:
    section: str
    name: str
    label: str
    default: str
    help: str

    @property
    def key(self) -> str:
        return f"{self.section}.{self.name}"


def _setting_defaults() -> list[Setting]:
    config = Config()
    return [
        Setting(
            "timer",
            "default_minutes",
            "Default minutes",
            f"{config.default_minutes:g}",
            "Countdown start time; fractions allowed, e.g. 1.5",
        ),
        Setting(
            "log",
            "folder",
            "Folder",
            _tilde(config.log_folder),
            "~ is expanded; relative paths start at the config file's folder",
        ),
        Setting(
            "log",
            "file",
            "File name",
            config.log_file,
            "{date}, {label} and {profile} are replaced",
        ),
        Setting(
            "log",
            "date_format",
            "Date format",
            config.log_date_format,
            "YYYY, YY, MM and DD are replaced",
        ),
        Setting(
            "log",
            "time_format",
            "Time format",
            config.log_time_format,
            "HH, hh (12-hour), mm, ss and AM are replaced",
        ),
        Setting(
            "log",
            "line_format",
            "Line format",
            config.log_line_format,
            "{date} {time} {mode} {event} {elapsed} {display} {label} {profile}",
        ),
    ]


def _tilde(path: Path) -> str:
    try:
        return str(Path("~") / path.relative_to(Path.home()))
    except ValueError:
        return str(path)


SETTINGS = _setting_defaults()


def setting_key(setting: Setting, profile: str = DEFAULT_PROFILE) -> str:
    """Where ``setting`` lives for ``profile``, as config messages name it."""
    return setting.key if profile == DEFAULT_PROFILE else f"profiles.{profile}.{setting.name}"


def profile_names(data: dict[str, Any]) -> list[str]:
    """The named profiles in raw settings, in file order."""
    profiles = data.get("profiles")
    return list(profiles) if isinstance(profiles, dict) else []


def setting_text(data: dict[str, Any], setting: Setting, profile: str = DEFAULT_PROFILE) -> str:
    """What the file sets for ``setting`` as editable text; empty if it is not set."""
    if profile == DEFAULT_PROFILE:
        table = data.get(setting.section)
    else:
        profiles = data.get("profiles")
        table = profiles.get(profile) if isinstance(profiles, dict) else None
    value = table.get(setting.name) if isinstance(table, dict) else None
    return "" if value is None else str(value)


def apply_settings(
    data: dict[str, Any], values: dict[str, str], profile: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    """Copy of ``data`` with each setting in ``values`` (by key) set, or removed if blank.

    The settings go in ``[timer]`` and ``[log]`` for the default profile, otherwise in the
    profile's own table, which is kept even when empty: an empty profile is still one.
    Text is kept as typed: spaces can matter, e.g. at the start of a line format.
    Anything else in ``data`` is kept. Whether the result is valid is for ``parse_config``.
    """
    result = {k: dict(v) if isinstance(v, dict) else v for k, v in data.items()}
    if profile != DEFAULT_PROFILE:
        profiles = result.setdefault("profiles", {})
        if not isinstance(profiles, dict):
            raise ConfigError("[profiles] must be a table")
        table = profiles.get(profile, {})
        if not isinstance(table, dict):
            raise ConfigError(f"[profiles.{profile}] must be a table")
        profiles[profile] = dict(table)
    for setting in SETTINGS:
        if profile == DEFAULT_PROFILE:
            table = result.setdefault(setting.section, {})
            if not isinstance(table, dict):
                raise ConfigError(f"[{setting.section}] must be a table")
        else:
            table = result["profiles"][profile]
        text = values.get(setting.key, "")
        if not text.strip():
            table.pop(setting.name, None)
        elif setting.key == "timer.default_minutes":
            table[setting.name] = _number(text.strip(), setting_key(setting, profile))
        else:
            table[setting.name] = text
    return {k: v for k, v in result.items() if v != {}}


def add_profile(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Copy of ``data`` with an empty profile called ``name``, which must be new."""
    name = name.strip()
    if not name:
        raise ConfigError("A profile needs a name")
    if name.lower() == DEFAULT_PROFILE or name in profile_names(data):
        raise ConfigError(f"There is already a profile called {name}")
    profiles = data.get("profiles", {})
    return {**data, "profiles": {**profiles, name: {}}}


def remove_profile(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Copy of ``data`` without the profile called ``name``."""
    profiles = {k: v for k, v in data.get("profiles", {}).items() if k != name}
    result = {k: v for k, v in data.items() if k != "profiles"}
    return {**result, "profiles": profiles} if profiles else result


def _number(text: str, key: str) -> int | float:
    try:
        number = float(text)
    except ValueError:
        raise ConfigError(f"{key} must be a positive number") from None
    return int(number) if number.is_integer() else number


def save_settings(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` as TOML. Comments in an existing file are not kept."""
    text = dumps_toml(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def dumps_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    _dump_table(data, "", lines)
    return "\n".join(lines) + "\n" if lines else ""


def _dump_table(table: dict[str, Any], prefix: str, lines: list[str]) -> None:
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    tables = {k: v for k, v in table.items() if isinstance(v, dict)}
    if prefix and (scalars or not tables):
        lines += ["", f"[{prefix}]"]
    for key, value in scalars.items():
        lines.append(f"{_dump_key(key)} = {_dump_value(value)}")
    for key, value in tables.items():
        _dump_table(value, f"{prefix}.{_dump_key(key)}" if prefix else _dump_key(key), lines)


def _dump_key(key: str) -> str:
    return (
        key
        if key and all(c.isalnum() or c in "_-" for c in key)
        else json.dumps(key, ensure_ascii=False)
    )


def _dump_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_dump_value(v) for v in value) + "]"
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    raise ConfigError(f"cannot write a {type(value).__name__} value")
