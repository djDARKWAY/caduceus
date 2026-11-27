import subprocess

import pytest

from caduceus.ui import window


def refuse_to_run(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("o tamanho da janela não devia ter sido alterado")


def test_in_windows_terminal_the_console_size_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WT_SESSION", "any-session")
    monkeypatch.setattr(subprocess, "run", refuse_to_run)
    monkeypatch.setattr(window, "_lock_resizing", refuse_to_run)

    window.fix_console_size()


def test_in_the_classic_console_the_size_is_fixed_and_locked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.setattr(window, "_is_classic_console", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: calls.append("mode"))
    monkeypatch.setattr(window, "_lock_resizing", lambda: calls.append("lock"))

    window.fix_console_size()

    assert calls == ["mode", "lock"]


def test_in_a_console_that_is_not_the_classic_one_the_size_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.setattr(window, "_is_classic_console", lambda: False)
    monkeypatch.setattr(subprocess, "run", refuse_to_run)
    monkeypatch.setattr(window, "_lock_resizing", refuse_to_run)

    window.fix_console_size()
