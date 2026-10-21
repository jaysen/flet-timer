"""User settings, read from a TOML file.

The file lives at ``$XDG_CONFIG_HOME/flet-timer/config.toml`` (``~/.config`` if unset).
``$FLET_TIMER_CONFIG`` overrides that path, e.g. to use a local file while developing.
It is optional: a missing file or missing keys fall back to the defaults below.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flet_timer.log import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_FILE,
    FILE_PLACEHOLDERS,
    unknown_placeholders,
)

DEFAULT_MINUTES = 5


class ConfigError(Exception):
    """The config file exists but cannot be used."""


def default_log_folder() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "flet-timer" / "log"


@dataclass(frozen=True)
class Config:
    default_minutes: float = DEFAULT_MINUTES
    log_folder: Path = field(default_factory=default_log_folder)
    log_file: str = DEFAULT_FILE
    log_date_format: str = DEFAULT_DATE_FORMAT

    @property
    def default_seconds(self) -> float:
        return self.default_minutes * 60


def config_path() -> Path:
    if override := os.environ.get("FLET_TIMER_CONFIG"):
        return Path(override)
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "flet-timer" / "config.toml"


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return Config()
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e

    timer = _section(data, "timer", path)
    minutes = timer.get("default_minutes", DEFAULT_MINUTES)
    # bool is an int subclass, so `true` would otherwise pass as 1 minute.
    if isinstance(minutes, bool) or not isinstance(minutes, int | float) or minutes <= 0:
        raise ConfigError(f"{path}: timer.default_minutes must be a positive number")

    log = _section(data, "log", path)
    folder = log.get("folder")
    if folder is None:
        log_folder = default_log_folder()
    elif isinstance(folder, str) and folder:
        # Relative paths are taken from the config file's folder, not wherever the app runs.
        log_folder = path.parent / Path(folder).expanduser()
    else:
        raise ConfigError(f"{path}: log.folder must be a non-empty string")

    file = log.get("file", DEFAULT_FILE)
    if not _is_filename(file):
        raise ConfigError(f"{path}: log.file must be a non-empty file name, without folders")
    if unknown := unknown_placeholders(file, FILE_PLACEHOLDERS):
        known = ", ".join(f"{{{name}}}" for name in sorted(FILE_PLACEHOLDERS))
        raise ConfigError(f"{path}: log.file has unknown placeholder {{{unknown[0]}}} ({known})")
    # The date ends up in the file name, so it follows the same rules.
    date_format = log.get("date_format", DEFAULT_DATE_FORMAT)
    if not _is_filename(date_format):
        raise ConfigError(f"{path}: log.date_format must be a non-empty string, without / or \\")

    return Config(
        default_minutes=minutes,
        log_folder=log_folder,
        log_file=file,
        log_date_format=date_format,
    )


def _is_filename(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not any(c in value for c in "/\\")


def _section(data: dict[str, Any], name: str, path: Path) -> dict[str, Any]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{path}: [{name}] must be a table")
    return section
