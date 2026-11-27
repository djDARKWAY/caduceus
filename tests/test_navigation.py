from dataclasses import replace

import pytest

from caduceus.controllers.keys import Key
from caduceus.controllers.menus import (
    CLEANUP_MENU,
    MAIN_MENU,
    MAINTENANCE_MENU,
    MEMORY_MENU,
    SAFE_MODE_MENU,
    SETTINGS_MENU,
    AdminNeed,
    Menu,
    MenuItem,
)
from caduceus.controllers.navigation import (
    Navigation,
    complete,
    finish_estimates,
    press,
)
from caduceus.maintenance.actions import Action, Outcome, Report
from caduceus.maintenance.free_space.recycle_bin import empty_recycle_bin
from caduceus.maintenance.free_space.temp_files import clean_temp_files
from caduceus.maintenance.free_space.windows_old import clean_windows_old
from caduceus.settings import Settings

SCAN, MAINTENANCE, _SETTINGS, EXIT = range(4)
WINDOWS_OLD_OPTION = next(
    index for index, item in enumerate(CLEANUP_MENU.items) if item.action is clean_windows_old
)
RECYCLE_BIN_OPTION = next(
    index for index, item in enumerate(CLEANUP_MENU.items) if item.action is empty_recycle_bin
)
HIBERNATION_OPTION = next(
    index for index, item in enumerate(MEMORY_MENU.items) if item.label_key == "memory.hibernation"
)
RISKY_OPTIONS = {index for index, item in enumerate(CLEANUP_MENU.items) if item.risky}


def press_all(*keys: Key, safe_mode: bool = False) -> Navigation:
    """Carrega as teclas, dando por calculadas as estimativas que o menu da limpeza pede."""
    navigation = Navigation(settings=Settings(safe_mode=safe_mode))
    for key in keys:
        navigation = press(navigation, key)
        if navigation.estimating:
            navigation = finish_estimates(navigation, {})
    return navigation


def open_temp_files_action() -> Navigation:
    return press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER, Key.ENTER)


def test_down_on_the_last_option_goes_to_the_first() -> None:
    selectable = [item for item in MAIN_MENU.items if not item.only_without_admin]

    assert press_all(*[Key.DOWN] * len(selectable)).index == 0


def test_up_on_the_first_option_goes_to_the_last() -> None:
    assert press_all(Key.UP).index == len(MAIN_MENU.items) - 1


def test_enter_on_manual_maintenance_opens_its_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER)
    assert navigation.menu is MAINTENANCE_MENU
    assert navigation.index == 0


def test_enter_on_free_up_space_opens_the_cleanup_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER)
    assert navigation.menu is CLEANUP_MENU


def test_backspace_returns_to_the_previous_menu_with_its_selection() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.BACK)
    assert navigation.menu is MAIN_MENU
    assert navigation.index == MAINTENANCE


def test_backspace_on_the_main_menu_changes_nothing() -> None:
    assert press_all(Key.BACK) == press_all()


def test_option_without_a_screen_shows_a_notice_that_only_backspace_closes() -> None:
    navigation = press_all(Key.ENTER)
    assert navigation.notice
    assert press(navigation, Key.BACK).notice is None
    for key in (Key.OTHER, Key.ENTER, Key.UP, Key.DOWN):
        assert press(navigation, key) == navigation
    assert press(navigation, Key.QUIT).finished
    assert press(navigation, Key.BACK).menu is MAIN_MENU


def test_enter_on_an_action_starts_it_straight_away() -> None:
    assert open_temp_files_action().running is clean_temp_files


def test_a_finished_action_shows_its_outcome_until_enter_is_pressed() -> None:
    outcome = Outcome(items=2, bytes_freed=100)

    navigation = complete(open_temp_files_action(), outcome)
    assert navigation.running is None
    assert navigation.outcome is outcome

    dismissed = press(navigation, Key.ENTER)
    assert dismissed.outcome is None
    assert dismissed.menu is CLEANUP_MENU


def test_enter_on_exit_finishes() -> None:
    assert press_all(*[Key.DOWN] * EXIT, Key.ENTER).finished


def test_quit_finishes_from_any_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.QUIT)
    assert navigation.finished


def test_other_keys_change_nothing() -> None:
    assert press_all(Key.OTHER) == press_all()


@pytest.mark.parametrize("key", [Key.UP, Key.DOWN, Key.BACK, Key.QUIT, Key.OTHER])
def test_only_enter_leaves_the_outcome_screen(key: Key) -> None:
    navigation = complete(open_temp_files_action(), Outcome(items=2, bytes_freed=100))

    assert press(navigation, key) == navigation


def open_windows_old_confirmation() -> Navigation:
    return press_all(
        *[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER, *[Key.DOWN] * WINDOWS_OLD_OPTION, Key.ENTER
    )


def test_an_action_with_a_warning_asks_for_confirmation_before_running() -> None:
    navigation = open_windows_old_confirmation()

    assert navigation.confirming
    assert navigation.running is None


def test_enter_confirms_and_runs_the_action() -> None:
    navigation = press(open_windows_old_confirmation(), Key.ENTER)

    assert not navigation.confirming
    assert navigation.running is clean_windows_old


def test_backspace_cancels_the_confirmation_without_running_anything() -> None:
    navigation = press(open_windows_old_confirmation(), Key.BACK)

    assert not navigation.confirming
    assert navigation.running is None
    assert navigation.menu is CLEANUP_MENU


@pytest.mark.parametrize("key", [Key.UP, Key.DOWN, Key.QUIT, Key.OTHER])
def test_only_enter_and_backspace_answer_the_confirmation(key: Key) -> None:
    navigation = open_windows_old_confirmation()

    assert press(navigation, key) == navigation


CLEANUP_PATH = (*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER)
SETTINGS_PATH = (*[Key.DOWN] * _SETTINGS, Key.ENTER)


def test_safe_mode_is_on_by_default() -> None:
    assert Navigation().settings.safe_mode


def test_with_safe_mode_on_the_cursor_skips_the_risky_options_in_both_directions() -> None:
    first = press_all(*CLEANUP_PATH, safe_mode=True)
    visited_down = [first.index]
    navigation = first
    for _ in range(len(CLEANUP_MENU.items)):
        navigation = press(navigation, Key.DOWN)
        visited_down.append(navigation.index)
    visited_up = [first.index]
    navigation = first
    for _ in range(len(CLEANUP_MENU.items)):
        navigation = press(navigation, Key.UP)
        visited_up.append(navigation.index)

    assert not RISKY_OPTIONS & set(visited_down + visited_up)
    assert len(set(visited_down)) == len(CLEANUP_MENU.items) - len(RISKY_OPTIONS)


def test_with_safe_mode_off_the_cursor_reaches_windows_old() -> None:
    navigation = press_all(*CLEANUP_PATH, *[Key.DOWN] * WINDOWS_OLD_OPTION)

    assert navigation.index == WINDOWS_OLD_OPTION


def test_a_blocked_option_does_nothing_even_if_the_state_points_at_it() -> None:
    at_windows_old = replace(
        press_all(*CLEANUP_PATH, safe_mode=True), selected=(1, 0, WINDOWS_OLD_OPTION)
    )

    assert press(at_windows_old, Key.ENTER) == at_windows_old


def test_safe_mode_does_not_block_the_harmless_actions() -> None:
    navigation = press_all(*CLEANUP_PATH, Key.ENTER, safe_mode=True)

    assert navigation.running is not None


def test_the_recycle_bin_runs_straight_away_even_with_safe_mode_on() -> None:
    # Com o Modo seguro ligado, o cursor salta as opÃ§Ãµes arriscadas que vÃªm antes
    moves = RECYCLE_BIN_OPTION - len([i for i in RISKY_OPTIONS if i < RECYCLE_BIN_OPTION])
    navigation = press_all(*CLEANUP_PATH, *[Key.DOWN] * moves, Key.ENTER, safe_mode=True)

    assert navigation.running is empty_recycle_bin
    assert not navigation.confirming


def test_the_recycle_bin_is_the_last_cleanup_so_it_also_empties_what_the_others_leave() -> None:
    actions = [item.action for item in CLEANUP_MENU.items if item.action is not None]

    assert actions[-1] is empty_recycle_bin


def test_with_safe_mode_off_windows_old_asks_for_confirmation() -> None:
    navigation = press_all(
        *CLEANUP_PATH, *[Key.DOWN] * WINDOWS_OLD_OPTION, Key.ENTER, safe_mode=False
    )

    assert navigation.confirming


def test_enter_on_the_safe_mode_setting_opens_the_on_and_off_options() -> None:
    opened = press_all(*SETTINGS_PATH, safe_mode=True)

    options = press(opened, Key.ENTER)

    assert options.menu is SAFE_MODE_MENU
    assert options.settings.safe_mode


def test_choosing_off_and_then_on_changes_safe_mode_and_returns_to_the_settings() -> None:
    options = press(press_all(*SETTINGS_PATH, safe_mode=True), Key.ENTER)

    off = press(press(options, Key.DOWN), Key.ENTER)
    on_again = press(press(off, Key.ENTER), Key.ENTER)  # o submenu abre no ON

    assert not off.settings.safe_mode
    assert off.menu is SETTINGS_MENU
    assert on_again.settings.safe_mode
    assert on_again.menu is SETTINGS_MENU


def test_opening_the_cleanup_menu_asks_for_the_estimates_and_ignores_keys_meanwhile() -> None:
    navigation = Navigation()
    for key in (*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER):
        navigation = press(navigation, key)

    assert navigation.estimating
    assert press(navigation, Key.BACK) == navigation

    estimated = finish_estimates(navigation, {"cleanup.caches": 5})
    assert not estimated.estimating
    assert estimated.estimates == {"cleanup.caches": 5}


def test_finishing_a_new_estimate_keeps_the_others() -> None:
    navigation = finish_estimates(press_all(*CLEANUP_PATH), {"cleanup.caches": 5, "cleanup.x": 7})

    updated = finish_estimates(navigation, {"cleanup.caches": 0})

    assert updated.estimates == {"cleanup.caches": 0, "cleanup.x": 7}


def test_after_an_action_only_its_own_estimate_is_calculated_again() -> None:
    finished = complete(open_temp_files_action(), Outcome(items=2, bytes_freed=100))

    assert press(finished, Key.ENTER).to_estimate == ("cleanup.temp_files",)


def open_run_all(safe_mode: bool) -> Navigation:
    return press_all(*CLEANUP_PATH, Key.UP, Key.ENTER, safe_mode=safe_mode)


@pytest.mark.parametrize("safe_mode", [True, False])
def test_running_all_cleanups_always_asks_for_confirmation(safe_mode: bool) -> None:
    navigation = open_run_all(safe_mode)

    assert navigation.confirming
    assert navigation.running is None


@pytest.mark.parametrize("safe_mode", [True, False])
def test_cancelling_the_confirmation_of_run_all_runs_nothing(safe_mode: bool) -> None:
    navigation = press(open_run_all(safe_mode), Key.BACK)

    assert not navigation.confirming
    assert navigation.running is None


def test_confirming_run_all_starts_one_combined_action() -> None:
    navigation = press(open_run_all(safe_mode=False), Key.ENTER)

    assert navigation.running is not None
    assert not navigation.confirming


def test_fast_run_all_skips_the_slow_cleanups() -> None:
    ran: list[str] = []

    def action_named(name: str) -> Action:
        def action(_report: Report) -> Outcome:
            ran.append(name)
            return Outcome(items=0, bytes_freed=0)

        return action

    menu = Menu(
        "test",
        (
            MenuItem("quick", action=action_named("quick")),
            MenuItem("slow", action=action_named("slow"), slow=True),
            MenuItem("fast", runs_all=True, skips_slow=True),
        ),
    )

    navigation = press(Navigation(menus=(menu,), selected=(2,)), Key.ENTER)
    assert navigation.running is not None
    navigation.running(lambda _: None)

    assert ran == ["quick"]


def test_after_run_all_every_estimate_is_calculated_again() -> None:
    finished = complete(open_run_all(safe_mode=False), Outcome(items=0, bytes_freed=0))

    assert len(press(finished, Key.ENTER).to_estimate) == sum(
        item.estimate is not None for item in CLEANUP_MENU.items
    )


def open_hibernation(safe_mode: bool = False, administrator: bool = True) -> Navigation:
    navigation = Navigation(
        menus=(MAIN_MENU, MEMORY_MENU),
        selected=(0, HIBERNATION_OPTION),
        settings=Settings(safe_mode=safe_mode),
        administrator=administrator,
    )
    assert navigation.item.label_key == "memory.hibernation"
    return press(navigation, Key.ENTER)


def test_hibernation_opens_a_submenu_with_off_and_on() -> None:
    navigation = open_hibernation()

    assert [item.label_key for item in navigation.menu.items] == [
        "memory.hibernation.off",
        "memory.hibernation.on",
    ]


def test_turning_hibernation_off_asks_for_confirmation() -> None:
    assert press(open_hibernation(), Key.ENTER).confirming


def test_turning_hibernation_on_runs_straight_away() -> None:
    navigation = press(press(open_hibernation(), Key.DOWN), Key.ENTER)

    assert navigation.running is not None
    assert not navigation.confirming


def test_safe_mode_blocks_hibernation_before_the_submenu() -> None:
    navigation = Navigation(
        menus=(MAIN_MENU, MEMORY_MENU),
        selected=(0, HIBERNATION_OPTION),
        settings=Settings(safe_mode=True),
    )

    assert press(navigation, Key.ENTER) == navigation


def blocked_by_admin_menu(administrator: bool) -> Navigation:
    def option(label: str, admin: AdminNeed | None) -> MenuItem:
        return MenuItem(label, label=label, action=lambda _report: Outcome(0, 0), admin=admin)

    items = (option("a", None), option("b", AdminNeed.ALL), option("c", AdminNeed.SOME))
    return Navigation(
        menus=(MAIN_MENU, Menu("memory.title", items)),
        selected=(0, 0),
        settings=Settings(safe_mode=False),
        administrator=administrator,
    )


def test_without_administrator_the_cursor_skips_what_needs_it_and_never_opens_a_result() -> None:
    navigation = blocked_by_admin_menu(administrator=False)

    visited = [navigation.index]
    for _ in range(3):
        navigation = press(navigation, Key.DOWN)
        visited.append(navigation.index)

    assert visited == [0, 2, 0, 2]
    assert press(replace(navigation, selected=(0, 1)), Key.ENTER).running is None


def test_with_administrator_everything_can_be_selected() -> None:
    navigation = blocked_by_admin_menu(administrator=True)

    assert press(navigation, Key.DOWN).index == 1


def instant_menu(outcome: Outcome) -> Navigation:
    item = MenuItem("startup:test", label="Example", action=lambda _report: outcome, instant=True)
    return Navigation(menus=(MAIN_MENU, Menu("startup.title", (item,))), selected=(0, 0))


def test_an_instant_action_that_works_goes_straight_back_to_the_list() -> None:
    running = press(instant_menu(Outcome(0, 0)), Key.ENTER)
    assert running.running is not None

    done = complete(running, Outcome(0, 0))

    assert done.running is None
    assert done.outcome is None


def test_an_instant_action_that_goes_wrong_shows_its_result() -> None:
    running = press(instant_menu(Outcome(0, 0)), Key.ENTER)

    done = complete(running, Outcome(0, 0, admin_required=("Example",)))

    assert done.outcome is not None


def test_a_menu_created_when_it_is_opened_is_loaded_on_every_entry() -> None:
    loaded: list[str] = []

    def loader() -> Menu:
        loaded.append("loaded")
        return Menu("startup.title", (MenuItem("startup.none"),))

    parent = Menu("memory.title", (MenuItem("memory.startup", submenu_loader=loader),))
    navigation = Navigation(menus=(MAIN_MENU, parent), selected=(0, 0))

    opened = press(navigation, Key.ENTER)
    reopened = press(press(opened, Key.BACK), Key.ENTER)

    assert opened.menu.title_key == "startup.title"
    assert reopened.menu.title_key == "startup.title"
    assert loaded == ["loaded", "loaded"]


def list_menu(*risky: bool) -> Navigation:
    def option(index: int, is_risky: bool) -> MenuItem:
        return MenuItem(
            f"startup:{index}",
            label=str(index),
            action=lambda _report: Outcome(0, 0),
            risky=is_risky,
        )

    items = tuple(option(index, is_risky) for index, is_risky in enumerate(risky))
    startup = MenuItem("memory.startup", submenu=Menu("startup.title", items))
    parent = Menu("memory.title", (startup,))
    settings = Settings(safe_mode=True)
    return Navigation(menus=(MAIN_MENU, parent), selected=(0, 0), settings=settings)


def test_with_safe_mode_on_the_cursor_skips_the_options_that_need_it_off() -> None:
    navigation = press(list_menu(False, True, True, False), Key.ENTER)

    visited = [navigation.index]
    for _ in range(4):
        navigation = press(navigation, Key.DOWN)
        visited.append(navigation.index)

    assert visited == [0, 3, 0, 3, 0]


def test_a_list_where_everything_needs_safe_mode_off_stays_closed_and_says_why() -> None:
    navigation = list_menu(True, True)

    opened = press(navigation, Key.ENTER)

    assert opened.menu == navigation.menu
    assert opened.notice == "notice.nothing_selectable"


def main_menu_at_restart(administrator: bool) -> Navigation:
    restart = next(i for i, item in enumerate(MAIN_MENU.items) if item.only_without_admin)
    return Navigation(selected=(restart,), administrator=administrator)


def test_restart_as_administrator_is_offered_only_without_administrator() -> None:
    without = press(main_menu_at_restart(administrator=False), Key.ENTER)
    with_admin = main_menu_at_restart(administrator=True)

    assert without.running is not None
    assert press(with_admin, Key.ENTER) == with_admin


def test_when_the_restart_goes_ahead_the_app_closes_without_a_result() -> None:
    running = press(main_menu_at_restart(administrator=False), Key.ENTER)

    done = complete(running, Outcome(0, 0, quit_after=True))

    assert done.finished
    assert done.closes_console
    assert done.outcome is None


def test_when_the_user_declines_the_windows_prompt_a_notice_is_shown() -> None:
    running = press(main_menu_at_restart(administrator=False), Key.ENTER)

    done = complete(running, Outcome(0, 0, notice="notice.restart_cancelled"))

    assert not done.finished
    assert done.notice == "notice.restart_cancelled"


def test_after_an_uninstall_the_list_is_created_again_without_the_program() -> None:
    installed = ["Alpha", "Beta", "Gamma"]

    def program(name: str) -> MenuItem:
        def uninstall(_report: Report) -> Outcome:
            installed.remove(name)
            return Outcome(1, 0)

        return MenuItem(f"program:{name}", label=name, action=uninstall, refreshes_menu=True)

    def loader() -> Menu:
        return Menu("programs.title", tuple(program(name) for name in installed))

    parent = Menu("apps.title", (MenuItem("apps.programs", submenu_loader=loader),))
    start = Navigation(menus=(MAIN_MENU, parent), selected=(0, 0))
    navigation = press(press(start, Key.ENTER), Key.DOWN)
    running = press(navigation, Key.ENTER)
    assert running.running is not None
    done = complete(running, running.running(lambda _step: None))

    back = press(done, Key.ENTER)

    assert [item.label for item in back.menu.items] == ["Alpha", "Gamma"]
    assert back.item.label == "Gamma"


def test_without_administrator_the_scheduled_tasks_cannot_even_be_opened() -> None:
    position = next(
        i for i, item in enumerate(MEMORY_MENU.items) if item.label_key == "memory.tasks"
    )
    navigation = Navigation(
        menus=(MAIN_MENU, MEMORY_MENU), selected=(0, position), administrator=False
    )

    assert press(navigation, Key.ENTER) == navigation
