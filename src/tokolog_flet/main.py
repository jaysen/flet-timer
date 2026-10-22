"""Flet UI entry point. Keep this thin: behaviour lives in timer.py."""

import asyncio
import os
import subprocess
import sys
from functools import partial
from pathlib import Path

import flet as ft

from tokolog_flet.config import (
    DEFAULT_PROFILE,
    Config,
    ConfigError,
    Profile,
    config_mtime,
    config_path,
    create_config,
    load_config,
)
from tokolog_flet.log import EventLog
from tokolog_flet.state import load_last_profile, save_last_profile
from tokolog_flet.timer import Countdown, State, Stopwatch, parse_duration

TICK_SECONDS = 0.2
# How often to look for edits to the config file.
CONFIG_POLL_SECONDS = 1.0
# Also picked up by `flet build` as the app icon.
ICON = Path(__file__).parent.parent / "assets" / "icon.png"

COUNTDOWN = "countdown"
SET_TIME_TOOLTIP = "Click to set the time, e.g. 25, 1:30 or 1h30m"
STOPWATCH = "stopwatch"
# Window and time sizes for the full and compact views.
FULL_SIZE = (380, 260)
# Extra window height for the profile picker, and the gap kept under it.
PICKER_HEIGHT = 32
PICKER_GAP = 20
COMPACT_SIZE = (220, 170)
FULL_TIME_SIZE = 72
COMPACT_TIME_SIZE = 42
FULL_BUTTON_WIDTH = 100
COMPACT_BUTTON_WIDTH = 76


def log_lines(profile: Profile) -> dict[str, str]:
    lines = {
        COUNTDOWN: profile.log_line_format_countdown,
        STOPWATCH: profile.log_line_format_stopwatch,
    }
    # A blank per-mode line means "use line_format", not "skip".
    return {mode: line for mode, line in lines.items() if line}


def open_in_editor(path: Path) -> None:
    """Open ``path`` in the system's default app for it, without waiting."""
    if sys.platform == "win32":
        os.startfile(path)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(page: ft.Page, config: Config, config_error: str = "") -> None:
    """``config_error`` is why the config file couldn't be used; the defaults stand in."""
    page.title = "Tokolog-flet"
    page.window.width, page.window.height = FULL_SIZE
    page.window.icon = str(ICON)
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.padding = 4

    profile_name = load_last_profile()
    if profile_name not in config.profiles:
        profile_name = DEFAULT_PROFILE
    profile = config.profile(profile_name)
    timers: dict[str, Stopwatch] = {
        COUNTDOWN: Countdown(profile.default_seconds),
        STOPWATCH: Stopwatch(),
    }
    current = STOPWATCH
    timer = timers[current]
    events = EventLog(
        profile.log_folder,
        profile.log_file,
        profile.log_date_format,
        profile.log_time_format,
        profile.log_line_format,
        profile=profile_name,
        lines=log_lines(profile),
    )

    mode = ft.SegmentedButton(
        selected=[current],
        segments=[
            ft.Segment(value=COUNTDOWN, label="Timer"),
            ft.Segment(value=STOPWATCH, label="Stopwatch"),
        ],
        show_selected_icon=False,
        tooltip="Select mode",
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=30, vertical=0),
            text_style=ft.TextStyle(size=11),
            visual_density=ft.VisualDensity.COMPACT,
        ),
    )
    # A borderless caption above the time, so it reads as a title rather than a form field.
    label = ft.TextField(
        hint_text=current,
        width=260,
        dense=True,
        text_size=16,
        text_align=ft.TextAlign.CENTER,
        border=ft.NoInputBorder(),
        color=ft.Colors.ON_SURFACE_VARIANT,
        hint_style=ft.TextStyle(color=ft.Colors.OUTLINE),
    )
    display = ft.Text(timer.display(), size=FULL_TIME_SIZE, weight=ft.FontWeight.W_300)
    # Clicking the countdown's time swaps it for this field, styled to look the same.
    time_field = ft.TextField(
        width=300,
        dense=True,
        text_size=FULL_TIME_SIZE,
        text_style=ft.TextStyle(weight=ft.FontWeight.W_300),
        text_align=ft.TextAlign.CENTER,
        border=ft.NoInputBorder(),
        content_padding=0,
        visible=False,
    )
    time_display = ft.GestureDetector(display)
    start_pause = ft.FilledButton("Start", width=FULL_BUTTON_WIDTH)
    reset = ft.OutlinedButton("Reset", width=FULL_BUTTON_WIDTH)
    profile_picker = ft.Dropdown(
        width=200,
        dense=True,
        text_size=14,
        text_style=ft.TextStyle(weight=ft.FontWeight.W_200),
        content_padding=ft.Padding.symmetric(horizontal=4, vertical=0),
        # Borderless, so it reads as a caption rather than competing with Start/Reset.
        border=ft.NoInputBorder(),
        tooltip="Profile: where and how to log",
        leading_icon=ft.Icon(ft.Icons.TUNE, size=14),
    )

    def sync_profile_picker() -> None:
        profile_picker.options = [
            ft.DropdownOption(key=name, text=name) for name in [DEFAULT_PROFILE, *config.profiles]
        ]
        profile_picker.value = profile_name
        # Nothing to pick between until the config file names a profile.
        shown = bool(config.profiles)
        profile_picker.visible = shown and not compact
        if not compact:
            # Without the picker the bar only mirrors the top bar, so the content stays centred.
            bottom_bar.height = PICKER_HEIGHT + PICKER_GAP if shown else 24
            page.window.height = FULL_SIZE[1] + (PICKER_HEIGHT if shown else 0)

    def log_state() -> None:
        events.update(current, timer, (label.value or "").strip() or fallback_label())

    def fallback_label() -> str:
        # Without a label of its own, a timer takes the profile's, else its mode, as the hint shows.
        return config.profile(profile_name).default_label or current

    def can_set_time() -> bool:
        # Only before starting or once finished, so a paused countdown isn't lost by accident.
        return isinstance(timer, Countdown) and timer.state in (State.IDLE, State.FINISHED)

    def render() -> None:
        log_state()
        display.value = timer.display()
        label.hint_text = fallback_label()
        editable = can_set_time()
        time_display.mouse_cursor = ft.MouseCursor.CLICK if editable else None
        time_display.tooltip = SET_TIME_TOOLTIP if editable else None
        start_pause.content = "Pause" if timer.state is State.RUNNING else "Start"
        start_pause.disabled = timer.state is State.FINISHED
        # A session stays in one log; only an idle or finished timer can change profile.
        profile_picker.disabled = timer.state in (State.RUNNING, State.PAUSED)
        page.update()

    async def tick() -> None:
        ticking = timer
        while ticking is timer and timer.state is State.RUNNING:
            render()
            await asyncio.sleep(TICK_SECONDS)
        render()

    async def on_time_click(_: ft.TapEvent[ft.GestureDetector]) -> None:
        if not can_set_time():
            return
        time_field.value = display.value
        time_field.selection = ft.TextSelection(0, len(display.value or ""))
        time_field.visible = True
        time_display.visible = False
        page.update()
        await time_field.focus()

    def finish_setting_time(apply: bool) -> None:
        if not time_field.visible:
            return
        time_field.visible = False
        time_display.visible = True
        seconds = parse_duration(time_field.value or "") if apply else None
        if seconds is not None and isinstance(timer, Countdown):
            timer.duration = seconds
            timer.reset()
        render()

    def on_time_submit(_: ft.Event[ft.TextField]) -> None:
        finish_setting_time(apply=True)

    def on_key(e: ft.KeyboardEvent) -> None:
        if e.key == "Escape":
            finish_setting_time(apply=False)

    def on_mode_change(_: ft.Event[ft.SegmentedButton]) -> None:
        nonlocal current, timer
        finish_setting_time(apply=False)
        log_state()
        timer.reset()
        log_state()
        current = mode.selected[0]
        timer = timers[current]
        render()

    def on_start_pause(_: ft.Event[ft.Button]) -> None:
        # Note the state just before acting, so a pause or stop logs the exact time.
        log_state()
        if timer.state is State.RUNNING:
            timer.pause()
            render()
        else:
            timer.start()
            page.run_task(tick)

    def on_reset(_: ft.Event[ft.OutlinedButton]) -> None:
        log_state()
        timer.reset()
        render()

    def edit_config(_: ft.Event[ft.IconButton] | ft.Event[ft.Container]) -> None:
        finish_setting_time(apply=False)
        path = config_path()
        try:
            create_config(path)
            open_in_editor(path)
        except OSError as e:
            show_error(f"Could not open {path}: {e.strerror or e}")
            page.update()

    def show_error(message: str) -> None:
        error_text.value = message
        error_bar.visible = bool(message)

    async def watch_config() -> None:
        # Saving in the editor is the "apply"; a broken save keeps the last good config.
        path = config_path()
        seen = config_mtime(path)
        while True:
            await asyncio.sleep(CONFIG_POLL_SECONDS)
            if (changed := config_mtime(path)) == seen:
                continue
            seen = changed
            try:
                new = load_config(path)
            except ConfigError as e:
                show_error(str(e).removeprefix(f"{path}: "))
                page.update()
                continue
            show_error("")
            apply_config(new)

    def use_profile(old: Profile, new: Profile) -> None:
        countdown = timers[COUNTDOWN]
        # Only an untouched countdown follows the new default; a set or running one keeps its time.
        if (
            isinstance(countdown, Countdown)
            and countdown.state is State.IDLE
            and countdown.duration == old.default_seconds
        ):
            countdown.duration = new.default_seconds
        # Same log object, so a running timer isn't taken for a fresh start.
        events.folder = new.log_folder
        events.file = new.log_file
        events.date_format = new.log_date_format
        events.time_format = new.log_time_format
        events.line_format = new.log_line_format
        events.lines = log_lines(new)
        events.profile = profile_name

    def apply_config(new: Config) -> None:
        nonlocal config, profile_name
        old = config.profile(profile_name)
        config = new
        # The picked profile may have been removed or renamed.
        if profile_name not in new.profiles:
            profile_name = DEFAULT_PROFILE
        use_profile(old, new.profile(profile_name))
        sync_profile_picker()
        render()

    def on_profile_select(_: ft.Event[ft.Dropdown]) -> None:
        nonlocal profile_name
        old = config.profile(profile_name)
        profile_name = profile_picker.value or DEFAULT_PROFILE
        use_profile(old, config.profile(profile_name))
        save_last_profile(profile_name)
        render()

    def on_minimize(_: ft.Event[ft.IconButton]) -> None:
        page.window.minimized = True
        page.update()

    compact = False
    full_size = FULL_SIZE

    def on_toggle_compact(_: ft.Event[ft.IconButton]) -> None:
        nonlocal compact, full_size
        compact = not compact
        if compact:
            # Remember the full size so going back restores it, even if resized.
            full_size = page.window.width, page.window.height
            page.window.width, page.window.height = COMPACT_SIZE
        else:
            page.window.width, page.window.height = full_size
        # Only the label, time and buttons stay, plus this button and the window buttons.
        settings_button.visible = mode.visible = bottom_bar.visible = not compact
        sync_profile_picker()
        size = COMPACT_TIME_SIZE if compact else FULL_TIME_SIZE
        display.size = time_field.text_size = size
        label.width = 200 if compact else 260
        style = (
            ft.ButtonStyle(
                visual_density=ft.VisualDensity.COMPACT,
                text_style=ft.TextStyle(size=12),
                padding=ft.Padding.symmetric(horizontal=8, vertical=0),
            )
            if compact
            else None
        )
        for button in (start_pause, reset):
            button.width = COMPACT_BUTTON_WIDTH if compact else FULL_BUTTON_WIDTH
            button.style = style
        buttons.spacing = 4 if compact else 8
        compact_button.icon = ft.Icons.OPEN_IN_FULL if compact else ft.Icons.CLOSE_FULLSCREEN
        compact_button.tooltip = "Full view" if compact else "Compact view"
        page.update()

    async def on_close(_: ft.Event[ft.IconButton]) -> None:
        await page.window.close()

    def window_button(icon: ft.IconData, tooltip: str, on_click) -> ft.IconButton:
        return ft.IconButton(
            icon,
            icon_size=14,
            tooltip=tooltip,
            on_click=on_click,
            style=ft.ButtonStyle(padding=4),
            width=26,
            height=26,
        )

    # As wide as the window buttons so the mode toggle sits centred.
    settings_button = window_button(
        ft.Icons.SETTINGS, "Settings: opens config.toml; saving it applies", edit_config
    )
    compact_button = window_button(ft.Icons.CLOSE_FULLSCREEN, "Compact view", on_toggle_compact)
    settings_slot = ft.Container(
        ft.Row([settings_button, compact_button], spacing=0),
        width=52,
        alignment=ft.Alignment.CENTER_LEFT,
    )
    top_bar = ft.Row(
        [
            settings_slot,
            mode,
            ft.Row(
                [
                    window_button(ft.Icons.MINIMIZE, "Minimise", on_minimize),
                    window_button(ft.Icons.CLOSE, "Close", on_close),
                ],
                spacing=0,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    buttons = ft.Row([start_pause, reset], alignment=ft.MainAxisAlignment.CENTER, spacing=8)
    error_text = ft.Text(size=11, color=ft.Colors.ON_ERROR_CONTAINER, max_lines=3, expand=True)
    # Stays until the file is fixed; clicking it opens the file.
    error_bar = ft.Container(
        ft.Row(
            [ft.Icon(ft.Icons.ERROR_OUTLINE, size=14, color=ft.Colors.ERROR), error_text],
            spacing=6,
        ),
        bgcolor=ft.Colors.ERROR_CONTAINER,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        tooltip=f"Problem in {config_path()}; click to edit",
        on_click=edit_config,
    )
    show_error(config_error.removeprefix(f"{config_path()}: "))
    # Mirrors the top bar's height so the content sits in the true centre.
    bottom_bar = ft.Container(
        profile_picker,
        height=32,
        alignment=ft.Alignment.TOP_CENTER,
        padding=ft.Padding.only(bottom=PICKER_GAP),
    )

    sync_profile_picker()
    mode.on_change = on_mode_change
    profile_picker.on_select = on_profile_select
    time_display.on_tap = on_time_click
    time_field.on_submit = on_time_submit
    # Clicking away, e.g. on Start, keeps what was typed.
    time_field.on_blur = on_time_submit
    page.on_keyboard_event = on_key
    start_pause.on_click = on_start_pause
    reset.on_click = on_reset
    # No title bar, so empty space is the drag handle. The drag area sits behind the
    # controls rather than wrapping them, so it can't steal their clicks.
    page.add(
        ft.Stack(
            [
                ft.WindowDragArea(ft.Container(), maximizable=False, expand=True),
                ft.Column(
                    [
                        top_bar,
                        error_bar,
                        ft.Column(
                            [
                                ft.Column(
                                    [label, time_display, time_field],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=0,
                                ),
                                buttons,
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=0,
                            expand=True,
                        ),
                        bottom_bar,
                    ],
                    expand=True,
                ),
            ],
            expand=True,
        )
    )
    page.run_task(watch_config)


def run() -> None:
    # A broken config still opens the app, on the defaults, so the gear can fix it.
    try:
        config, error = load_config(), ""
    except ConfigError as e:
        config, error = Config(), str(e)
    ft.run(partial(main, config=config, config_error=error))


if __name__ == "__main__":
    run()
