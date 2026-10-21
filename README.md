# flet-timer

Functional play with [Flet UI](https://flet.dev).. a desktop timer that logs to my wiki

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

## Check

```sh
uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest
```

`pre-commit` runs the same checks on commit, using the versions pinned in `uv.lock`.