"""What the app is doing: the picked profile, the timers and the log, independent of any UI.

The UI reads state from here and calls the methods below; it only has to draw.
"""

import time

from tokolog_flet.config import DEFAULT_PROFILE, Config, Profile
from tokolog_flet.log import EventLog
from tokolog_flet.timer import Clock, Countdown, State, Stopwatch, parse_duration

COUNTDOWN = "countdown"
STOPWATCH = "stopwatch"


def under_way(timer: Stopwatch) -> bool:
    """Running or paused: a run that a reset or a change would cut short."""
    return timer.state in (State.RUNNING, State.PAUSED)


class Session:
    def __init__(self, config: Config, profile_name: str, clock: Clock = time.monotonic) -> None:
        self.config = config
        self.profile_name = profile_name if profile_name in config.profiles else DEFAULT_PROFILE
        profile = self.profile
        self.timers: dict[str, Stopwatch] = {
            COUNTDOWN: Countdown(profile.default_seconds, clock),
            STOPWATCH: Stopwatch(clock),
        }
        # A profile that allows only one mode starts in it.
        self.current = profile.mode or STOPWATCH
        self.events = EventLog(profile.log_folder)
        self.events.use_profile(profile, self.profile_name)
        # What the label field holds.
        self.label = ""

    @property
    def profile(self) -> Profile:
        return self.config.profile(self.profile_name)

    @property
    def timer(self) -> Stopwatch:
        return self.timers[self.current]

    @property
    def locked_mode(self) -> str | None:
        return self.profile.mode

    def fallback_label(self) -> str:
        # Without a label of its own, a timer takes the profile's, else its mode, as the hint shows.
        return self.profile.default_label or self.current

    def log_state(self) -> None:
        self.events.update(self.current, self.timer, self.label.strip() or self.fallback_label())

    def can_set_time(self) -> bool:
        # Only before starting or once over, so a paused countdown isn't lost by accident.
        return isinstance(self.timer, Countdown) and not under_way(self.timer)

    def set_time(self, text: str) -> None:
        """Set the countdown from ``text`` as typed; text that isn't a time is ignored."""
        seconds = parse_duration(text)
        if seconds is not None and isinstance(self.timer, Countdown):
            self.timer.duration = seconds
            self.timer.reset()

    def switch_mode(self, new: str) -> None:
        self.log_state()
        self.timer.reset()
        self.log_state()
        self.current = new

    def follow_profile_mode(self) -> None:
        """Switch to the profile's mode, once the timer isn't under way."""
        # Waits, e.g. after a config edit mid-session, so nothing is cut short.
        locked = self.locked_mode
        if locked and locked != self.current and not under_way(self.timer):
            self.switch_mode(locked)

    def start_pause(self) -> bool:
        """Start, resume or pause; True if the timer is now running."""
        # Note the state just before acting, so a pause logs the exact time.
        self.log_state()
        if self.timer.state is State.RUNNING:
            self.timer.pause()
            return False
        self.timer.start()
        return True

    def stop_reset(self) -> None:
        # A run is stopped first, so its time can be read before Reset clears it.
        self.log_state()
        if under_way(self.timer):
            self.timer.stop()
        else:
            self.timer.reset()

    def select_profile(self, name: str) -> None:
        old = self.profile
        self.profile_name = name
        self._use_profile(old)

    def apply_config(self, new: Config) -> None:
        old = self.profile
        self.config = new
        # The picked profile may have been removed or renamed.
        if self.profile_name not in new.profiles:
            self.profile_name = DEFAULT_PROFILE
        self._use_profile(old)

    def _use_profile(self, old: Profile) -> None:
        new = self.profile
        countdown = self.timers[COUNTDOWN]
        # Only an untouched countdown follows the new default; a set or running one keeps its time.
        if (
            isinstance(countdown, Countdown)
            and countdown.state is State.IDLE
            and countdown.duration == old.default_seconds
        ):
            countdown.duration = new.default_seconds
        self.events.use_profile(new, self.profile_name)
