from datetime import date, datetime
from pathlib import Path

import pytest

from tokolog_flet.log import (
    EventLog,
    format_date,
    format_time,
    log_filename,
    template_error,
)
from tokolog_flet.timer import Countdown, Stopwatch


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


@pytest.mark.parametrize(
    ("date_format", "expected"),
    [
        ("YYYY-MM-DD", "2026-10-21"),
        ("YYYYMMDD", "20261021"),
        ("DD.MM.YY", "21.10.26"),
    ],
)
def test_format_date(date_format: str, expected: str) -> None:
    assert format_date(date_format, date(2026, 10, 21)) == expected


@pytest.mark.parametrize(
    ("time_format", "hour", "expected"),
    [
        ("HH:mm:ss", 14, "14:05:09"),
        ("HH:mm", 9, "09:05"),
        ("hh:mm AM", 14, "02:05 PM"),
        ("hh:mm AM", 0, "12:05 AM"),
        ("HHmm", 14, "1405"),
    ],
)
def test_format_time(time_format: str, hour: int, expected: str) -> None:
    assert format_time(time_format, datetime(2026, 10, 21, hour, 5, 9)) == expected


def test_time_format_in_line(tmp_path: Path, clock: FakeClock) -> None:
    log = EventLog(
        tmp_path,
        time_format="hh:mm AM",
        line_format="{time} {event}",
        now=lambda: datetime(2026, 10, 21, 14, 5, 9),
    )
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s)
    assert lines(tmp_path) == ["02:05 PM start"]


@pytest.mark.parametrize(
    ("file", "expected"),
    [
        ("{date}.log", "2026-10-21.log"),
        ("flet-{date}.md", "flet-2026-10-21.md"),
        ("SUMMARY-{date}", "SUMMARY-2026-10-21"),  # only {date} is replaced
        ("timer.md", "timer.md"),
        ("{date}-{label}.md", "2026-10-21-client-a-b.md"),  # no folders from the label
    ],
)
def test_log_filename(file: str, expected: str) -> None:
    assert log_filename(file, "YYYY-MM-DD", date(2026, 10, 21), "client/a\\b") == expected


@pytest.mark.parametrize(
    ("template", "error"),
    [
        ("{date}-{mode:<9} {{literal}}", None),
        ("{dat}", "unknown placeholder {dat}"),
        ("{}", "empty placeholder {}"),
        ("{date", "expected '}' before end of string"),
    ],
)
def test_template_error(template: str, error: str | None) -> None:
    assert template_error(template, ("date", "mode")) == error


def test_writes_to_configured_file_name(tmp_path: Path, clock: FakeClock) -> None:
    log = EventLog(
        tmp_path, "flet-{date}.md", "YYYYMMDD", now=lambda: datetime(2026, 10, 21, 9, 30, 5)
    )
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s)
    assert (tmp_path / "flet-20261021.md").read_text() == "09:30:05  stopwatch  start   00:00\n"


def test_appends_to_existing_file(tmp_path: Path, clock: FakeClock) -> None:
    (tmp_path / "2026-10-21.log").write_text("# Notes\n")
    log = make_log(tmp_path)
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s)
    assert lines(tmp_path) == ["# Notes", "09:30:05  stopwatch  start   00:00"]


def test_starts_new_line_if_file_lacks_trailing_newline(tmp_path: Path, clock: FakeClock) -> None:
    (tmp_path / "2026-10-21.log").write_text("# Notes")
    log = make_log(tmp_path)
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s)
    assert lines(tmp_path) == ["# Notes", "09:30:05  stopwatch  start   00:00"]


def test_line_format(tmp_path: Path, clock: FakeClock) -> None:
    log = EventLog(
        tmp_path,
        line_format=" - {date} {time} - {mode} {event} {elapsed} ({display})",
        now=lambda: datetime(2026, 10, 21, 9, 30, 5),
    )
    c = Countdown(300, clock)
    c.start()
    log.update("countdown", c)
    clock.now = 65
    log.update("countdown", c)  # as the UI does just before acting
    c.reset()
    log.update("countdown", c)
    assert lines(tmp_path) == [
        " - 2026-10-21 09:30:05 - countdown start 00:00 (05:00)",
        # a stop reports the time reached, not the reset values
        " - 2026-10-21 09:30:05 - countdown stop 01:05 (03:55)",
    ]


def test_label_in_line_and_file(tmp_path: Path, clock: FakeClock) -> None:
    log = EventLog(
        tmp_path,
        file="{label}.log",
        line_format="{event} {label}",
        now=lambda: datetime(2026, 10, 21, 9, 30, 5),
    )
    s = Stopwatch(clock)
    s.start()
    log.update("stopwatch", s, "writing")
    assert (tmp_path / "writing.log").read_text() == "start writing\n"
