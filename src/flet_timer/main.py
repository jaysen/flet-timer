"""Flet UI entry point. Keep this thin: behaviour lives in timer.py."""

import asyncio
from functools import partial

import flet as ft

from flet_timer.config import Config, load_config
from flet_timer.log import EventLog
from flet_timer.timer import Countdown, State, Stopwatch

TICK_SECONDS = 0.2

COUNTDOWN = "countdown"
STOPWATCH = "stopwatch"


def main(page: ft.Page, config: Config) -> None:
    page.title = "FLET-Timer"
    page.window.width = 450
    page.window.height = 360
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.padding = 4

    timers: dict[str, Stopwatch] = {
        COUNTDOWN: Countdown(config.default_seconds),
        STOPWATCH: Stopwatch(),
    }
    current = COUNTDOWN
    timer = timers[current]
    events = EventLog(
        config.log_folder, config.log_file, config.log_date_format, config.log_line_format
    )

    mode = ft.SegmentedButton(
        selected=[COUNTDOWN],
        segments=[
            ft.Segment(value=COUNTDOWN, label="Timer", icon=ft.Icons.HOURGLASS_BOTTOM),
            ft.Segment(value=STOPWATCH, label="Stopwatch", icon=ft.Icons.TIMER),
        ],
    )
    label = ft.TextField(
        hint_text="Label (optional)",
        width=220,
        height=36,
        dense=True,
        text_size=14,
        border_radius=18,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=8),
    )
    display = ft.Text(timer.display(), size=64)
    start_pause = ft.FilledButton("Start")

    def log_state() -> None:
        events.update(current, timer, (label.value or "").strip())

    def render() -> None:
        log_state()
        display.value = timer.display()
        start_pause.content = "Pause" if timer.state is State.RUNNING else "Start"
        start_pause.disabled = timer.state is State.FINISHED
        page.update()

    async def tick() -> None:
        ticking = timer
        while ticking is timer and timer.state is State.RUNNING:
            render()
            await asyncio.sleep(TICK_SECONDS)
        render()

    def on_mode_change(_: ft.Event[ft.SegmentedButton]) -> None:
        nonlocal current, timer
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

    def on_minimize(_: ft.Event[ft.IconButton]) -> None:
        page.window.minimized = True
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

    mode.on_change = on_mode_change
    start_pause.on_click = on_start_pause
    # No title bar, so the whole window is the drag handle.
    page.add(
        ft.WindowDragArea(
            ft.Column(
                [
                    ft.Row(
                        [
                            # Balances the window buttons so the mode toggle sits centred.
                            ft.Container(width=52),
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
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Column(
                        [
                            label,
                            display,
                            ft.Row(
                                [start_pause, ft.OutlinedButton("Reset", on_click=on_reset)],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True,
                    ),
                ],
                expand=True,
            ),
            maximizable=False,
            expand=True,
        )
    )


def run() -> None:
    # Load before opening the window so a bad config fails fast with a readable error.
    ft.run(partial(main, config=load_config()))


if __name__ == "__main__":
    run()
