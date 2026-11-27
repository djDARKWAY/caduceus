import ctypes
import os
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


PROCESSES = [
    (10, 1, "explorer.exe"),
    (20, 10, "powershell.exe"),
    (30, 20, "python.exe"),
    (40, 10, "code.exe"),
    (50, 40, "python.exe"),
    (60, 70, "python.exe"),
]


@pytest.mark.parametrize(("own_id", "expected"), [(30, 20), (50, None), (60, None), (99, None)])
def test_only_a_real_shell_that_launched_the_app_is_closed(
    own_id: int, expected: int | None
) -> None:
    assert window.launching_shell(PROCESSES, own_id) == expected


def test_nothing_is_closed_when_the_app_was_not_launched_from_a_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(window, "_running_processes", lambda: PROCESSES)
    monkeypatch.setattr(os, "getpid", lambda: 50)
    monkeypatch.setattr(ctypes.windll.kernel32, "TerminateProcess", refuse_to_run)

    window.close_launching_shell()


def test_the_real_process_list_includes_this_one() -> None:
    own = [
        name
        for process_id, _parent, name in window._running_processes()
        if process_id == os.getpid()
    ]

    assert own and own[0].startswith("python")
