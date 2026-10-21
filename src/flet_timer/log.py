"""Activity log: one line per timer event, in a file named after the date.

Events are worked out from state changes, so the UI only has to report the timer's
state before and after each action, and on every tick.
"""

import os
import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from flet_timer.timer import State, Stopwatch, format_seconds

DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_FILE = "{date}.log"

DATE_TOKENS = re.compile("YYYY|YY|MM|DD")
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
FILE_PLACEHOLDERS = {"date"}

EVENTS: dict[tuple[State, State], str] = {
    (State.IDLE, State.RUNNING): "start",
    (State.PAUSED, State.RUNNING): "resume",
    (State.RUNNING, State.PAUSED): "pause",
    (State.RUNNING, State.IDLE): "stop",
    (State.PAUSED, State.IDLE): "stop",
    (State.RUNNING, State.FINISHED): "finish",
}


def format_date(date_format: str, day: date) -> str:
    """Replace YYYY, YY, MM and DD, e.g. ``YYYY-MM-DD`` -> ``2026-10-21``."""
    tokens = {"YYYY": f"{day:%Y}", "YY": f"{day:%y}", "MM": f"{day:%m}", "DD": f"{day:%d}"}
    return DATE_TOKENS.sub(lambda m: tokens[m[0]], date_format)


def unknown_placeholders(template: str, known: set[str]) -> list[str]:
    return [name for name in PLACEHOLDER.findall(template) if name not in known]


def log_filename(file: str, date_format: str, day: date) -> str:
    """Fill ``{date}`` in ``file``, e.g. ``flet-{date}.md`` -> ``flet-2026-10-21.md``."""
    return file.replace("{date}", format_date(date_format, day))


class EventLog:
    """Appends ``HH:MM:SS  mode  event  elapsed`` lines to a dated file in ``folder``."""

    def __init__(
        self,
        folder: Path,
        file: str = DEFAULT_FILE,
        date_format: str = DEFAULT_DATE_FORMAT,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.folder = folder
        self.file = file
        self.date_format = date_format
        self.now = now
        self._seen: dict[str, tuple[State, float]] = {}

    def update(self, mode: str, timer: Stopwatch) -> None:
        state, elapsed = timer.state, timer.elapsed
        before, last_elapsed = self._seen.get(mode, (State.IDLE, 0.0))
        self._seen[mode] = (state, elapsed)
        if event := EVENTS.get((before, state)):
            # A stop has already reset the timer, so report the time it had reached.
            self._write(mode, event, last_elapsed if event == "stop" else elapsed)

    def _write(self, mode: str, event: str, elapsed: float) -> None:
        stamp = self.now()
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / log_filename(self.file, self.date_format, stamp)
        line = f"{stamp:%H:%M:%S}  {mode:<9}  {event:<6}  {format_seconds(elapsed)}\n"
        # The file may be a note edited by hand; don't glue the line onto its last one.
        if not _ends_with_newline(path):
            line = "\n" + line
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def _ends_with_newline(path: Path) -> bool:
    """True for a missing or empty file too: nothing to separate from."""
    try:
        with path.open("rb") as f:
            if f.seek(0, os.SEEK_END) == 0:
                return True
            f.seek(-1, os.SEEK_END)
            return f.read(1) == b"\n"
    except FileNotFoundError:
        return True
