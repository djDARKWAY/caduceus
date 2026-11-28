import winreg
from collections.abc import Callable
from dataclasses import replace

import pytest

from caduceus.controllers import tables
from caduceus.controllers.keys import Key
from caduceus.controllers.menu_model import Menu, MenuItem
from caduceus.controllers.menus import MAIN_MENU, MAINTENANCE_MENU
from caduceus.controllers.navigation import (
    NOTHING_SELECTABLE_NOTICE,
    Navigation,
    complete,
    press,
)
from caduceus.controllers.tables import programs_menu
from caduceus.maintenance.actions import Outcome
from caduceus.maintenance.apps.installed_programs import InstalledProgram
from caduceus.maintenance.apps.store_apps import StoreApp
from caduceus.maintenance.apps.winget_upgrades import UpgradableApp
from caduceus.settings import Settings

PROGRAM_LABELS = ("programs.update", "programs.repair", "programs.reset", "programs.uninstall")


def installed(name: str, size: int | None = None) -> InstalledProgram:
    return InstalledProgram(
        name, "Maker", "1.0", "", size, r"C:\Apps\un.exe", winreg.HKEY_CURRENT_USER, f"k\\{name}"
    )


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Fixa o que o registo, a Store e o winget dizem, sem tocar no que a máquina tem."""

    def set_sources(
        programs: list[InstalledProgram] | None = None,
        store: list[StoreApp] | None = None,
        upgrades: list[UpgradableApp] | None = None,
    ) -> None:
        monkeypatch.setattr(tables, "list_installed_programs", lambda: programs or [])
        monkeypatch.setattr(tables, "list_store_apps", lambda: store or [])
        monkeypatch.setattr(tables, "list_upgradable", lambda: upgrades)

    return set_sources


def row(menu: Menu, label: str) -> MenuItem:
    return next(item for item in menu.items if item.label == label)


def options(item: MenuItem) -> dict[str, MenuItem]:
    assert item.submenu is not None
    return {option.label_key: option for option in item.submenu.items}


def open_table(settings: Settings | None = None) -> Navigation:
    maintenance = Navigation(menus=(MAIN_MENU, MAINTENANCE_MENU), selected=(1, 2))
    return replace(press(maintenance, Key.ENTER), settings=settings or Settings(safe_mode=False))


def test_every_program_offers_the_four_possibilities_but_only_those_that_apply(
    sources: Callable[..., None],
) -> None:
    store = StoreApp("Maker.Todo", "Maker.Todo_1.0_x64__abc", "1.0")
    sources(
        programs=[installed("Plain"), installed("Updatable")],
        store=[store],
        upgrades=[UpgradableApp("Updatable", "Maker.Updatable", "1.0", "2.0")],
    )
    menu = programs_menu()

    plain = options(row(menu, "Plain"))
    updatable = options(row(menu, "Updatable"))
    todo = options(row(menu, "Maker.Todo"))

    assert tuple(plain) == PROGRAM_LABELS
    assert {key: option.unavailable for key, option in plain.items()} == {
        "programs.update": True,
        "programs.repair": True,
        "programs.reset": True,
        "programs.uninstall": False,
    }
    assert not updatable["programs.update"].unavailable
    assert not updatable["programs.uninstall"].unavailable
    assert [key for key, option in todo.items() if not option.unavailable] == [
        "programs.repair",
        "programs.reset",
    ]


def test_an_update_matches_the_program_by_name_and_the_store_app_by_id(
    sources: Callable[..., None],
) -> None:
    sources(
        programs=[installed("Editor")],
        store=[StoreApp("Maker.Todo", "Maker.Todo_1.0_x64__abc", "1.0")],
        upgrades=[
            UpgradableApp("EDITOR", "Maker.Editor", "1.0", "1.5"),
            UpgradableApp("To Do", "maker.todo", "1.0", "1.1"),
        ],
    )
    menu = programs_menu()

    assert [item.label for item in menu.items if item.label] == ["Editor", "Maker.Todo"]
    assert row(menu, "Editor").cells[1] == "1.5"
    assert row(menu, "Maker.Todo").cells[1] == "1.1"


def test_an_update_that_matches_nothing_is_still_listed_on_a_row_of_its_own(
    sources: Callable[..., None],
) -> None:
    sources(upgrades=[UpgradableApp("Odd One", "Odd.One", "1", "2")])

    only = row(programs_menu(), "Odd One")

    assert [key for key, option in options(only).items() if not option.unavailable] == [
        "programs.update"
    ]


def test_update_all_closes_the_table_and_only_exists_when_there_is_something_to_update(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Plain")])
    assert not any(item.runs_all for item in programs_menu().items)

    sources(programs=[installed("Plain")], upgrades=[UpgradableApp("Odd One", "Odd.One", "1", "2")])
    last = programs_menu().items[-1]
    assert last.runs_all and last.label_key == "programs.update_all"
    assert last.action is not None and last.confirm_key is None


def test_winget_not_answering_still_lists_the_programs_without_updates(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Plain")], upgrades=None)

    menu = programs_menu()

    assert [item.label for item in menu.items] == ["Plain"]
    assert row(menu, "Plain").cells[1] is None


def test_no_programs_at_all_shows_an_empty_table_that_says_so(
    sources: Callable[..., None],
) -> None:
    sources()

    assert [item.label_key for item in programs_menu().items] == ["programs.none"]


def test_choosing_a_program_opens_its_possibilities_and_the_cursor_skips_the_dimmed_ones(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Plain")])

    submenu = press(open_table(), Key.ENTER)

    assert submenu.menu.title == "Plain"
    assert submenu.item.label_key == "programs.uninstall"
    assert press(submenu, Key.DOWN).item.label_key == "programs.uninstall"
    assert press(press(submenu, Key.ENTER), Key.ENTER).running is not None


def test_only_reset_asks_for_confirmation_and_safe_mode_blocks_it(
    sources: Callable[..., None],
) -> None:
    sources(
        programs=[installed("Plain")],
        store=[StoreApp("Maker.Todo", "Maker.Todo_1.0_x64__abc", "1.0")],
        upgrades=[UpgradableApp("Plain", "Maker.Plain", "1.0", "2.0")],
    )
    menu = programs_menu()

    asking = [
        key
        for item in menu.items
        if item.submenu is not None
        for key, option in options(item).items()
        if option.confirm_key is not None
    ]
    assert asking == ["programs.reset"]

    safe = open_table(Settings(safe_mode=True))
    todo = press(safe, Key.ENTER)  # a Store app (a primeira linha), com o Modo seguro ligado
    assert todo.item.label_key == "programs.repair"
    assert press(todo, Key.DOWN).item.label_key == "programs.repair"


def test_a_program_that_only_safe_mode_off_can_uninstall_opens_a_notice_instead(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Some Runtime")])

    opened = press(open_table(Settings(safe_mode=True)), Key.ENTER)

    assert opened.notice == NOTHING_SELECTABLE_NOTICE


def test_after_an_update_from_a_program_the_table_is_created_again_and_keeps_its_sort(
    sources: Callable[..., None],
) -> None:
    pending = [UpgradableApp("Beta", "Maker.Beta", "1.0", "2.0")]
    programs = [installed("Alpha", 30), installed("Beta", 20), installed("Gamma", 10)]
    sources(programs=programs, upgrades=pending)
    by_size = press(open_table(), Key.COLUMN_4)  # do menor para o maior: Gamma, Beta, Alpha
    on_beta = press(by_size, Key.DOWN)
    assert on_beta.item.label == "Beta"

    inside = press(on_beta, Key.ENTER)
    running = press(inside, Key.ENTER)
    assert running.running is not None and inside.item.label_key == "programs.update"
    pending.clear()
    done = complete(running, Outcome(1, 0))
    back = press(done, Key.ENTER)

    assert back.menu.title_key == "programs.title" and back.menu.title is None
    assert back.sort == by_size.sort
    assert back.item.label == "Beta"
    assert row(back.menu, "Beta").cells[1] is None  # já não tem versão nova à espera
    assert not any(item.runs_all for item in back.menu.items)
    assert press(back, Key.BACK).sort is None
