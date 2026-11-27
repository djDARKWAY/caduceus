import sys

import pytest

from caduceus.maintenance import admin


def fake_shell_execute(result: int, calls: list[tuple[object, ...]]) -> object:
    def execute(*arguments: object) -> int:
        calls.append(arguments)
        return result

    return execute


def test_restarting_asks_windows_for_administrator_and_then_asks_the_app_to_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(admin, "_shell_execute", fake_shell_execute(42, calls))

    outcome = admin.restart_as_administrator(lambda _: None)

    assert outcome.quit_after
    assert calls[0][1:4] == ("runas", sys.executable, "-m caduceus")


@pytest.mark.parametrize("windows_answer", [0, 5, 32])
def test_if_windows_does_not_start_it_the_app_stays_open_with_a_notice(
    windows_answer: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin, "_shell_execute", fake_shell_execute(windows_answer, []))

    outcome = admin.restart_as_administrator(lambda _: None)

    assert not outcome.quit_after
    assert outcome.notice == "notice.restart_cancelled"
