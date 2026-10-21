"""Flet UI entry point. Keep this thin: behaviour lives in timer.py."""

import asyncio

import flet as ft

from flet_timer.timer import Countdown, State, format_seconds

DEFAULT_SECONDS = 5 * 60
TICK_SECONDS = 0.2


def main(page: ft.Page) -> None:
    page.title = "Flet Timer"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    countdown = Countdown(DEFAULT_SECONDS)
    display = ft.Text(format_seconds(countdown.remaining), size=64)
    start_pause = ft.FilledButton("Start")

    def render() -> None:
        display.value = format_seconds(countdown.remaining)
        start_pause.content = "Pause" if countdown.state is State.RUNNING else "Start"
        start_pause.disabled = countdown.state is State.FINISHED
        page.update()

    async def tick() -> None:
        while countdown.state is State.RUNNING:
            render()
            await asyncio.sleep(TICK_SECONDS)
        render()

    def on_start_pause(_: ft.Event[ft.Button]) -> None:
        if countdown.state is State.RUNNING:
            countdown.pause()
            render()
        else:
            countdown.start()
            page.run_task(tick)

    def on_reset(_: ft.Event[ft.OutlinedButton]) -> None:
        countdown.reset()
        render()

    start_pause.on_click = on_start_pause
    page.add(
        display,
        ft.Row(
            [start_pause, ft.OutlinedButton("Reset", on_click=on_reset)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )


def run() -> None:
    ft.run(main)


if __name__ == "__main__":
    run()
