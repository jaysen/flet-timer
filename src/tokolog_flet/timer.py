"""Stopwatch and countdown timer logic, independent of any UI.

Time is read from an injectable clock so the logic can be tested without sleeping.
"""

import re
import time
from collections.abc import Callable
from enum import Enum, auto

Clock = Callable[[], float]


class State(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    # Stopped by hand: the time stays on show until reset.
    STOPPED = auto()
    FINISHED = auto()


class Stopwatch:
    """Counts up from zero until paused, stopped or reset."""

    def __init__(self, clock: Clock = time.monotonic) -> None:
        self.clock = clock
        self._elapsed = 0.0
        self._started_at: float | None = None
        self._stopped = False

    @property
    def elapsed(self) -> float:
        running = 0.0 if self._started_at is None else self.clock() - self._started_at
        return self._elapsed + running

    @property
    def state(self) -> State:
        if self._started_at is not None:
            return State.RUNNING
        if self._stopped:
            return State.STOPPED
        return State.PAUSED if self._elapsed > 0 else State.IDLE

    def display(self) -> str:
        return format_seconds(self.elapsed)

    def start(self) -> None:
        if self.state in (State.IDLE, State.PAUSED):
            self._started_at = self.clock()

    def pause(self) -> None:
        if self.state is State.RUNNING:
            self._elapsed = self.elapsed
            self._started_at = None

    def stop(self) -> None:
        """End the run but keep its time, so it can be read before a reset."""
        if self.state in (State.RUNNING, State.PAUSED):
            self._elapsed = self.elapsed
            self._started_at = None
            self._stopped = True

    def reset(self) -> None:
        self._elapsed = 0.0
        self._started_at = None
        self._stopped = False


class Countdown(Stopwatch):
    """Counts down from ``duration`` and finishes at zero."""

    def __init__(self, duration: float, clock: Clock = time.monotonic) -> None:
        super().__init__(clock)
        self.duration = duration

    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("duration must be positive")
        self._duration = seconds

    @property
    def elapsed(self) -> float:
        return min(super().elapsed, self.duration)

    @property
    def remaining(self) -> float:
        return self.duration - self.elapsed

    @property
    def state(self) -> State:
        if self.remaining <= 0:
            return State.FINISHED
        return super().state

    def display(self) -> str:
        # Round up so 00:00 only shows when finished.
        return format_seconds(self.remaining, round_up=True)


def format_seconds(seconds: float, *, round_up: bool = False) -> str:
    """Format as MM:SS, or H:MM:SS from one hour up."""
    total = max(0, int(-(-seconds // 1) if round_up else seconds // 1))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
NUMBER = r"\d+(?:\.\d+)?"
UNITS = re.compile(rf"(?:({NUMBER})\s*([hms])\s*)+")
UNIT_PART = re.compile(rf"({NUMBER})\s*([hms])")


def parse_duration(text: str) -> float | None:
    """Seconds from ``25`` (minutes), ``1:30``, ``1:00:00`` or ``1h30m``; None if unusable."""
    text = text.strip().lower()
    if re.fullmatch(NUMBER, text):
        seconds = float(text) * 60
    elif re.fullmatch(r"\d+(?::\d+){1,2}", text):
        *leading, last = (int(part) for part in text.split(":"))
        # 1:90 is more likely a typo than 2:30, so only the first part may exceed 59.
        if any(part > 59 for part in [*leading[1:], last]):
            return None
        seconds = 0
        for part in [*leading, last]:
            seconds = seconds * 60 + part
    elif UNITS.fullmatch(text):
        parts = UNIT_PART.findall(text)
        units = [unit for _, unit in parts]
        if len(set(units)) != len(units):
            return None
        seconds = sum(float(number) * UNIT_SECONDS[unit] for number, unit in parts)
    else:
        return None
    return seconds if seconds > 0 else None
