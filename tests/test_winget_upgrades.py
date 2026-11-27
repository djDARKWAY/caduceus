import subprocess

import pytest

from caduceus.maintenance.apps import winget_upgrades
from caduceus.maintenance.apps.winget_upgrades import (
    UpgradableApp,
    list_upgradable,
    parse_upgradable,
    update_apps,
)

TABLE = (
    "  - \r   \\ \r"
    "Nome                          ID                     Versão       Disponível   Origem\r\n"
    "------------------------------------------------------------------------------------\r\n"
    "GitHub CLI                    GitHub.cli             2.101.0      2.106.0      winget\r\n"
    "Ubisoft Connect               Ubisoft.Connect        < 175.2.0.1  175.2.0.13   winget\r\n"
    "\r\n"
    "2 atualizações disponíveis.\r\n"
)


def test_the_apps_with_updates_are_read_with_their_current_and_latest_versions() -> None:
    assert parse_upgradable(TABLE) == [
        UpgradableApp("GitHub CLI", "GitHub.cli", "2.101.0", "2.106.0"),
        UpgradableApp("Ubisoft Connect", "Ubisoft.Connect", "< 175.2.0.1", "175.2.0.13"),
    ]


@pytest.mark.parametrize(
    "output", ["", "No installed package found matching input criteria.", "Nome  ID\r\n-----"]
)
def test_an_output_without_a_table_gives_no_apps(output: str) -> None:
    assert parse_upgradable(output) == []


@pytest.fixture(autouse=True)
def empty_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(winget_upgrades, "_cache", None)


def test_without_winget_the_list_is_unknown_and_not_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)

    assert list_upgradable() is None


def test_a_slow_winget_gives_an_unknown_list(monkeypatch: pytest.MonkeyPatch) -> None:
    def too_slow(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("winget", 1)

    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr("subprocess.run", too_slow)

    assert list_upgradable() is None


def test_the_list_is_reused_and_an_updated_app_leaves_it(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    class Result:
        stdout = TABLE.encode("utf-8")

    def fake_run(*_args: object, **_kwargs: object) -> Result:
        calls.append(1)
        return Result()

    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(winget_upgrades, "run_system_tool", lambda *_a, **_k: True)

    first = list_upgradable()
    assert first is not None
    update_apps(first[:1])(lambda _: None)
    second = list_upgradable()

    assert len(calls) == 1
    assert second is not None
    assert [app.package_id for app in second] == ["Ubisoft.Connect"]


def test_each_chosen_app_is_updated_by_its_id_and_the_failures_are_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[list[str]] = []

    def fake_tool(_exe: str, arguments: list[str], *_args: object, **_kwargs: object) -> bool:
        ran.append(arguments)
        return arguments[-1] != "Broken.App"

    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr(winget_upgrades, "run_system_tool", fake_tool)
    apps = [
        UpgradableApp("Fine", "Fine.App", "1", "2"),
        UpgradableApp("Broken", "Broken.App", "1", "2"),
    ]

    outcome = update_apps(apps)(lambda _: None)

    assert [arguments[-1] for arguments in ran] == ["Fine.App", "Broken.App"]
    assert outcome.items == 1
    assert outcome.failures == ("Broken",)


def test_updating_one_app_touches_only_that_app(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[str] = []

    def fake_tool(_exe: str, arguments: list[str], *_args: object, **_kwargs: object) -> bool:
        ran.append(arguments[-1])
        return True

    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr(winget_upgrades, "run_system_tool", fake_tool)
    apps = [UpgradableApp("A", "A.App", "1", "2"), UpgradableApp("B", "B.App", "1", "2")]

    update_apps(apps[:1])(lambda _: None)

    assert ran == ["A.App"]


def test_the_table_is_read_as_utf_8_so_accented_titles_keep_the_columns_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        stdout = TABLE.encode("utf-8")

    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr("subprocess.run", lambda *_a, **_k: Result())

    apps = list_upgradable()

    assert apps is not None
    assert [app.version for app in apps] == ["2.101.0", "< 175.2.0.1"]
