# Tok-o-log (flet)

Functional play with [Flet UI](https://flet.dev).. a desktop timer that logs, in a configurable format, to a configurable file - in my case: a journal page in wiki

## Features

- **Timer + stopwatch modes** with quick mode switching.
- **Flexible countdown input** (`25`, `1:30`, `1:00:00`, `1h30m`) and inline editing.
- **Start / pause / resume / reset flow** with elapsed/display time tracking.
- **Compact view toggle** for a minimal always-visible timer window.
- **Editable label** per session, used in log output.
- **Named profiles**, each with its own log file, line format and countdown default.
- **Configurable settings file** for defaults and logging behavior.
- **Daily log files** with templated file names and line formats.
- **Customizable placeholders** for `{date}`, `{time}`, `{mode}`, `{event}`, `{elapsed}`, `{display}`, `{label}` and `{profile}`.


## Setup

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is not installed
uv sync                                           # creates .venv, installs Python 3.12 if needed

uv run pre-commit install                         # .pre-commit-config.yaml  
```

Open the folder in VS Code and accept the recommended extensions; the interpreter is
preselected as `.venv`.

## Run

```sh
uv run flet run src/tokolog_flet/main.py   # hot reload while developing
uv run tokolog-flet                        # plain run via entry point
```

Or press F5 in VS Code ("Flet: run app").

To set the countdown, click its time and type e.g. `25` (minutes), `1:30`, `1:00:00` or
`1h30m`, then press Enter (Esc cancels). It starts at `[timer] default_minutes` from the config.

The shrink icon next to the gear switches to a compact view that shows just the
label, time and Start/Reset, e.g. to keep a running timer in a corner. The same button
(now an expand icon) brings back the full view.

## Config

Optional. Settings are read from `~/.config/tokolog-flet/config.toml`
(or `$XDG_CONFIG_HOME/tokolog-flet/config.toml`); anything left out uses the default.
[config.example.toml](config.example.toml) lists every setting:

```sh
mkdir -p ~/.config/tokolog-flet 
cp config.example.toml ~/.config/tokolog-flet/config.toml
```

The gear icon in the top bar opens a settings popup showing what the file sets. Edit a field to change it, empty one to go back to its default (the default shows as the hint), then Save. Changes apply straight away. Saving rewrites the file, so comments in it are lost; keys the app doesn't know are kept.

To use a different file, e.g. a local one while developing (`config.toml` is gitignored):

```sh
TOKOLOG_FLET_CONFIG=config.toml uv run tokolog-flet
```

## Log

Every start, pause, resume, stop and finish is appended to a file per day in the log folder
(`~/.local/share/tokolog-flet/log/` unless `[log] folder` is set in the config):

```text
09:30:05  countdown  start   00:00
09:42:17  countdown  pause   12:12
09:55:05  countdown  finish  25:00
```

The last column is how much time had run when the event happened.

The file name defaults to `2026-10-21.log`. To change it, e.g. to `flet-20261021.md`:

```toml
[log]
file = "flet-{date}.md"
date_format = "YYYYMMDD"   # YYYY, YY, MM and DD are replaced
time_format = "HH:mm"      # HH, hh (12-hour), mm, ss and AM (AM/PM) are replaced
line_format = "- {time} {mode} {event} {display}"
```

`line_format` can use `{date}`, `{time}`, `{mode}`, `{event}`, `{elapsed}`, `{display}`
(what the timer showed, so time left for a countdown), `{label}` (the label typed in
the app, or the mode if none) and `{profile}`. `file` can use `{date}`, `{label}` and
`{profile}`. See [config.example.toml](config.example.toml) for details.

## Profiles

A profile is a named set of log settings, e.g. one for your journal and one for a work
timesheet. The label stays separate, so any label can be logged under any profile.
`[timer]` and `[log]` make up the `default` profile. Each `[profiles.<name>]` table
overrides any of their keys and takes the rest from them:

```toml
[profiles.work]
default_minutes = 50
folder = "~/work/timesheets"
file = "timesheet-{date}.csv"
line_format = "{date},{time},{label},{event},{elapsed}"
```

Once the config has a profile, a picker appears at the bottom of the window. It is
locked while a timer runs or is paused, so a session stays in one log. Switching changes
where the next events go, and an untouched countdown takes the profile's default minutes.
The app reopens on the profile picked last, which it remembers in
`~/.local/state/tokolog-flet/state.json`.

Profiles can also be added, edited and deleted in the settings popup. Pick one at the
top. A blank field takes the default profile's value, shown as the hint.

## Check

```sh
uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest
```

`pre-commit` runs the same checks on commit, using the versions pinned in `uv.lock`.