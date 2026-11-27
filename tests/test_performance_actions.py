from dataclasses import replace
from uuid import UUID

import pytest

from caduceus.controllers.keys import Key
from caduceus.controllers.menus import PERFORMANCE_MENU
from caduceus.controllers.navigation import Navigation, column_count, complete, loads_menu, press
from caduceus.maintenance.actions import Report, Step
from caduceus.maintenance.performance import (
    free_standby,
    optimize_drives,
    power_plan,
    restart_explorer,
)
from caduceus.maintenance.powershell import run_powershell


def performance_option(key: str) -> Navigation:
    index = next(i for i, item in enumerate(PERFORMANCE_MENU.items) if item.label_key == key)
    return Navigation(menus=(PERFORMANCE_MENU,), selected=(index,))


@pytest.mark.parametrize("existing", ["original", "copy", "missing"])
def test_high_performance_is_only_duplicated_if_neither_scheme_exists(
    monkeypatch: pytest.MonkeyPatch, existing: str
) -> None:
    schemes = {"original": power_plan._HIGH, "copy": power_plan._HIGH_COPY}
    monkeypatch.setattr(
        power_plan,
        "_scheme_name",
        lambda scheme: "High" if scheme == schemes.get(existing) else None,
    )
    commands: list[list[str]] = []

    def run(executable: str, arguments: list[str], _report: Report, _step_key: str) -> bool:
        commands.append([executable, *arguments])
        return True

    monkeypatch.setattr(power_plan, "run_system_tool", run)

    outcome = power_plan.set_high_performance(lambda _: None)

    original, copy = str(power_plan._HIGH), str(power_plan._HIGH_COPY)
    activate = ["powercfg.exe", "/setactive", original if existing == "original" else copy]
    duplicate = ["powercfg.exe", "/duplicatescheme", original, copy]
    assert commands == ([duplicate, activate] if existing == "missing" else [activate])
    assert not outcome.failures


def test_balanced_can_be_selected_in_basic_mode_and_the_active_plan_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = power_plan._HIGH_COPY

    def run(executable: str, arguments: list[str], _report: Report, _step_key: str) -> bool:
        nonlocal active
        assert executable == "powercfg.exe" and arguments[0] == "/setactive"
        active = UUID(arguments[1])
        return True

    monkeypatch.setattr(power_plan, "run_system_tool", run)
    monkeypatch.setattr(power_plan, "_active_scheme", lambda: active)
    parent = replace(performance_option("performance.power_plan"), administrator=False)
    submenu = press(parent, Key.ENTER)
    assert submenu.menu.title_key == "performance.power_plan.title"
    assert [item.state() for item in submenu.menu.items if item.state is not None] == [False, True]

    running = press(submenu, Key.ENTER)
    assert running.running is not None
    assert not running.running(lambda _: None).failures

    assert [item.state() for item in submenu.menu.items if item.state is not None] == [True, False]


def test_restart_explorer_closes_then_reopens_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def stop(*, force_if_unresponsive: bool) -> bool:
        assert force_if_unresponsive
        calls.append("stop")
        return True

    def start() -> bool:
        calls.append("start")
        return True

    monkeypatch.setattr(restart_explorer, "stop_explorer", stop)
    monkeypatch.setattr(restart_explorer, "start_explorer", start)
    at_restart = replace(performance_option("performance.restart_explorer"), administrator=False)
    running = press(at_restart, Key.ENTER)
    assert running.running is not None

    done = complete(running, running.running(lambda _: None))

    assert calls == ["stop", "start"]
    assert done.outcome is None and done.running is None


def test_standby_memory_still_shows_the_ram_gain_for_an_instant_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    measurements = iter((2 * 1024**2, 10 * 1024**2))
    monkeypatch.setattr(free_standby, "is_admin", lambda: True)
    monkeypatch.setattr(free_standby, "_free_memory_bytes", lambda: next(measurements))
    monkeypatch.setattr(free_standby, "_purge_standby", lambda: True)
    running = press(performance_option("performance.free_standby"), Key.ENTER)
    assert running.item.instant and running.running is not None

    done = complete(running, running.running(lambda _: None))

    assert done.outcome is not None
    assert done.outcome.bytes_freed == 8 * 1024**2
    assert done.outcome.freed_key == "performance.free_standby.gain"
    assert not done.outcome.items_counted


def test_standby_memory_without_administrator_does_not_touch_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_purge() -> bool:
        raise AssertionError("The standby list must not be purged")

    monkeypatch.setattr(free_standby, "is_admin", lambda: False)
    monkeypatch.setattr(free_standby, "_purge_standby", unexpected_purge)

    assert free_standby.free_standby_memory(lambda _: None).admin_required


def test_optimize_drives_loads_a_table_and_keeps_unknown_drives_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = """[
        {"letter":"D","name":"Media","id":"disk1","media":null,"size":2048,"free":1024},
        {"letter":"C","name":"Windows","id":"disk0","media":"SSD","size":1024,"free":512}
    ]"""
    monkeypatch.setattr(optimize_drives, "run_powershell", lambda _script: output)
    parent = performance_option("performance.optimize_drives")
    basic = replace(parent, administrator=False)
    assert not loads_menu(basic, Key.ENTER) and press(basic, Key.ENTER) == basic
    assert loads_menu(parent, Key.ENTER)

    table = press(parent, Key.ENTER)

    assert column_count(table.menu) == 4
    assert table.item.label == "C: Windows"
    assert table.item.cells == ("performance.optimize_drives.media.SSD", 1024, 512)
    assert table.item.slow and table.item.action is not None
    assert press(table, Key.DOWN).item.action is None


_STORAGE_FIXTURE = """
function Get-Disk {
    [pscustomobject]@{ Number = 0; BusType = 11; UniqueId = 'windows-disk' }
}
function Get-PhysicalDisk {
    [pscustomobject]@{ DeviceId = 0; UniqueId = 'unrelated'; MediaType = 3 }
    [pscustomobject]@{ DeviceId = 9; UniqueId = 'windows-disk'; MediaType = $currentMedia }
}
function Get-Partition {
    param($Volume, $ErrorAction)
    [pscustomobject]@{ DiskNumber = 0 }
}
function Get-Volume {
    param($DriveLetter)
    [pscustomobject]@{ ObjectId = $currentId; DriveType = 'Fixed' }
}
function Optimize-Volume {
    param($InputObject, [switch]$ReTrim, [switch]$Defrag)
    if ($InputObject.ObjectId -ne 'volume0' -or $ReTrim.IsPresent -eq $Defrag.IsPresent) { exit 2 }
    if ($ReTrim) { 'trim' }
    if ($Defrag) { 'defrag' }
}
"""


@pytest.mark.parametrize(
    ("media", "current_media", "current_id", "expected"),
    [
        ("SSD", 4, "volume0", "trim"),
        ("HDD", 3, "volume0", "defrag"),
        ("HDD", 4, "volume0", None),
        ("HDD", 3, "different-volume", None),
    ],
)
def test_the_optimizer_rechecks_media_and_identity_before_running_an_operation(
    monkeypatch: pytest.MonkeyPatch,
    media: str,
    current_media: int,
    current_id: str,
    expected: str | None,
) -> None:
    monkeypatch.setattr(optimize_drives, "is_admin", lambda: True)
    steps: list[Step] = []

    def fake_optimization(script: str, report: Report, key: str, values: dict[str, str]) -> bool:
        report(Step(key, 0, 0, values))
        fixture = (
            f"$currentMedia = {current_media}\n$currentId = '{current_id}'\n" + _STORAGE_FIXTURE
        )
        output = run_powershell(fixture + script)
        assert (output.strip() if output is not None else None) == expected
        return output is not None

    monkeypatch.setattr(optimize_drives, "run_powershell_with_progress", fake_optimization)
    drive = optimize_drives.Drive("C", "Windows", "volume0", media, 2048, 1024)

    outcome = optimize_drives.optimize_drive(drive)(steps.append)

    assert bool(outcome.failures) == (expected is None)
    assert steps == [
        Step(f"performance.optimize_drives.{media}.step", 0, 0, {"drive": drive.label})
    ]
