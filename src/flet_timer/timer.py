"""Stopwatch and countdown timer logic, independent of any UI.

Time is read from an injectable clock so the logic can be tested without sleeping.
"""

import time
from collections.abc import Callable
from enum import Enum, auto

Clock = Callable[[], float]


class State(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    FINISHED = auto()


class Stopwatch:
    """Counts up from zero until paused or reset."""

    def __init__(self, clock: Clock = time.monotonic) -> None:
        self.clock = clock
        self._elapsed = 0.0
        self._started_at: float | None = None

    @property
    def elapsed(self) -> float:
        running = 0.0 if self._started_at is None else self.clock() - self._started_at
        return self._elapsed + running

    @property
    def state(self) -> State:
        if self._started_at is not None:
            return State.RUNNING
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

    def reset(self) -> None:
        self._elapsed = 0.0
        self._started_at = None


class Countdown(Stopwatch):
    """Counts down from ``duration`` and finishes at zero."""

    def __init__(self, duration: float, clock: Clock = time.monotonic) -> None:
        if duration <= 0:
            raise ValueError("duration must be positive")
        super().__init__(clock)
        self.duration = duration

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
