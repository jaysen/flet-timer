"""What the app remembers between runs, e.g. the profile last picked.

Unlike the config, the app writes this itself, to ``$XDG_STATE_HOME/tokolog-flet/state.json``
(``~/.local/state`` if unset). Losing it is harmless, so problems reading or writing it
are ignored.
"""

import json
import os
from pathlib import Path


def state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "tokolog-flet" / "state.json"


def load_last_profile(path: Path | None = None) -> str:
    """The profile last picked; empty if none was saved or the file can't be read."""
    try:
        data = json.loads((path or state_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    profile = data.get("profile") if isinstance(data, dict) else None
    return profile if isinstance(profile, str) else ""


def save_last_profile(profile: str, path: Path | None = None) -> None:
    path = path or state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"profile": profile}) + "\n", encoding="utf-8")
    except OSError:
        pass
