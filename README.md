# flet-timer

Functional play with [Flet UI](https://flet.dev).. a desktop countdown timer and stopwatch that logs to my wiki

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
uv run flet run src/flet_timer/main.py   # hot reload while developing
uv run flet-timer                        # plain run via entry point
```

Or press F5 in VS Code ("Flet: run app").

## Config

Optional. Settings are read from `~/.config/flet-timer/config.toml`
(or `$XDG_CONFIG_HOME/flet-timer/config.toml`); anything left out uses the default.
[config.example.toml](config.example.toml) lists every setting:

```sh
mkdir -p ~/.config/flet-timer 
cp config.example.toml ~/.config/flet-timer/config.toml
```

To use a different file, e.g. a local one while developing (`config.toml` is gitignored):

```sh
FLET_TIMER_CONFIG=config.toml uv run flet-timer
```

## Log

Every start, pause, resume, stop and finish is appended to a file per day in the log folder
(`~/.local/share/flet-timer/log/` unless `[log] folder` is set in the config):

```text
09:30:05  countdown  start   00:00
09:42:17  countdown  pause   12:12
09:55:05  countdown  finish  25:00
```

The last column is the time on the clock when the event happened.

## Check

```sh
uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest
```

`pre-commit` runs the same checks on commit, using the versions pinned in `uv.lock`.