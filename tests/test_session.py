from pathlib import Path

import pytest

from tokolog_flet.config import DEFAULT_PROFILE, Config, Profile
from tokolog_flet.session import COUNTDOWN, STOPWATCH, Session
from tokolog_flet.timer import Countdown, State


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def make_config(tmp_path: Path, **profiles: Profile) -> Config:
    return Config(log_folder=tmp_path / "default", profiles=profiles)


def countdown_of(session: Session) -> Countdown:
    countdown = session.timers[COUNTDOWN]
    assert isinstance(countdown, Countdown)
    return countdown


def log_lines(folder: Path) -> list[str]:
    return [line for path in folder.glob("*") for line in path.read_text().splitlines()]


def test_unknown_profile_falls_back_to_default(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path), "gone", clock)
    assert session.profile_name == DEFAULT_PROFILE


def test_starts_in_profile_mode(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path, work=Profile(mode=COUNTDOWN, log_folder=tmp_path / "work"))
    assert Session(config, "work", clock).current == COUNTDOWN
    assert Session(config, DEFAULT_PROFILE, clock).current == STOPWATCH


def test_countdown_starts_at_profile_default(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path, work=Profile(default_minutes=50))
    assert countdown_of(Session(config, "work", clock)).duration == 50 * 60


def test_fallback_label(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path, work=Profile(default_label="deep work"))
    session = Session(config, DEFAULT_PROFILE, clock)
    assert session.fallback_label() == STOPWATCH
    session.select_profile("work")
    assert session.fallback_label() == "deep work"


def test_start_pause_reports_running(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path), DEFAULT_PROFILE, clock)
    assert session.start_pause() is True
    assert session.timer.state is State.RUNNING
    clock.now = 5
    assert session.start_pause() is False
    assert session.timer.state is State.PAUSED


def test_stop_then_reset(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path), DEFAULT_PROFILE, clock)
    session.start_pause()
    clock.now = 5
    session.stop_reset()
    assert session.timer.state is State.STOPPED
    assert session.timer.elapsed == 5
    session.stop_reset()
    assert session.timer.state is State.IDLE


def test_logs_with_label_or_fallback(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path)
    session = Session(config, DEFAULT_PROFILE, clock)
    session.events.line_format = "{event} {label}"
    session.start_pause()
    session.log_state()
    session.label = "  writing "
    clock.now = 5
    session.start_pause()
    session.log_state()
    assert log_lines(tmp_path / "default") == ["start stopwatch", "pause writing"]


def test_switch_mode_stops_and_resets(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path), DEFAULT_PROFILE, clock)
    session.events.line_format = "{mode} {event} {elapsed}"
    session.start_pause()
    session.log_state()
    clock.now = 5
    session.switch_mode(COUNTDOWN)
    assert session.current == COUNTDOWN
    assert session.timers[STOPWATCH].state is State.IDLE
    assert log_lines(tmp_path / "default") == ["stopwatch start 00:00", "stopwatch stop 00:05"]


def test_can_set_time_only_on_a_countdown_not_under_way(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path), DEFAULT_PROFILE, clock)
    assert not session.can_set_time()
    session.switch_mode(COUNTDOWN)
    assert session.can_set_time()
    session.start_pause()
    assert not session.can_set_time()
    session.stop_reset()
    assert session.can_set_time()


@pytest.mark.parametrize(("text", "duration"), [("10", 600), ("1:30", 90), ("nonsense", 1500)])
def test_set_time(tmp_path: Path, clock: FakeClock, text: str, duration: float) -> None:
    session = Session(make_config(tmp_path), DEFAULT_PROFILE, clock)
    session.switch_mode(COUNTDOWN)
    session.set_time(text)
    assert countdown_of(session).duration == duration


def test_follow_profile_mode_waits_for_run_to_end(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path), DEFAULT_PROFILE, clock)
    session.start_pause()
    session.apply_config(Config(mode=COUNTDOWN, log_folder=tmp_path / "default"))
    session.follow_profile_mode()
    assert session.current == STOPWATCH
    session.stop_reset()
    session.follow_profile_mode()
    assert session.current == COUNTDOWN


def test_untouched_countdown_follows_new_default(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path, work=Profile(default_minutes=50))
    session = Session(config, DEFAULT_PROFILE, clock)
    session.select_profile("work")
    assert countdown_of(session).duration == 50 * 60


def test_set_countdown_keeps_its_time(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path, work=Profile(default_minutes=50))
    session = Session(config, DEFAULT_PROFILE, clock)
    session.switch_mode(COUNTDOWN)
    session.set_time("10")
    session.select_profile("work")
    assert countdown_of(session).duration == 10 * 60


def test_select_profile_moves_the_log(tmp_path: Path, clock: FakeClock) -> None:
    config = make_config(tmp_path, work=Profile(log_folder=tmp_path / "work"))
    session = Session(config, DEFAULT_PROFILE, clock)
    session.select_profile("work")
    assert session.events.folder == tmp_path / "work"
    assert session.events.profile == "work"


def test_apply_config_drops_removed_profile(tmp_path: Path, clock: FakeClock) -> None:
    session = Session(make_config(tmp_path, work=Profile()), "work", clock)
    session.apply_config(make_config(tmp_path))
    assert session.profile_name == DEFAULT_PROFILE
    assert session.events.profile == DEFAULT_PROFILE
