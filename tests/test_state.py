from pathlib import Path

import pytest

from tokolog_flet.state import load_last_profile, save_last_profile, state_path


def test_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "state.json"
    save_last_profile("work", path)
    assert load_last_profile(path) == "work"


@pytest.mark.parametrize("text", [None, "not json", "[]", '{"profile": 5}'])
def test_unreadable_is_empty(tmp_path: Path, text: str | None) -> None:
    path = tmp_path / "state.json"
    if text is not None:
        path.write_text(text)
    assert load_last_profile(path) == ""


def test_save_ignores_unwritable_path(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("")
    save_last_profile("work", tmp_path / "file" / "state.json")


def test_state_path_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert state_path() == tmp_path / "tokolog-flet" / "state.json"
