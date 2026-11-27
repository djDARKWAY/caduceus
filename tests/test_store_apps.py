import json

import pytest

from caduceus.maintenance.apps import store_apps
from caduceus.maintenance.apps.store_apps import (
    StoreApp,
    parse_store_apps,
    repair_store_app,
    reset_store_app,
)

OUTPUT = json.dumps(
    [
        {"Name": "Zeta.App", "FullName": "Zeta.App_1.0.0.0_x64__abc", "Version": "1.0.0.0"},
        {"Name": "Alpha.App", "FullName": "Alpha.App_2.0.0.0_x64__abc", "Version": "2.0.0.0"},
        {"Name": "Evil", "FullName": "x'; Remove-Item C:\\ #", "Version": "1"},
    ]
)
APP = StoreApp("Alpha.App", "Alpha.App_2.0.0.0_x64__abc", "2.0.0.0")


def run_with(monkeypatch: pytest.MonkeyPatch, succeeds: bool) -> list[str]:
    commands: list[str] = []

    def fake_tool(_exe: str, arguments: list[str], *_args: object, **_kwargs: object) -> bool:
        commands.append(arguments[-1])
        return succeeds

    monkeypatch.setattr(store_apps, "run_system_tool", fake_tool)
    return commands


def test_store_apps_are_listed_by_name_and_unsafe_package_names_are_ignored() -> None:
    assert [app.name for app in parse_store_apps(OUTPUT)] == ["Alpha.App", "Zeta.App"]


@pytest.mark.parametrize("output", ["", "not json", "{}"])
def test_an_unreadable_store_list_gives_no_apps(output: str) -> None:
    assert parse_store_apps(output) == []


def test_repairing_registers_the_app_again_without_resetting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = run_with(monkeypatch, succeeds=True)

    outcome = repair_store_app(APP)(lambda _: None)

    assert "Add-AppxPackage" in commands[0]
    assert "Reset-AppxPackage" not in commands[0]
    assert APP.full_name in commands[0]
    assert outcome.items == 1


def test_resetting_runs_the_reset_of_that_package(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = run_with(monkeypatch, succeeds=True)

    outcome = reset_store_app(APP)(lambda _: None)

    assert "Reset-AppxPackage" in commands[0]
    assert outcome.rows[0].label_key == "category.reset_app"


def test_an_app_windows_could_not_repair_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    run_with(monkeypatch, succeeds=False)

    outcome = repair_store_app(APP)(lambda _: None)

    assert outcome.failures == ("Alpha.App",)
    assert outcome.items == 0
