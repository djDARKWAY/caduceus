import pytest

from caduceus.controllers.keys import Key
from caduceus.controllers.menus import CLEANUP_MENU, MAIN_MENU, MAINTENANCE_MENU
from caduceus.controllers.navigation import Navigation, complete, press
from caduceus.maintenance.actions import Outcome
from caduceus.maintenance.recycle_bin import empty_recycle_bin

SCAN, MAINTENANCE, _SETTINGS, EXIT = range(4)


def press_all(*keys: Key) -> Navigation:
    navigation = Navigation()
    for key in keys:
        navigation = press(navigation, key)
    return navigation


def open_recycle_bin_action() -> Navigation:
    return press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER, Key.DOWN, Key.ENTER)


def test_down_on_the_last_option_goes_to_the_first() -> None:
    assert press_all(*[Key.DOWN] * len(MAIN_MENU.items)).index == 0


def test_up_on_the_first_option_goes_to_the_last() -> None:
    assert press_all(Key.UP).index == len(MAIN_MENU.items) - 1


def test_enter_on_manual_maintenance_opens_its_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER)
    assert navigation.menu is MAINTENANCE_MENU
    assert navigation.index == 0


def test_enter_on_pc_cleanup_opens_the_cleanup_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER)
    assert navigation.menu is CLEANUP_MENU


def test_backspace_returns_to_the_previous_menu_with_its_selection() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.BACK)
    assert navigation.menu is MAIN_MENU
    assert navigation.index == MAINTENANCE


def test_backspace_on_the_main_menu_changes_nothing() -> None:
    assert press_all(Key.BACK) == Navigation()


def test_option_without_a_screen_shows_a_notice_that_any_key_closes() -> None:
    navigation = press_all(Key.ENTER)
    assert navigation.notice
    assert not press(navigation, Key.OTHER).notice
    assert press(navigation, Key.OTHER).menu is MAIN_MENU


def test_enter_on_an_action_starts_it_straight_away() -> None:
    assert open_recycle_bin_action().running is empty_recycle_bin


def test_a_finished_action_shows_its_outcome_until_enter_is_pressed() -> None:
    outcome = Outcome(items=2, bytes_freed=100)

    navigation = complete(open_recycle_bin_action(), outcome)
    assert navigation.running is None
    assert navigation.outcome is outcome

    dismissed = press(navigation, Key.ENTER)
    assert dismissed.outcome is None
    assert dismissed.menu is CLEANUP_MENU


def test_enter_on_exit_finishes() -> None:
    assert press_all(*[Key.DOWN] * EXIT, Key.ENTER).finished


def test_q_finishes_from_any_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.QUIT)
    assert navigation.finished


def test_other_keys_change_nothing() -> None:
    assert press_all(Key.OTHER) == Navigation()


@pytest.mark.parametrize("key", [Key.UP, Key.DOWN, Key.BACK, Key.QUIT, Key.OTHER])
def test_only_enter_leaves_the_outcome_screen(key: Key) -> None:
    navigation = complete(open_recycle_bin_action(), Outcome(items=2, bytes_freed=100))

    assert press(navigation, key) == navigation
