import pytest

from caduceus.maintenance.apps import winget_upgrades
from caduceus.maintenance.apps.winget_upgrades import (
    UpgradableApp,
    parse_upgradable,
    update_all_apps,
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


def test_the_apps_with_updates_are_read_from_the_table_columns() -> None:
    assert parse_upgradable(TABLE) == [
        UpgradableApp("GitHub CLI", "GitHub.cli"),
        UpgradableApp("Ubisoft Connect", "Ubisoft.Connect"),
    ]


@pytest.mark.parametrize(
    "output", ["", "No installed package found matching input criteria.", "Nome  ID\r\n-----"]
)
def test_an_output_without_a_table_gives_no_apps(output: str) -> None:
    assert parse_upgradable(output) == []


def test_without_winget_nothing_runs_and_the_user_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)

    assert update_all_apps(lambda _: None).notice == "notice.winget_missing"


def test_with_nothing_to_update_the_user_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr(winget_upgrades, "list_upgradable", lambda _winget: [])

    assert update_all_apps(lambda _: None).notice == "notice.apps_up_to_date"


def test_each_app_is_updated_by_its_id_and_the_failures_are_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[list[str]] = []

    def fake_tool(_exe: str, arguments: list[str], *_args: object, **_kwargs: object) -> bool:
        ran.append(arguments)
        return arguments[-1] != "Broken.App"

    monkeypatch.setattr("shutil.which", lambda _name: "winget.exe")
    monkeypatch.setattr(
        winget_upgrades,
        "list_upgradable",
        lambda _winget: [UpgradableApp("Fine", "Fine.App"), UpgradableApp("Broken", "Broken.App")],
    )
    monkeypatch.setattr(winget_upgrades, "run_system_tool", fake_tool)

    outcome = update_all_apps(lambda _: None)

    assert [arguments[-1] for arguments in ran] == ["Fine.App", "Broken.App"]
    assert outcome.items == 1
    assert outcome.failures == ("Broken",)
