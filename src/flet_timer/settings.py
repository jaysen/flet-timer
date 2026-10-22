"""The settings popup: edits the config file and hands back the result."""

from collections.abc import Callable
from pathlib import Path

import flet as ft

from flet_timer.config import (
    SETTINGS,
    Config,
    ConfigError,
    apply_settings,
    parse_config,
    read_settings,
    save_settings,
    setting_text,
)

DIALOG_WIDTH = 340
HELP = "Leave a field empty to use its default."


def open_settings(
    page: ft.Page,
    path: Path,
    on_saved: Callable[[Config], None],
    on_closed: Callable[[], None],
) -> None:
    try:
        data = read_settings(path)
    except ConfigError as e:
        data = {}
        problem = f"{e}\nSaving will replace the file."
    else:
        problem = ""

    fields = {
        s.key: ft.TextField(
            label=s.label,
            value=setting_text(data, s),
            hint_text=s.default,
            dense=True,
            text_size=13,
        )
        for s in SETTINGS
    }
    error = ft.Text(problem, color=ft.Colors.ERROR, size=12, visible=bool(problem))

    def show_error(message: str) -> None:
        error.value = message
        error.visible = bool(message)
        page.update()

    def on_save(_: ft.Event[ft.Button]) -> None:
        values = {key: field.value or "" for key, field in fields.items()}
        try:
            new = apply_settings(data, values)
            config = parse_config(new, path)
            save_settings(path, new)
        except ConfigError as e:
            show_error(str(e))
            return
        except OSError as e:
            show_error(f"{path}: {e.strerror or e}")
            return
        page.pop_dialog()
        on_closed()
        on_saved(config)

    def on_clear(_: ft.Event[ft.TextButton]) -> None:
        for field in fields.values():
            field.value = ""
        show_error("")

    def on_cancel(_: ft.Event[ft.TextButton]) -> None:
        page.pop_dialog()
        on_closed()

    actions: list[ft.Control] = [
        ft.TextButton("Clear all", on_click=on_clear),
        ft.TextButton("Cancel", on_click=on_cancel),
        ft.FilledButton("Save", on_click=on_save),
    ]
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Settings", size=18),
            content=ft.Column(
                [
                    ft.Text(f"{path}\n{HELP}", size=11, color=ft.Colors.OUTLINE),
                    *fields.values(),
                    error,
                ],
                width=DIALOG_WIDTH,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                tight=True,
            ),
            actions=actions,
        )
    )
