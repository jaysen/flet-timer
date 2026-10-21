from datetime import datetime
from pathlib import Path

import pytest

from flet_timer.log import EventLog
from flet_timer.timer import Countdown, Stopwatch


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def make_log(folder: Path) -> EventLog:
    return EventLog(folder, now=lambda: datetime(2026, 10, 21, 9, 30, 5))


def lines(folder: Path) -> list[str]:
    return (folder / "2026-10-21.log").read_text().splitlines()


def test_logs_start_pause_resume_stop(tmp_path: Path, clock: FakeClock) -> None:
    log = make_log(tmp_path)
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s)
    clock.now = 65
    log.update("stopwatch", s)  # a tick: no change, no line
    s.pause()
    log.update("stopwatch", s)
    s.start()
    log.update("stopwatch", s)
    clock.now = 90
    log.update("stopwatch", s)
    s.reset()
    log.update("stopwatch", s)
    assert lines(tmp_path) == [
        "09:30:05  stopwatch  start   00:00",
        "09:30:05  stopwatch  pause   01:05",
        "09:30:05  stopwatch  resume  01:05",
        "09:30:05  stopwatch  stop    01:30",
    ]


def test_logs_finish_once(tmp_path: Path, clock: FakeClock) -> None:
    log = make_log(tmp_path)
    c = Countdown(60, clock)
    c.start()
    log.update("countdown", c)
    clock.now = 61
    log.update("countdown", c)
    log.update("countdown", c)
    c.reset()  # resetting a finished countdown is not a stop
    log.update("countdown", c)
    assert lines(tmp_path) == [
        "09:30:05  countdown  start   00:00",
        "09:30:05  countdown  finish  01:00",
    ]


def test_reset_while_idle_logs_nothing(tmp_path: Path, clock: FakeClock) -> None:
    log = make_log(tmp_path)
    s = Stopwatch(clock)
    s.reset()
    log.update("stopwatch", s)
    assert not (tmp_path / "2026-10-21.log").exists()


def test_tracks_modes_separately(tmp_path: Path, clock: FakeClock) -> None:
    log = make_log(tmp_path)
    c, s = Countdown(60, clock), Stopwatch(clock)
    c.start()
    log.update("countdown", c)
    log.update("stopwatch", s)
    assert lines(tmp_path) == ["09:30:05  countdown  start   00:00"]


def test_creates_folder_and_appends_per_day(tmp_path: Path, clock: FakeClock) -> None:
    folder = tmp_path / "nested" / "log"
    days = iter([datetime(2026, 10, 21, 23, 59), datetime(2026, 10, 22, 0, 1)])
    log = EventLog(folder, now=lambda: next(days))
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s)
    clock.now = 120
    s.pause()
    log.update("stopwatch", s)
    assert (folder / "2026-10-21.log").read_text().startswith("23:59:00  stopwatch  start")
    assert (folder / "2026-10-22.log").read_text().startswith("00:01:00  stopwatch  pause")
