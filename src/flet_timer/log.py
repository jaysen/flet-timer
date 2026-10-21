"""Activity log: one line per timer event, in a file per day.

Events are worked out from state changes, so the UI only has to report the timer's
state before and after each action, and on every tick.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from flet_timer.timer import State, Stopwatch, format_seconds

EVENTS: dict[tuple[State, State], str] = {
    (State.IDLE, State.RUNNING): "start",
    (State.PAUSED, State.RUNNING): "resume",
    (State.RUNNING, State.PAUSED): "pause",
    (State.RUNNING, State.IDLE): "stop",
    (State.PAUSED, State.IDLE): "stop",
    (State.RUNNING, State.FINISHED): "finish",
}


class EventLog:
    """Appends ``HH:MM:SS  mode  event  elapsed`` lines to ``folder/YYYY-MM-DD.log``."""

    def __init__(self, folder: Path, now: Callable[[], datetime] = datetime.now) -> None:
        self.folder = folder
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
        path = self.folder / f"{stamp:%Y-%m-%d}.log"
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{stamp:%H:%M:%S}  {mode:<9}  {event:<6}  {format_seconds(elapsed)}\n")
