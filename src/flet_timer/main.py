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
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.window.width = 450
    page.window.height = 300

    timers: dict[str, Stopwatch] = {
        COUNTDOWN: Countdown(config.default_seconds),
        STOPWATCH: Stopwatch(),
    }
    current = COUNTDOWN
    timer = timers[current]
    events = EventLog(config.log_folder)

    mode = ft.SegmentedButton(
        selected=[COUNTDOWN],
        segments=[
            ft.Segment(value=COUNTDOWN, label="Timer", icon=ft.Icons.HOURGLASS_BOTTOM),
            ft.Segment(value=STOPWATCH, label="Stopwatch", icon=ft.Icons.TIMER),
        ],
    )
    display = ft.Text(timer.display(), size=64)
    start_pause = ft.FilledButton("Start")

    def render() -> None:
        events.update(current, timer)
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
        events.update(current, timer)
        timer.reset()
        events.update(current, timer)
        current = mode.selected[0]
        timer = timers[current]
        render()

    def on_start_pause(_: ft.Event[ft.Button]) -> None:
        # Note the state just before acting, so a pause or stop logs the exact time.
        events.update(current, timer)
        if timer.state is State.RUNNING:
            timer.pause()
            render()
        else:
            timer.start()
            page.run_task(tick)

    def on_reset(_: ft.Event[ft.OutlinedButton]) -> None:
        events.update(current, timer)
        timer.reset()
        render()

    mode.on_change = on_mode_change
    start_pause.on_click = on_start_pause
    page.add(
        mode,
        display,
        ft.Row(
            [start_pause, ft.OutlinedButton("Reset", on_click=on_reset)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )


def run() -> None:
    # Load before opening the window so a bad config fails fast with a readable error.
    ft.run(partial(main, config=load_config()))


if __name__ == "__main__":
    run()
