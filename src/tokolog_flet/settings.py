"""The settings popup: edits the config file and hands back the result."""

from collections.abc import Callable
from pathlib import Path

import flet as ft

from tokolog_flet.config import (
    SETTINGS,
    Config,
    ConfigError,
    Setting,
    apply_settings,
    parse_config,
    read_settings,
    save_settings,
    setting_text,
)

# The window grows to this while the popup is open; the timer window is too small for it.
WINDOW_SIZE = (440, 620)
DIALOG_WIDTH = 360
SECTIONS = {"timer": ("Timer", ft.Icons.TIMER_OUTLINED), "log": ("Log", ft.Icons.NOTES)}
# Templates are easier to read, and their spacing easier to see, in a fixed-width font.
MONOSPACE = {"log.file", "log.date_format", "log.time_format", "log.line_format"}
NUMBER = ft.InputFilter(regex_string=r"^\d*\.?\d*$")


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
        problem = f"{_without_path(str(e), path)}\nSaving will replace the file."
    else:
        problem = ""

    fields: dict[str, ft.TextField] = {}
    clear_buttons: dict[str, ft.IconButton] = {}
    banner_text = ft.Text(problem, size=11, color=ft.Colors.ON_ERROR_CONTAINER)
    banner = ft.Container(
        ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, size=16, color=ft.Colors.ERROR), banner_text]),
        bgcolor=ft.Colors.ERROR_CONTAINER,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        visible=bool(problem),
    )

    def show_banner(message: str) -> None:
        banner_text.value = message
        banner.visible = bool(message)

    def sync_clear_button(key: str) -> None:
        clear_buttons[key].visible = bool(fields[key].value)

    def on_change(e: ft.Event[ft.TextField]) -> None:
        key = next(k for k, f in fields.items() if f is e.control)
        e.control.error = None
        sync_clear_button(key)
        e.control.update()

    def clear_field(key: str) -> None:
        fields[key].value = ""
        fields[key].error = None
        sync_clear_button(key)
        page.update()

    def make_field(setting: Setting) -> ft.TextField:
        key = setting.key
        clear_buttons[key] = ft.IconButton(
            ft.Icons.CLOSE,
            icon_size=14,
            tooltip="Use the default",
            on_click=lambda _: clear_field(key),
            style=ft.ButtonStyle(padding=0),
            width=24,
            height=24,
        )
        field = ft.TextField(
            label=setting.label,
            value=setting_text(data, setting),
            hint_text=setting.default,
            hint_style=ft.TextStyle(color=ft.Colors.OUTLINE),
            # The label covers the hint until the field is focused, so the tooltip says it too.
            tooltip=f"Default: {setting.default}\n{setting.help}",
            error_max_lines=3,
            dense=True,
            text_size=11,
            border=ft.OutlineInputBorder(border_radius=8),
            suffix=clear_buttons[key],
            on_change=on_change,
        )
        if key in MONOSPACE:
            field.text_style = ft.TextStyle(font_family="monospace")
        if key == "timer.default_minutes":
            field.input_filter = NUMBER
            field.keyboard_type = ft.KeyboardType.NUMBER
        fields[key] = field
        sync_clear_button(key)
        return field

    def section(name: str) -> list[ft.Control]:
        title, icon = SECTIONS[name]
        heading = ft.Row(
            [
                ft.Icon(icon, size=16, color=ft.Colors.PRIMARY),
                ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
            ],
            spacing=6,
        )
        return [heading, *(make_field(s) for s in SETTINGS if s.section == name)]

    def on_save(_: ft.Event[ft.Button]) -> None:
        values = {key: field.value or "" for key, field in fields.items()}
        try:
            new = apply_settings(data, values)
            config = parse_config(new, path)
            save_settings(path, new)
        except ConfigError as e:
            show_error(_without_path(str(e), path))
            return
        except OSError as e:
            show_banner(f"Could not save: {e.strerror or e}")
            page.update()
            return
        page.pop_dialog()
        on_saved(config)

    def show_error(message: str) -> None:
        # Put the message under the field it is about, if there is one.
        setting = next((s for s in SETTINGS if message.startswith(s.key)), None)
        if setting:
            detail = message.removeprefix(setting.key).lstrip(": ")
            fields[setting.key].error = detail[:1].upper() + detail[1:]
            show_banner("")
        else:
            show_banner(message)
        page.update()

    def on_reset_all(_: ft.Event[ft.TextButton]) -> None:
        for key, field in fields.items():
            field.value = ""
            field.error = None
            sync_clear_button(key)
        show_banner("")
        page.update()

    def on_cancel(_: ft.Event[ft.TextButton]) -> None:
        page.pop_dialog()

    path_row = ft.Row(
        [
            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=14, color=ft.Colors.OUTLINE),
            ft.Text(str(path), size=11, color=ft.Colors.OUTLINE, selectable=True, expand=True),
        ],
        spacing=6,
        tooltip="Saving rewrites this file; comments in it are not kept",
    )
    actions: list[ft.Control] = [
        ft.TextButton("Reset all", icon=ft.Icons.RESTART_ALT, on_click=on_reset_all),
        ft.Row(
            [
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.FilledButton("Save", on_click=on_save),
            ],
            spacing=6,
            tight=True,
        ),
    ]
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.Icons.SETTINGS_OUTLINED), ft.Text("Settings", size=19)],
                spacing=10,
            ),
            content=ft.Column(
                [
                    path_row,
                    # Room on the right so the scrollbar doesn't sit on the fields.
                    ft.Container(
                        ft.Column(
                            [
                                *section("timer"),
                                ft.Container(height=4),
                                *section("log"),
                                banner,
                            ],
                            spacing=12,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                        padding=ft.Padding.only(right=14),
                    ),
                ],
                width=DIALOG_WIDTH,
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                tight=True,
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            content_padding=ft.Padding.only(left=24, right=24, top=20, bottom=0),
            inset_padding=16,
            # Every way of closing ends here, including Esc.
            on_dismiss=lambda _: on_closed(),
        )
    )


def _without_path(message: str, path: Path) -> str:
    """ConfigError messages start with the file; the popup already shows it."""
    return message.removeprefix(f"{path}: ")
