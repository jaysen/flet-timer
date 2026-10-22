"""Flet UI entry point. Keep this thin: behaviour lives in timer.py."""

import asyncio
from functools import partial
from pathlib import Path

import flet as ft

from flet_timer.config import Config, config_path, load_config
from flet_timer.log import EventLog
from flet_timer.settings import WINDOW_SIZE, open_settings
from flet_timer.timer import Countdown, State, Stopwatch, parse_duration

TICK_SECONDS = 0.2
# Also picked up by `flet build` as the app icon.
ICON = Path(__file__).parent.parent / "assets" / "icon.png"

COUNTDOWN = "countdown"
SET_TIME_TOOLTIP = "Click to set the time, e.g. 25, 1:30 or 1h30m"
STOPWATCH = "stopwatch"
# Window and time sizes for the full and compact views.
FULL_SIZE = (380, 260)
COMPACT_SIZE = (220, 170)
FULL_TIME_SIZE = 72
COMPACT_TIME_SIZE = 42
FULL_BUTTON_WIDTH = 104
COMPACT_BUTTON_WIDTH = 76


def main(page: ft.Page, config: Config) -> None:
    page.title = "FLET-Timer"
    page.window.width, page.window.height = FULL_SIZE
    page.window.icon = str(ICON)
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.padding = 4

    timers: dict[str, Stopwatch] = {
        COUNTDOWN: Countdown(config.default_seconds),
        STOPWATCH: Stopwatch(),
    }
    current = STOPWATCH
    timer = timers[current]
    events = EventLog(
        config.log_folder,
        config.log_file,
        config.log_date_format,
        config.log_time_format,
        config.log_line_format,
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
        hint_text="Add a label",
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

    def log_state() -> None:
        events.update(current, timer, (label.value or "").strip())

    def can_set_time() -> bool:
        # Only before starting or once finished, so a paused countdown isn't lost by accident.
        return isinstance(timer, Countdown) and timer.state in (State.IDLE, State.FINISHED)

    def render() -> None:
        log_state()
        display.value = timer.display()
        editable = can_set_time()
        time_display.mouse_cursor = ft.MouseCursor.CLICK if editable else None
        time_display.tooltip = SET_TIME_TOOLTIP if editable else None
        start_pause.content = "Pause" if timer.state is State.RUNNING else "Start"
        start_pause.disabled = timer.state is State.FINISHED
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

    def on_settings(_: ft.Event[ft.IconButton]) -> None:
        finish_setting_time(apply=False)
        size = page.window.width, page.window.height
        page.window.width, page.window.height = WINDOW_SIZE

        def restore_window() -> None:
            page.window.width, page.window.height = size
            page.update()

        open_settings(page, config_path(), apply_config, restore_window)
        page.update()

    def apply_config(new: Config) -> None:
        nonlocal config
        countdown = timers[COUNTDOWN]
        # Only an untouched countdown follows the new default; a set or running one keeps its time.
        if (
            isinstance(countdown, Countdown)
            and countdown.state is State.IDLE
            and countdown.duration == config.default_seconds
        ):
            countdown.duration = new.default_seconds
        config = new
        # Same log object, so a running timer isn't taken for a fresh start.
        events.folder = new.log_folder
        events.file = new.log_file
        events.date_format = new.log_date_format
        events.time_format = new.log_time_format
        events.line_format = new.log_line_format
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
        settings_button.visible = mode.visible = bottom_spacer.visible = not compact
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
    settings_button = window_button(ft.Icons.SETTINGS, "Settings", on_settings)
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
    # Mirrors the top bar's height so the content sits in the true centre.
    bottom_spacer = ft.Container(height=24)

    mode.on_change = on_mode_change
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
                        bottom_spacer,
                    ],
                    expand=True,
                ),
            ],
            expand=True,
        )
    )


def run() -> None:
    # Load before opening the window so a bad config fails fast with a readable error.
    ft.run(partial(main, config=load_config()))


if __name__ == "__main__":
    run()
