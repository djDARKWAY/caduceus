import msvcrt
from collections.abc import Iterator

import pytest

from caduceus.ui import Key, next_index, read_key


def press(monkeypatch: pytest.MonkeyPatch, *chars: str) -> Key:
    typed: Iterator[str] = iter(chars)
    monkeypatch.setattr(msvcrt, "getwch", lambda: next(typed))
    return read_key()


def test_down_on_the_last_option_goes_to_the_first() -> None:
    assert next_index(3, Key.DOWN, 4) == 0


def test_up_on_the_first_option_goes_to_the_last() -> None:
    assert next_index(0, Key.UP, 4) == 3


def test_arrows_move_one_option_at_a_time() -> None:
    assert next_index(1, Key.DOWN, 4) == 2
    assert next_index(2, Key.UP, 4) == 1


def test_other_keys_keep_the_selected_option() -> None:
    assert next_index(2, Key.OTHER, 4) == 2
    assert next_index(2, Key.BACK, 4) == 2


def test_arrow_keys_are_read_as_up_and_down(monkeypatch: pytest.MonkeyPatch) -> None:
    assert press(monkeypatch, "\xe0", "H") is Key.UP
    assert press(monkeypatch, "\x00", "P") is Key.DOWN


def test_enter_selects_and_backspace_goes_back(monkeypatch: pytest.MonkeyPatch) -> None:
    assert press(monkeypatch, "\r") is Key.ENTER
    assert press(monkeypatch, "\x08") is Key.BACK


@pytest.mark.parametrize("char", ["q", "Q", "\x03"])
def test_q_and_ctrl_c_quit_the_application(monkeypatch: pytest.MonkeyPatch, char: str) -> None:
    assert press(monkeypatch, char) is Key.QUIT


def test_unknown_keys_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    assert press(monkeypatch, "x") is Key.OTHER
    assert press(monkeypatch, "\xe0", "K") is Key.OTHER
