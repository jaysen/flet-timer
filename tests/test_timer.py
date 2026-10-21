import pytest

from flet_timer.timer import Countdown, State, format_seconds


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_new_countdown_is_idle(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    assert c.state is State.IDLE
    assert c.remaining == 10


def test_counts_down_while_running(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    c.start()
    clock.now = 3
    assert c.state is State.RUNNING
    assert c.remaining == 7


def test_pause_freezes_remaining(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    c.start()
    clock.now = 3
    c.pause()
    clock.now = 100
    assert c.state is State.PAUSED
    assert c.remaining == 7


def test_resume_continues_from_pause(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    c.start()
    clock.now = 3
    c.pause()
    clock.now = 50
    c.start()
    clock.now = 52
    assert c.remaining == 5


def test_finishes_and_clamps_at_zero(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    c.start()
    clock.now = 99
    assert c.state is State.FINISHED
    assert c.remaining == 0


def test_reset_returns_to_idle(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    c.start()
    clock.now = 4
    c.reset()
    assert c.state is State.IDLE
    assert c.remaining == 10


def test_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError):
        Countdown(0)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00"), (0.1, "00:01"), (59.5, "01:00"), (60, "01:00"), (300, "05:00")],
)
def test_format_seconds(seconds: float, expected: str) -> None:
    assert format_seconds(seconds) == expected
