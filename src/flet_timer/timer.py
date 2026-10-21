"""Countdown timer logic, independent of any UI.

Time is read from an injectable clock so the logic can be tested without sleeping.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    FINISHED = auto()


@dataclass
class Countdown:
    duration: float
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    _elapsed: float = field(default=0.0, init=False)
    _started_at: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError("duration must be positive")

    @property
    def elapsed(self) -> float:
        running = 0.0 if self._started_at is None else self.clock() - self._started_at
        return min(self._elapsed + running, self.duration)

    @property
    def remaining(self) -> float:
        return self.duration - self.elapsed

    @property
    def state(self) -> State:
        if self.remaining <= 0:
            return State.FINISHED
        if self._started_at is not None:
            return State.RUNNING
        return State.PAUSED if self._elapsed > 0 else State.IDLE

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


def format_seconds(seconds: float) -> str:
    """Format as MM:SS, rounding up so 0:00 only shows when finished."""
    total = max(0, int(-(-seconds // 1)))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"
