from dataclasses import replace

from caduceus.controllers.keys import Key
from caduceus.controllers.menus import CLEANUP_MENU, MAIN_MENU, Menu, MenuItem
from caduceus.controllers.navigation import (
    Navigation,
    column_count,
    complete,
    display_order,
    loads_menu,
    press,
)
from caduceus.maintenance.actions import Outcome, Report

MAINTENANCE = 1
SIZE_COLUMNS = (("apps.uninstall.column.size", 9),)


def table(*rows: tuple[str, int | None]) -> Navigation:
    """Uma tabela com duas colunas, o nome e o tamanho (como a dos programas instalados)."""
    items = tuple(MenuItem(f"program:{name}", label=name, cells=(size,)) for name, size in rows)
    return Navigation(
        menus=(MAIN_MENU, Menu("apps.uninstall.title", items, SIZE_COLUMNS)), selected=(0, 0)
    )


def shown(navigation: Navigation) -> list[str | None]:
    return [navigation.menu.items[index].label for index in display_order(navigation)]


def test_key_2_sorts_the_size_column_up_then_down_with_the_unknown_sizes_last() -> None:
    navigation = table(("Beta", 300), ("Alpha", None), ("Gamma", 100), ("Delta", 200))

    up = press(navigation, Key.COLUMN_2)
    down = press(up, Key.COLUMN_2)
    up_again = press(down, Key.COLUMN_2)

    assert shown(up) == ["Gamma", "Delta", "Beta", "Alpha"]
    assert shown(down) == ["Beta", "Delta", "Gamma", "Alpha"]
    assert shown(up_again) == shown(up)


def test_key_1_sorts_the_names_alphabetically_ignoring_case_and_again_reverses_them() -> None:
    navigation = table(("beta", 1), ("Alpha", 2), ("gamma", 3))

    up = press(navigation, Key.COLUMN_1)
    down = press(up, Key.COLUMN_1)

    assert shown(up) == ["Alpha", "beta", "gamma"]
    assert shown(down) == ["gamma", "beta", "Alpha"]


def test_choosing_another_column_starts_in_ascending_order_again() -> None:
    navigation = table(("beta", 1), ("Alpha", 2))
    sized_down = press(press(navigation, Key.COLUMN_2), Key.COLUMN_2)

    named = press(sized_down, Key.COLUMN_1)

    assert shown(named) == ["Alpha", "beta"]


def test_a_column_key_that_the_table_does_not_have_does_nothing() -> None:
    navigation = table(("Alpha", 1))

    assert press(navigation, Key.COLUMN_3) == navigation


def test_the_column_keys_do_nothing_outside_the_tables() -> None:
    main_menu = Navigation()

    assert column_count(MAIN_MENU) == 0
    assert press(main_menu, Key.COLUMN_1) == main_menu


def test_the_cursor_goes_to_the_first_shown_row_and_then_follows_the_order_that_is_shown() -> None:
    at_gamma = press(table(("Beta", 300), ("Alpha", None), ("Gamma", 100)), Key.COLUMN_2)

    assert shown(at_gamma) == ["Gamma", "Beta", "Alpha"]
    assert at_gamma.item.label == "Gamma"
    assert press(at_gamma, Key.DOWN).item.label == "Beta"
    assert press(at_gamma, Key.UP).item.label == "Alpha"


def test_sorting_never_changes_the_order_of_the_menu_itself() -> None:
    navigation = table(("Beta", 300), ("Alpha", 100))

    sorted_up = press(navigation, Key.COLUMN_2)

    assert sorted_up.menu is navigation.menu


def test_the_state_column_sorts_off_before_on_and_the_text_columns_by_what_is_shown() -> None:
    def option(name: str, enabled: bool, trigger: str) -> MenuItem:
        return MenuItem(f"task:{name}", label=name, state=lambda: enabled, cells=(trigger,))

    items = (
        option("A", False, "performance.tasks.boot"),
        option("B", True, "performance.tasks.logon"),
    )
    menu = Menu("performance.tasks.title", items, (("performance.tasks.column.trigger", 7),))
    texts = {"performance.tasks.boot": "Startup", "performance.tasks.logon": "Logon"}
    navigation = Navigation(menus=(MAIN_MENU, menu), selected=(0, 0), texts=texts)

    assert column_count(menu) == 3
    assert shown(press(navigation, Key.COLUMN_2)) == ["A", "B"]
    assert shown(press(press(navigation, Key.COLUMN_2), Key.COLUMN_2)) == ["B", "A"]
    assert shown(press(navigation, Key.COLUMN_3)) == ["B", "A"]  # Logon vem antes de Startup


def test_run_all_stays_last_and_the_cleanups_keep_the_order_they_run_in() -> None:
    estimates = {item.label_key: index for index, item in enumerate(CLEANUP_MENU.items)}
    navigation = Navigation(
        menus=(MAIN_MENU, CLEANUP_MENU), selected=(MAINTENANCE, 0), estimates=estimates
    )

    sorted_down = press(press(navigation, Key.COLUMN_2), Key.COLUMN_2)

    run_all = [i for i, item in enumerate(CLEANUP_MENU.items) if item.runs_all]
    assert display_order(sorted_down)[-len(run_all) :] == run_all
    assert display_order(sorted_down)[0] != 0
    assert sorted_down.menu is CLEANUP_MENU


def test_leaving_the_table_forgets_the_sort() -> None:
    sorted_up = press(table(("Beta", 1), ("Alpha", 2)), Key.COLUMN_1)

    assert press(sorted_up, Key.BACK).sort is None


def test_after_an_uninstall_the_list_keeps_its_sort_and_the_cursor_its_place_in_it() -> None:
    installed: dict[str, int] = {"A": 300, "B": 100, "C": 200}

    def program(name: str, size: int) -> MenuItem:
        def uninstall(_report: Report) -> Outcome:
            del installed[name]
            return Outcome(1, 0)

        return MenuItem(
            f"program:{name}", label=name, action=uninstall, cells=(size,), refreshes_menu=True
        )

    def loader() -> Menu:
        items = tuple(program(name, size) for name, size in installed.items())
        return Menu("apps.uninstall.title", items, SIZE_COLUMNS)

    parent = Menu("maintenance.title", (MenuItem("apps.uninstall", submenu_loader=loader),))
    opened = press(Navigation(menus=(MAIN_MENU, parent), selected=(0, 0)), Key.ENTER)
    by_size = press(opened, Key.COLUMN_2)  # mostrado: B, C, A
    running = press(by_size, Key.ENTER)  # o cursor foi para B, a primeira mostrada
    assert running.running is not None
    done = complete(running, running.running(lambda _step: None))

    back = press(done, Key.ENTER)

    assert shown(back) == ["C", "A"]
    assert back.item.label == "C"


def test_sorting_moves_the_cursor_to_the_first_row_of_the_new_order() -> None:
    estimates = {
        item.label_key: index
        for index, item in enumerate(CLEANUP_MENU.items)
        if item.estimate is not None
    }
    navigation = Navigation(
        menus=(MAIN_MENU, CLEANUP_MENU), selected=(MAINTENANCE, 4), estimates=estimates
    )

    sorted_down = press(press(navigation, Key.COLUMN_2), Key.COLUMN_2)

    assert sorted_down.index == display_order(sorted_down)[0]


def test_the_update_all_option_stays_last_in_any_sort_and_runs_its_own_action() -> None:
    def update_all(_report: Report) -> Outcome:
        return Outcome(2, 0)

    def app(name: str, version: str) -> MenuItem:
        return MenuItem(f"update:{name}", label=name, action=update_all, cells=(version, "9"))

    items = (
        app("A", "3"),
        app("B", "1"),
        MenuItem("apps.update_all", action=update_all, runs_all=True),
    )
    menu = Menu("apps.update.title", items, (("c", 8), ("l", 8)))
    navigation = Navigation(menus=(MAIN_MENU, menu), selected=(0, 0))

    by_version = press(navigation, Key.COLUMN_2)

    assert [menu.items[i].label_key for i in display_order(by_version)][-1] == "apps.update_all"
    assert press(replace(navigation, selected=(0, 2)), Key.ENTER).running is update_all


def test_opening_or_reloading_a_list_is_announced_so_the_loading_can_be_shown() -> None:
    def loader() -> Menu:
        return Menu("programs.title", ())

    parent = Menu("maintenance.title", (MenuItem("apps.uninstall", submenu_loader=loader),))
    closed = Navigation(menus=(MAIN_MENU, parent), selected=(0, 0))

    assert loads_menu(closed, Key.ENTER)
    assert not loads_menu(closed, Key.DOWN)
    assert not loads_menu(Navigation(), Key.ENTER)  # o menu principal não cria listas
