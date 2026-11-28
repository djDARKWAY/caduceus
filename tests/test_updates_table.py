from collections.abc import Callable

import pytest

from caduceus.controllers import tables
from caduceus.controllers.keys import Key
from caduceus.controllers.menus import MAIN_MENU, MAINTENANCE_MENU
from caduceus.controllers.navigation import Navigation, complete, press
from caduceus.controllers.tables import updates_menu
from caduceus.maintenance.actions import Outcome
from caduceus.maintenance.apps.winget_upgrades import UpgradableApp

UPDATES_OPTION = 3  # a posição de «Updates» na Manutenção manual


@pytest.fixture
def winget(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[UpgradableApp] | None], None]:
    """Fixa o que o winget diz (None é «não respondeu»), sem lhe tocar."""

    def say(upgrades: list[UpgradableApp] | None) -> None:
        monkeypatch.setattr(tables, "list_upgradable", lambda: upgrades)

    return say


def app(name: str, available: str = "2.0") -> UpgradableApp:
    return UpgradableApp(name, f"Maker.{name}", "1.0", available)


def test_every_app_with_a_newer_version_is_listed_with_the_current_and_the_latest(
    winget: Callable[[list[UpgradableApp] | None], None],
) -> None:
    winget([app("Beta", "3.0"), app("Alpha")])

    items = updates_menu().items

    assert [item.label for item in items if not item.runs_all] == ["Beta", "Alpha"]
    assert items[0].cells == ("1.0", "3.0")


def test_update_all_closes_the_table_and_runs_without_asking(
    winget: Callable[[list[UpgradableApp] | None], None],
) -> None:
    winget([app("Alpha")])

    last = updates_menu().items[-1]

    assert last.runs_all and last.label_key == "updates.update_all"
    assert last.action is not None and last.confirm_key is None


@pytest.mark.parametrize(("listed", "expected"), [([], "updates.none"), (None, "updates.failed")])
def test_without_updates_or_without_winget_the_table_says_which_it_is(
    winget: Callable[[list[UpgradableApp] | None], None],
    listed: list[UpgradableApp] | None,
    expected: str,
) -> None:
    winget(listed)

    assert [item.label_key for item in updates_menu().items] == [expected]


def test_after_updating_an_app_the_table_is_created_again_without_it(
    winget: Callable[[list[UpgradableApp] | None], None],
) -> None:
    pending = [app("Alpha"), app("Beta")]
    winget(pending)
    maintenance = Navigation(menus=(MAIN_MENU, MAINTENANCE_MENU), selected=(1, UPDATES_OPTION))
    on_alpha = press(maintenance, Key.ENTER)
    assert on_alpha.menu.title_key == "updates.title" and on_alpha.item.label == "Alpha"

    running = press(on_alpha, Key.ENTER)
    assert running.running is not None
    pending.pop(0)
    back = press(complete(running, Outcome(1, 0)), Key.ENTER)

    assert [item.label for item in back.menu.items if not item.runs_all] == ["Beta"]
    assert back.item.label == "Beta"
