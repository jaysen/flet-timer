"""The settings popup: edits the config file and hands back the result."""

from collections.abc import Callable
from pathlib import Path

import flet as ft

from tokolog_flet.config import (
    DEFAULT_PROFILE,
    SETTINGS,
    Config,
    ConfigError,
    Setting,
    add_profile,
    apply_settings,
    parse_config,
    profile_names,
    read_settings,
    remove_profile,
    save_settings,
    setting_key,
    setting_text,
)

# The window grows to this while the popup is open; the timer window is too small for it.
WINDOW_SIZE = (440, 620)
DIALOG_WIDTH = 360
SECTIONS = {"timer": ("Timer", ft.Icons.TIMER_OUTLINED), "log": ("Log", ft.Icons.NOTES)}
# Templates are easier to read, and their spacing easier to see, in a fixed-width font.
MONOSPACE = {"file", "date_format", "time_format", "line_format"}
NUMBER = ft.InputFilter(regex_string=r"^\d*\.?\d*$")


def open_settings(
    page: ft.Page,
    path: Path,
    on_saved: Callable[[Config], None],
    on_closed: Callable[[], None],
    profile: str = DEFAULT_PROFILE,
) -> None:
    """Edit ``path``, starting on ``profile``; edits to every profile are saved together."""
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

    selected = profile if profile in profile_names(data) else DEFAULT_PROFILE

    def inherited(setting: Setting) -> str:
        """What a blank field means: the built-in default, or the default profile's value."""
        if selected == DEFAULT_PROFILE:
            return setting.default
        return setting_text(data, setting) or setting.default

    def load_fields() -> None:
        named = selected != DEFAULT_PROFILE
        for setting in SETTINGS:
            field = fields[setting.name]
            hint = inherited(setting)
            field.value = setting_text(data, setting, selected)
            field.hint_text = hint
            # The label covers the hint until the field is focused, so the tooltip says it too.
            field.tooltip = f"{'From default' if named else 'Default'}: {hint}\n{setting.help}"
            field.error = None
            clear_buttons[setting.name].tooltip = (
                "Use the default profile's value" if named else "Use the default"
            )
            sync_clear_button(setting.name)

    def store_fields() -> bool:
        """Keep what the fields say in ``data``; False, with the error shown, if unusable."""
        nonlocal data
        try:
            data = apply_settings(data, field_values(), selected)
        except ConfigError as e:
            show_error(str(e))
            return False
        return True

    def field_values() -> dict[str, str]:
        return {key: field.value or "" for key, field in fields.items()}

    def make_field(setting: Setting) -> ft.TextField:
        key = setting.name
        clear_buttons[key] = ft.IconButton(
            ft.Icons.CLOSE,
            icon_size=14,
            on_click=lambda _: clear_field(key),
            style=ft.ButtonStyle(padding=0),
            width=24,
            height=24,
        )
        field = ft.TextField(
            label=setting.label,
            hint_style=ft.TextStyle(color=ft.Colors.OUTLINE),
            error_max_lines=3,
            dense=True,
            text_size=11,
            border=ft.OutlineInputBorder(border_radius=8),
            suffix=clear_buttons[key],
            on_change=on_change,
        )
        if key in MONOSPACE:
            field.text_style = ft.TextStyle(font_family="monospace")
        if key == "default_minutes":
            field.input_filter = NUMBER
            field.keyboard_type = ft.KeyboardType.NUMBER
        fields[key] = field
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
        return [heading, *(make_field(s) for s in SETTINGS if s.group == name)]

    profile_picker = ft.Dropdown(
        label="Profile",
        dense=True,
        text_size=12,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=8),
        tooltip="Which profile the fields below set",
    )
    delete_button = ft.IconButton(
        ft.Icons.DELETE_OUTLINE, icon_size=18, tooltip="Delete this profile"
    )
    new_name = ft.TextField(
        label="New profile name",
        dense=True,
        text_size=12,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=8),
    )
    new_row = ft.Row(
        [
            new_name,
            ft.IconButton(ft.Icons.CHECK, icon_size=18, tooltip="Add", on_click=lambda _: add()),
            ft.IconButton(
                ft.Icons.CLOSE, icon_size=18, tooltip="Cancel", on_click=lambda _: hide_new()
            ),
        ],
        spacing=0,
        visible=False,
    )
    inherit_note = ft.Text(
        "Blank fields use the default profile's value.", size=11, color=ft.Colors.OUTLINE
    )

    def sync_profiles() -> None:
        profile_picker.options = [
            ft.DropdownOption(key=name, text=name)
            for name in [DEFAULT_PROFILE, *profile_names(data)]
        ]
        profile_picker.value = selected
        delete_button.visible = inherit_note.visible = selected != DEFAULT_PROFILE

    def select(name: str) -> None:
        nonlocal selected
        selected = name
        sync_profiles()
        load_fields()
        show_banner("")

    def on_profile_select(_: ft.Event[ft.Dropdown]) -> None:
        if store_fields():
            select(profile_picker.value or DEFAULT_PROFILE)
        else:
            profile_picker.value = selected
        page.update()

    async def on_new(_: ft.Event[ft.IconButton]) -> None:
        new_name.value = ""
        new_name.error = None
        new_row.visible = True
        page.update()
        await new_name.focus()

    def hide_new() -> None:
        new_row.visible = False
        page.update()

    def add() -> None:
        nonlocal data
        if not store_fields():
            page.update()
            return
        try:
            data = add_profile(data, new_name.value or "")
        except ConfigError as e:
            new_name.error = str(e)
            page.update()
            return
        new_row.visible = False
        select((new_name.value or "").strip())
        page.update()

    def on_delete(_: ft.Event[ft.IconButton]) -> None:
        # Nothing is written until Save, so Cancel brings the profile back.
        nonlocal data
        data = remove_profile(data, selected)
        select(DEFAULT_PROFILE)
        page.update()

    new_button = ft.IconButton(ft.Icons.ADD, icon_size=18, tooltip="New profile", on_click=on_new)
    profile_picker.on_select = on_profile_select
    delete_button.on_click = on_delete
    new_name.on_submit = lambda _: add()

    def on_save(_: ft.Event[ft.Button]) -> None:
        if not store_fields():
            page.update()
            return
        try:
            config = parse_config(data, path)
            save_settings(path, data)
        except ConfigError as e:
            show_error(str(e))
            return
        except OSError as e:
            show_banner(f"Could not save: {e.strerror or e}")
            page.update()
            return
        page.pop_dialog()
        on_saved(config)

    def show_error(message: str) -> None:
        # Put the message under the field it is about, if it is on show.
        message = _without_path(message, path)
        setting = next((s for s in SETTINGS if _is_about(message, setting_key(s, selected))), None)
        if setting:
            detail = message.removeprefix(setting_key(setting, selected)).lstrip(": ")
            fields[setting.name].error = detail[:1].upper() + detail[1:]
            show_banner("")
        else:
            show_banner(message)
        page.update()

    def on_reset_all(_: ft.Event[ft.TextButton]) -> None:
        # Only the profile on show; the others keep what they set.
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
    content = ft.Column(
        [
            path_row,
            # Room on the right so the scrollbar doesn't sit on the fields.
            ft.Container(
                ft.Column(
                    [
                        ft.Row([profile_picker, new_button, delete_button], spacing=0),
                        new_row,
                        inherit_note,
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
    )
    # The fields only exist once section() has built them.
    sync_profiles()
    load_fields()
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.Icons.SETTINGS_OUTLINED), ft.Text("Settings", size=19)],
                spacing=10,
            ),
            content=content,
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            content_padding=ft.Padding.only(left=24, right=24, top=20, bottom=0),
            inset_padding=16,
            # Every way of closing ends here, including Esc.
            on_dismiss=lambda _: on_closed(),
        )
    )


def _is_about(message: str, key: str) -> bool:
    """Whether ``message`` starts with ``key`` itself, not a longer key it prefixes."""
    return message.startswith(key) and message[len(key) : len(key) + 1] in (" ", ":")


def _without_path(message: str, path: Path) -> str:
    """ConfigError messages start with the file; the popup already shows it."""
    return message.removeprefix(f"{path}: ")
