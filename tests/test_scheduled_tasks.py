import json
import subprocess

import pytest

from caduceus.maintenance.memory import scheduled_tasks
from caduceus.maintenance.memory.scheduled_tasks import TaskEntry, parse_tasks, toggle_task

OUTPUT = json.dumps(
    [
        {
            "Name": "ZTool",
            "Folder": "\\",
            "Enabled": False,
            "Trigger": "boot",
            "Command": "C:\\Tools\\ztool.exe --run",
        },
        {
            "Name": "AcPower",
            "Folder": "\\ASUS\\",
            "Enabled": True,
            "Trigger": "logon",
            "Command": "",
        },
    ]
)


def make_entry(name: str = "Example", enabled: bool = True) -> TaskEntry:
    return TaskEntry(name, "\\Vendor\\", "app.exe", "logon", enabled, None)


class FakeResult:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_tasks_are_listed_by_name_with_their_trigger_and_state() -> None:
    tasks = parse_tasks(OUTPUT, {})

    assert [task.name for task in tasks] == ["AcPower", "ZTool"]
    assert [task.trigger for task in tasks] == ["logon", "boot"]
    assert [task.enabled for task in tasks] == [True, False]
    assert tasks[0].full_name == "\\ASUS\\AcPower"


@pytest.mark.parametrize("output", ["", "not json", "{}", '[{"Name": "NoFolder"}]'])
def test_an_unreadable_task_list_gives_no_tasks(output: str) -> None:
    assert parse_tasks(output, {}) == []


def test_only_updater_tasks_can_be_switched_off_with_safe_mode_on() -> None:
    assert not TaskEntry(
        "GoogleUpdateTaskMachine", "\\", "", "logon", True, None
    ).needs_safe_mode_off
    assert make_entry("VpnClientStart").needs_safe_mode_off


def test_switching_a_task_off_without_administrator_asks_for_it_and_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_to_run(*_args: object, **_kwargs: object) -> FakeResult:
        raise AssertionError("nothing may run without administrator")

    monkeypatch.setattr(scheduled_tasks, "is_admin", lambda: False)
    monkeypatch.setattr(subprocess, "run", refuse_to_run)
    entry = make_entry()

    outcome = toggle_task(entry)(lambda _: None)

    assert outcome.admin_required == ("Example",)
    assert entry.enabled


def test_switching_a_task_off_disables_it_and_switching_it_on_enables_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> FakeResult:
        commands.append(command)
        return FakeResult(0)

    monkeypatch.setattr(scheduled_tasks, "is_admin", lambda: True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    entry = make_entry()

    toggle_task(entry)(lambda _: None)
    assert not entry.enabled
    toggle_task(entry)(lambda _: None)

    assert entry.enabled
    assert [command[-3:] for command in commands] == [
        ["/TN", "\\Vendor\\Example", "/DISABLE"],
        ["/TN", "\\Vendor\\Example", "/ENABLE"],
    ]


def test_a_task_that_windows_refuses_to_change_is_reported_and_keeps_its_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scheduled_tasks, "is_admin", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: FakeResult(1))
    entry = make_entry()

    outcome = toggle_task(entry)(lambda _: None)

    assert outcome.failures == ("Example",)
    assert entry.enabled
