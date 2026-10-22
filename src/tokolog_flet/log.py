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

from tokolog_flet.timer import Countdown, State, Stopwatch, format_seconds

DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_TIME_FORMAT = "HH:mm:ss"
DEFAULT_FILE = "{date}.log"
DEFAULT_LINE_FORMAT = "{time}  {mode:<9}  {event:<6}  {elapsed}"

DATE_TOKENS = re.compile("YYYY|YY|MM|DD")
TIME_TOKENS = re.compile("HH|hh|mm|ss|AM")
FILE_PLACEHOLDERS = ("date", "label", "profile")
# display is what the timer showed: remaining time for a countdown, elapsed for a stopwatch.
# The timer_ ones are blank for a stopwatch.
LINE_PLACEHOLDERS = (
    "date",
    "time",
    "mode",
    "event",
    "elapsed",
    "display",
    "label",
    "profile",
    "timer_minutes",
    "timer_remaining",
)

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


def format_time(time_format: str, moment: datetime) -> str:
    """Replace HH, hh (12-hour), mm, ss and AM (AM or PM), e.g. ``HH:mm`` -> ``14:05``."""
    tokens = {
        "HH": f"{moment:%H}",
        "hh": f"{moment:%I}",
        "mm": f"{moment:%M}",
        "ss": f"{moment:%S}",
        "AM": "AM" if moment.hour < 12 else "PM",
    }
    return TIME_TOKENS.sub(lambda m: tokens[m[0]], time_format)


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


def log_filename(file: str, date_format: str, day: date, label: str = "", profile: str = "") -> str:
    """Fill ``file``'s placeholders, e.g. ``flet-{date}.md`` -> ``flet-2026-10-21.md``."""
    return file.format(
        date=format_date(date_format, day), label=_safe(label), profile=_safe(profile)
    )


def _safe(text: str) -> str:
    """Free text for a file name; keep it from turning the name into a path."""
    return text.replace("/", "-").replace("\\", "-")


class EventLog:
    """Appends a ``line_format`` line per event to a dated file in ``folder``."""

    def __init__(
        self,
        folder: Path,
        file: str = DEFAULT_FILE,
        date_format: str = DEFAULT_DATE_FORMAT,
        time_format: str = DEFAULT_TIME_FORMAT,
        line_format: str = DEFAULT_LINE_FORMAT,
        now: Callable[[], datetime] = datetime.now,
        profile: str = "",
    ) -> None:
        self.folder = folder
        self.file = file
        self.date_format = date_format
        self.time_format = time_format
        self.line_format = line_format
        self.now = now
        self.profile = profile
        self._seen: dict[str, tuple[State, float, str]] = {}

    def update(self, mode: str, timer: Stopwatch, label: str = "") -> None:
        seen = timer.state, timer.elapsed, timer.display()
        before = self._seen.get(mode, (State.IDLE, 0.0, ""))
        self._seen[mode] = seen
        if event := EVENTS.get((before[0], seen[0])):
            # A stop has already reset the timer, so report the time it had reached.
            _, elapsed, display = before if event == "stop" else seen
            self._write(mode, event, elapsed, display, label, timer)

    def _write(
        self, mode: str, event: str, elapsed: float, display: str, label: str, timer: Stopwatch
    ) -> None:
        stamp = self.now()
        countdown = isinstance(timer, Countdown)
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / log_filename(self.file, self.date_format, stamp, label, self.profile)
        line = self.line_format.format(
            date=format_date(self.date_format, stamp),
            time=format_time(self.time_format, stamp),
            mode=mode,
            event=event,
            elapsed=format_seconds(elapsed),
            display=display,
            label=label,
            profile=self.profile,
            # Minutes as a plain number, like default_minutes: 25, or 1.5 for 1:30.
            timer_minutes=f"{timer.duration / 60:g}" if countdown else "",
            timer_remaining=display if countdown else "",
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
