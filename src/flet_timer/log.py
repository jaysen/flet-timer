"""Activity log: one line per timer event, in a file named after the date.

Events are worked out from state changes, so the UI only has to report the timer's
state before and after each action, and on every tick.
"""

import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from flet_timer.timer import State, Stopwatch, format_seconds

DEFAULT_NAME = "YYYY-MM-DD"
DEFAULT_EXTENSION = "log"

DATE_TOKENS = re.compile("YYYY|YY|MM|DD")

EVENTS: dict[tuple[State, State], str] = {
    (State.IDLE, State.RUNNING): "start",
    (State.PAUSED, State.RUNNING): "resume",
    (State.RUNNING, State.PAUSED): "pause",
    (State.RUNNING, State.IDLE): "stop",
    (State.PAUSED, State.IDLE): "stop",
    (State.RUNNING, State.FINISHED): "finish",
}


def log_filename(name: str, extension: str, day: date) -> str:
    """Fill the date tokens in ``name``, e.g. ``YYYYMMDD`` and ``md`` -> ``20261021.md``."""
    tokens = {"YYYY": f"{day:%Y}", "YY": f"{day:%y}", "MM": f"{day:%m}", "DD": f"{day:%d}"}
    stem = DATE_TOKENS.sub(lambda m: tokens[m[0]], name)
    return f"{stem}.{extension}" if extension else stem


class EventLog:
    """Appends ``HH:MM:SS  mode  event  elapsed`` lines to a dated file in ``folder``."""

    def __init__(
        self,
        folder: Path,
        name: str = DEFAULT_NAME,
        extension: str = DEFAULT_EXTENSION,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.folder = folder
        self.name = name
        self.extension = extension
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
        path = self.folder / log_filename(self.name, self.extension, stamp)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{stamp:%H:%M:%S}  {mode:<9}  {event:<6}  {format_seconds(elapsed)}\n")
