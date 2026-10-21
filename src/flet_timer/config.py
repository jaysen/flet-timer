"""User settings, read from a TOML file.

The file lives at ``$XDG_CONFIG_HOME/flet-timer/config.toml`` (``~/.config`` if unset).
It is optional: a missing file or missing keys fall back to the defaults below.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MINUTES = 5


class ConfigError(Exception):
    """The config file exists but cannot be used."""


@dataclass(frozen=True)
class Config:
    default_minutes: float = DEFAULT_MINUTES

    @property
    def default_seconds(self) -> float:
        return self.default_minutes * 60


def config_path() -> Path:
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
    return Config(default_minutes=minutes)


def _section(data: dict[str, Any], name: str, path: Path) -> dict[str, Any]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{path}: [{name}] must be a table")
    return section
