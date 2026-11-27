import io
import subprocess
import time
import winreg
from pathlib import Path

import pytest

from caduceus.maintenance.actions import Action, Step
from caduceus.maintenance.free_space import components, hibernation, restore_points, windows_old
from caduceus.maintenance.system_tool import parse_percent, run_system_tool


def refuse_to_launch(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("nenhum processo devia ter sido lançado")


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (b"[=====                      10.0%                          ]", 10),
        (b"\r[==========================100.0%==========================]\r\n", 100),
        (b"[===  5.0% ]\r[====  12.5% ]", 12),
        (b"Deployment Image Servicing and Management tool", None),
    ],
)
def test_dism_progress_is_read_from_its_output(output: bytes, expected: int | None) -> None:
    assert parse_percent(output) == expected


def test_component_cleanup_without_administrator_asks_for_it_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(components, "is_admin", lambda: False)
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)

    outcome = components.clean_components(lambda _: None)

    assert outcome.admin_required
    assert outcome.rows == ()


def test_windows_old_without_administrator_asks_for_it_and_touches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "Windows.old").mkdir()
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(windows_old, "is_admin", lambda: False)
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)
    monkeypatch.setattr(winreg, "OpenKey", refuse_to_launch)

    outcome = windows_old.clean_windows_old(lambda _: None)

    assert outcome.admin_required == (str(tmp_path / "Windows.old"),)
    assert (tmp_path / "Windows.old").is_dir()


def test_windows_old_that_does_not_exist_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)

    outcome = windows_old.clean_windows_old(lambda _: None)

    assert (outcome.items, outcome.bytes_freed, outcome.rows) == (0, 0, ())


def test_the_cleanup_profile_is_never_one_that_another_handler_already_uses() -> None:
    taken = {6471, 6472, 6474}

    assert windows_old.free_profile(taken) == 6473
    assert windows_old.free_profile(set()) == 6471


def test_without_any_free_cleanup_profile_nothing_runs() -> None:
    with pytest.raises(OSError, match="perfis"):
        windows_old.free_profile(set(range(10000)))


@pytest.mark.parametrize(
    "action",
    [
        restore_points.clean_restore_points,
        hibernation.turn_off_hibernation,
        hibernation.turn_on_hibernation,
    ],
)
def test_system_setting_actions_without_administrator_ask_for_it_and_run_nothing(
    action: Action, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(restore_points, "is_admin", lambda: False)
    monkeypatch.setattr(hibernation, "is_admin", lambda: False)
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)

    outcome = action(lambda _: None)

    assert outcome.admin_required
    assert outcome.rows == ()


class FakeProcess:
    """Um processo que já terminou, com o código de saída dado."""

    def __init__(self, command: list[str], exit_code: int, output: bytes = b"") -> None:
        self.command = command
        self.stdout = io.BytesIO(output)
        self.exit_code = exit_code

    def __enter__(self) -> "FakeProcess":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self) -> int:
        return self.exit_code


def test_restore_points_are_deleted_for_the_system_drive_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[FakeProcess] = []

    def fake_popen(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(FakeProcess(command, 0))
        return launched[-1]

    monkeypatch.setenv("SystemDrive", "C:")
    monkeypatch.setattr(restore_points, "is_admin", lambda: True)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    outcome = restore_points.clean_restore_points(lambda _: None)

    assert [process.command[1:] for process in launched] == [
        ["delete", "shadows", "/for=C:", "/all", "/quiet"]
    ]
    assert outcome.rows[0].label_key == "category.restore_points"


def test_a_failed_system_tool_is_reported_as_a_failure_and_not_as_space_freed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hibernation, "is_admin", lambda: True)
    monkeypatch.setattr(subprocess, "Popen", lambda command, **_kwargs: FakeProcess(command, 1))

    outcome = hibernation.turn_off_hibernation(lambda _: None)

    assert outcome.failures
    assert outcome.rows == ()


def test_a_running_tool_reports_progress_under_the_step_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SlowProcess(FakeProcess):
        polls = 0

        def poll(self) -> int | None:
            SlowProcess.polls += 1
            return None if SlowProcess.polls < 3 else self.exit_code

    monkeypatch.setattr(
        subprocess, "Popen", lambda command, **_kwargs: SlowProcess(command, 0, b"[== 42.0% ]")
    )
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    steps: list[Step] = []

    assert run_system_tool(
        "dism.exe", [], steps.append, "cleanup.components.step", reports_percent=True
    )
    assert all(step.text_key == "cleanup.components.step" for step in steps)
    assert (42, 100) in [(step.done, step.total) for step in steps]
    assert (0, 0) in [(step.done, step.total) for step in steps]  # a barra anima-se até ao fim


@pytest.mark.parametrize(
    ("action", "expected_argument"),
    [(hibernation.turn_off_hibernation, "off"), (hibernation.turn_on_hibernation, "on")],
)
def test_each_hibernation_option_runs_its_own_command(
    action: Action, expected_argument: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched: list[FakeProcess] = []

    def fake_popen(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(FakeProcess(command, 0))
        return launched[-1]

    monkeypatch.setattr(hibernation, "is_admin", lambda: True)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    outcome = action(lambda _: None)

    assert [process.command[1:] for process in launched] == [["/hibernate", expected_argument]]
    assert len(outcome.rows) == 1
