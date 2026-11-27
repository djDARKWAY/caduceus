from caduceus.keys import Key
from caduceus.menus import MAIN_MENU, MAINTENANCE_MENU
from caduceus.navigation import Navigation, press

SCAN, MAINTENANCE, _SETTINGS, EXIT = range(4)


def press_all(*keys: Key) -> Navigation:
    navigation = Navigation()
    for key in keys:
        navigation = press(navigation, key)
    return navigation


def test_down_on_the_last_option_goes_to_the_first() -> None:
    assert press_all(*[Key.DOWN] * len(MAIN_MENU.items)).index == 0


def test_up_on_the_first_option_goes_to_the_last() -> None:
    assert press_all(Key.UP).index == len(MAIN_MENU.items) - 1


def test_enter_on_manual_maintenance_opens_its_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER)
    assert navigation.menu is MAINTENANCE_MENU
    assert navigation.index == 0


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


def test_pc_cleanup_has_no_actions_yet_and_shows_the_notice() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.ENTER)
    assert navigation.menu is MAINTENANCE_MENU
    assert navigation.notice


def test_enter_on_exit_finishes() -> None:
    assert press_all(*[Key.DOWN] * EXIT, Key.ENTER).finished


def test_q_finishes_from_any_menu() -> None:
    navigation = press_all(*[Key.DOWN] * MAINTENANCE, Key.ENTER, Key.QUIT)
    assert navigation.finished


def test_other_keys_change_nothing() -> None:
    assert press_all(Key.OTHER) == Navigation()
