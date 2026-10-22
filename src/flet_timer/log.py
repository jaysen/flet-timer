"""Activity log: one line per timer event, in a file named after the date.

The file name and line are ``str.format`` templates, so ``{mode:<9}`` pads and
``{{`` / ``}}`` give literal braces.

Events are worked out from state changes, so the UI only has to report the timer's
state before and after each action, and on every tick.
"""

import os
import re
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path

from flet_timer.timer import State, Stopwatch, format_seconds

DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_FILE = "{date}.log"
DEFAULT_LINE_FORMAT = "{time}  {mode:<9}  {event:<6}  {elapsed}"

DATE_TOKENS = re.compile("YYYY|YY|MM|DD")
FILE_PLACEHOLDERS = ("date", "label")
# display is what the timer showed: remaining time for a countdown, elapsed for a stopwatch.
LINE_PLACEHOLDERS = ("date", "time", "mode", "event", "elapsed", "display", "label")

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


def template_error(template: str, placeholders: Iterable[str]) -> str | None:
    """Why ``template`` can't be filled from ``placeholders``, or None if it can."""
    try:
        template.format(**dict.fromkeys(placeholders, ""))
    except KeyError as e:
        return f"unknown placeholder {{{e.args[0]}}}"
    except IndexError:
        return "empty placeholder {}"
    except (ValueError, AttributeError) as e:
        return str(e)
    return None


def log_filename(file: str, date_format: str, day: date, label: str = "") -> str:
    """Fill ``file``'s placeholders, e.g. ``flet-{date}.md`` -> ``flet-2026-10-21.md``."""
    # A label is free text; keep it from turning the name into a path.
    safe_label = label.replace("/", "-").replace("\\", "-")
    return file.format(date=format_date(date_format, day), label=safe_label)


class EventLog:
    """Appends a ``line_format`` line per event to a dated file in ``folder``."""

    def __init__(
        self,
        folder: Path,
        file: str = DEFAULT_FILE,
        date_format: str = DEFAULT_DATE_FORMAT,
        line_format: str = DEFAULT_LINE_FORMAT,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.folder = folder
        self.file = file
        self.date_format = date_format
        self.line_format = line_format
        self.now = now
        self._seen: dict[str, tuple[State, float, str]] = {}

    def update(self, mode: str, timer: Stopwatch, label: str = "") -> None:
        seen = timer.state, timer.elapsed, timer.display()
        before = self._seen.get(mode, (State.IDLE, 0.0, ""))
        self._seen[mode] = seen
        if event := EVENTS.get((before[0], seen[0])):
            # A stop has already reset the timer, so report the time it had reached.
            _, elapsed, display = before if event == "stop" else seen
            self._write(mode, event, elapsed, display, label)

    def _write(self, mode: str, event: str, elapsed: float, display: str, label: str) -> None:
        stamp = self.now()
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / log_filename(self.file, self.date_format, stamp, label)
        line = self.line_format.format(
            date=format_date(self.date_format, stamp),
            time=f"{stamp:%H:%M:%S}",
            mode=mode,
            event=event,
            elapsed=format_seconds(elapsed),
            display=display,
            label=label,
        )
        line += "\n"
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
