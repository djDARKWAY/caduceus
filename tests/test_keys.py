import msvcrt
from collections.abc import Iterator

import pytest

from caduceus.controllers.keys import Key, read_key


def press(monkeypatch: pytest.MonkeyPatch, *chars: str) -> Key:
    typed: Iterator[str] = iter(chars)
    monkeypatch.setattr(msvcrt, "getwch", lambda: next(typed))
    return read_key()


def test_arrow_keys_are_read_as_up_and_down(monkeypatch: pytest.MonkeyPatch) -> None:
    assert press(monkeypatch, "\xe0", "H") is Key.UP
    assert press(monkeypatch, "\x00", "P") is Key.DOWN


def test_enter_selects_and_backspace_goes_back(monkeypatch: pytest.MonkeyPatch) -> None:
    assert press(monkeypatch, "\r") is Key.ENTER
    assert press(monkeypatch, "\x08") is Key.BACK


@pytest.mark.parametrize("char", ["\x03"])
def test_ctrl_c_quits_the_application(monkeypatch: pytest.MonkeyPatch, char: str) -> None:
    assert press(monkeypatch, char) is Key.QUIT


def test_unknown_keys_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    assert press(monkeypatch, "x") is Key.OTHER
    assert press(monkeypatch, "\xe0", "K") is Key.OTHER
