import pytest

from flet_timer.timer import Countdown, State, Stopwatch, format_seconds


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


def test_countdown_display_rounds_up(clock: FakeClock) -> None:
    c = Countdown(10, clock)
    c.start()
    clock.now = 9.5
    assert c.display() == "00:01"


def test_new_stopwatch_is_idle(clock: FakeClock) -> None:
    s = Stopwatch(clock)
    assert s.state is State.IDLE
    assert s.elapsed == 0


def test_stopwatch_counts_up_without_limit(clock: FakeClock) -> None:
    s = Stopwatch(clock)
    s.start()
    clock.now = 10_000
    assert s.state is State.RUNNING
    assert s.elapsed == 10_000


def test_stopwatch_pause_resume_and_reset(clock: FakeClock) -> None:
    s = Stopwatch(clock)
    s.start()
    clock.now = 3
    s.pause()
    clock.now = 50
    assert s.state is State.PAUSED
    assert s.elapsed == 3
    s.start()
    clock.now = 52
    assert s.elapsed == 5
    s.reset()
    assert s.state is State.IDLE
    assert s.elapsed == 0


def test_stopwatch_display_rounds_down(clock: FakeClock) -> None:
    s = Stopwatch(clock)
    s.start()
    clock.now = 0.9
    assert s.display() == "00:00"


@pytest.mark.parametrize(
    ("seconds", "round_up", "expected"),
    [
        (0, True, "00:00"),
        (0.1, True, "00:01"),
        (59.5, True, "01:00"),
        (60, True, "01:00"),
        (300, True, "05:00"),
        (0.9, False, "00:00"),
        (59.5, False, "00:59"),
        (3600, False, "1:00:00"),
        (3725, False, "1:02:05"),
    ],
)
def test_format_seconds(seconds: float, round_up: bool, expected: str) -> None:
    assert format_seconds(seconds, round_up=round_up) == expected
