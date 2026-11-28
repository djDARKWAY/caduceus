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
from caduceus.maintenance.actions import Action, Outcome, Report
from caduceus.maintenance.apps.installed_programs import InstalledProgram
from caduceus.maintenance.apps.store_apps import StoreApp
from caduceus.settings import Settings

PROGRAMS_OPTION = 2  # a posição de «Programs» na Manutenção manual
POSSIBILITIES = ("programs.repair", "programs.reset", "programs.uninstall")
TODO = StoreApp("Maker.Todo", "Maker.Todo_1.0_x64__abc", "1.0")


def installed(name: str, size: int | None = None) -> InstalledProgram:
    return InstalledProgram(
        name, "Maker", "1.0", "", size, r"C:\Apps\un.exe", winreg.HKEY_CURRENT_USER, f"k\\{name}"
    )


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Fixa o que o registo e a Store dizem, sem tocar no que a máquina tem."""

    def set_sources(
        programs: list[InstalledProgram] | None = None, store: list[StoreApp] | None = None
    ) -> None:
        monkeypatch.setattr(tables, "list_installed_programs", lambda: programs or [])
        monkeypatch.setattr(tables, "list_store_apps", lambda: store or [])

    return set_sources


def row(menu: Menu, label: str) -> MenuItem:
    return next(item for item in menu.items if item.label == label)


def options(item: MenuItem) -> dict[str, MenuItem]:
    assert item.submenu is not None
    return {option.label_key: option for option in item.submenu.items}


def open_table(settings: Settings | None = None) -> Navigation:
    maintenance = Navigation(menus=(MAIN_MENU, MAINTENANCE_MENU), selected=(1, PROGRAMS_OPTION))
    return replace(press(maintenance, Key.ENTER), settings=settings or Settings(safe_mode=False))


def test_programs_and_store_apps_share_one_table_by_name_with_their_version_and_size(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Zeta", 2048), installed("Alpha")], store=[TODO])

    menu = programs_menu()

    assert [item.label for item in menu.items] == ["Alpha", "Maker.Todo", "Zeta"]
    assert row(menu, "Zeta").cells == ("1.0", 2048)
    assert row(menu, "Maker.Todo").cells == ("1.0", None)


def test_each_row_offers_the_three_possibilities_but_only_those_that_apply(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Plain")], store=[TODO])
    menu = programs_menu()

    program = options(row(menu, "Plain"))
    store = options(row(menu, "Maker.Todo"))

    assert tuple(program) == tuple(store) == POSSIBILITIES
    assert [key for key, option in program.items() if not option.unavailable] == [
        "programs.uninstall"
    ]
    assert [key for key, option in store.items() if not option.unavailable] == [
        "programs.repair",
        "programs.reset",
    ]


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
    sources(programs=[installed("Plain")], store=[TODO])

    asking = [
        key
        for item in programs_menu().items
        if item.submenu is not None
        for key, option in options(item).items()
        if option.confirm_key is not None
    ]
    assert asking == ["programs.reset"]

    todo = press(open_table(Settings(safe_mode=True)), Key.ENTER)  # a primeira linha: a Store app
    assert todo.item.label_key == "programs.repair"
    assert press(todo, Key.DOWN).item.label_key == "programs.repair"


def test_a_program_that_only_safe_mode_off_can_uninstall_opens_a_notice_instead(
    sources: Callable[..., None],
) -> None:
    sources(programs=[installed("Some Runtime")])

    opened = press(open_table(Settings(safe_mode=True)), Key.ENTER)

    assert opened.notice == NOTHING_SELECTABLE_NOTICE


def test_after_an_uninstall_from_a_program_the_table_is_created_again_and_keeps_its_sort(
    sources: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    programs = [installed("Alpha", 30), installed("Beta", 20), installed("Gamma", 10)]
    sources(programs=programs)

    def fake_uninstall(program: InstalledProgram) -> Action:
        def uninstall(_report: Report) -> Outcome:
            programs.remove(program)
            return Outcome(1, 0)

        return uninstall

    monkeypatch.setattr(tables, "uninstall_program", fake_uninstall)
    by_size = press(open_table(), Key.COLUMN_3)  # do menor para o maior: Gamma, Beta, Alpha
    on_beta = press(by_size, Key.DOWN)
    assert on_beta.item.label == "Beta"

    running = press(press(on_beta, Key.ENTER), Key.ENTER)
    assert running.running is not None
    done = complete(running, running.running(lambda _: None))
    back = press(done, Key.ENTER)

    assert back.menu.title_key == "programs.title" and back.menu.title is None
    assert [item.label for item in back.menu.items] == ["Alpha", "Gamma"]
    assert back.sort == by_size.sort
    assert back.item.label == "Alpha"  # o cursor fica na mesma posição da lista mostrada
    assert press(back, Key.BACK).sort is None
