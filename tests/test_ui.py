import io
import winreg
from dataclasses import replace

import pytest
from rich.console import Console

from caduceus.config import SELECTED_STYLE, WINDOW_LINES
from caduceus.controllers import tables
from caduceus.controllers.keys import Key
from caduceus.controllers.menu_model import Menu, MenuItem, item_label
from caduceus.controllers.menus import CLEANUP_MENU, MAIN_MENU, PERFORMANCE_MENU, SETTINGS_MENU
from caduceus.controllers.navigation import Navigation, press
from caduceus.controllers.tables import programs_menu, startup_menu
from caduceus.maintenance.apps.installed_programs import InstalledProgram
from caduceus.maintenance.apps.winget_upgrades import UpgradableApp
from caduceus.maintenance.performance import power_plan
from caduceus.maintenance.performance.optimize_drives import Drive
from caduceus.maintenance.performance.startup_programs import StartupEntry, StartupSource
from caduceus.settings import Settings
from caduceus.ui import render
from caduceus.ui.i18n import load_texts
from caduceus.ui.palette import ACCENT
from caduceus.ui.render import format_estimate, format_size


@pytest.fixture(autouse=True)
def fictitious_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """As listas dos menus são fictícias, para os testes não dependerem do que a máquina tem."""
    startup = [
        StartupEntry(f"app{n}", f"App {n:02}", rf"C:\Apps\app{n}.exe", StartupSource.RUN_USER, None)
        for n in range(25)
    ]
    programs = [
        InstalledProgram(
            f"Program {n:02}",
            "Maker",
            "1.0",
            "",
            (n + 1) * 1024,
            rf"C:\Apps\un{n}.exe",
            winreg.HKEY_CURRENT_USER,
            f"Software\\CaduceusTests\\program{n}",
        )
        for n in range(25)
    ]
    upgrades = [UpgradableApp("Program 03", "Maker.Program03", "1.0", "2.0")]
    monkeypatch.setattr(tables, "list_startup_entries", lambda: startup)
    monkeypatch.setattr(tables, "list_installed_programs", lambda: programs)
    monkeypatch.setattr(tables, "list_store_apps", list)
    monkeypatch.setattr(tables, "list_upgradable", lambda: upgrades)


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1536, "1.5 KB"),
        (5 * 1024**2, "5.0 MB"),
        (2 * 1024**3, "2.0 GB"),
        (3 * 1024**4, "3.0 TB"),
    ],
)
def test_sizes_are_shown_in_the_largest_fitting_unit(size: int, expected: str) -> None:
    assert format_size(size) == expected


@pytest.mark.parametrize(
    ("estimate", "expected"),
    [(None, "—"), (0, "0 B"), (1536, "~1.5 KB"), (2 * 1024**3, "~2.0 GB")],
)
def test_the_estimated_gain_is_shown_as_approximate_or_unknown(
    estimate: int | None, expected: str
) -> None:
    assert format_estimate(estimate) == expected


def test_an_option_blocked_by_safe_mode_is_shown_dimmed_even_when_selected() -> None:
    texts = load_texts("en")
    item = PERFORMANCE_MENU.items[0]

    assert render._render_option(texts, item, True, Settings(), blocked=True).style == "dim"
    assert render._render_option(texts, item, True, Settings()).style == SELECTED_STYLE


def test_an_option_created_at_runtime_shows_its_own_name() -> None:
    texts = load_texts("en")
    item = MenuItem("startup:run_user:Example", label="Example app")

    assert item_label(texts, item) == "Example app"
    assert item_label(texts, MenuItem("menu.exit")) == texts["menu.exit"]


@pytest.mark.parametrize(
    ("count", "index", "expected"),
    [(5, 4, range(0, 5)), (30, 0, range(0, 10)), (30, 15, range(10, 20)), (30, 29, range(20, 30))],
)
def test_the_list_scrolls_to_keep_the_selected_row_visible(
    count: int, index: int, expected: range
) -> None:
    assert render._visible_rows(count, index) == expected


def screen_lines(navigation: Navigation, height: int = WINDOW_LINES) -> list[str]:
    console = Console(width=120, height=height, record=True, file=io.StringIO())
    console.print(render.render_screen(load_texts("en"), navigation))
    return console.export_text().splitlines()


def test_the_power_plan_option_shows_the_current_plan_beside_its_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(power_plan, "_active_scheme", lambda: power_plan._BALANCED)
    index = next(
        i
        for i, item in enumerate(PERFORMANCE_MENU.items)
        if item.label_key == "performance.power_plan"
    )
    navigation = Navigation(menus=(PERFORMANCE_MENU,), selected=(index,))

    line = next(line for line in screen_lines(navigation) if "Power plan" in line)
    assert line.lstrip().startswith("Power plan BALANCED")

    submenu = screen_lines(press(navigation, Key.ENTER))
    assert any("BALANCED ON" in line for line in submenu)
    assert any("HIGH OFF" in line for line in submenu)

    monkeypatch.setattr(power_plan, "_active_scheme", lambda: power_plan._HIGH)
    line = next(line for line in screen_lines(navigation) if "Power plan" in line)
    assert line.lstrip().startswith("Power plan HIGH")


@pytest.mark.parametrize("selected", [0, 12, 24])
def test_the_run_all_options_stay_visible_while_only_the_table_scrolls(selected: int) -> None:
    programs = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, selected))
    cleanup = Navigation(menus=(MAIN_MENU, CLEANUP_MENU), selected=(0, selected % 5))

    for navigation, pinned in (
        (programs, ["► UPDATE ALL"]),
        (cleanup, ["» FAST CLEANUPS", "► ALL CLEANUPS"]),
    ):
        lines = screen_lines(navigation)

        assert len(lines) == WINDOW_LINES
        for text in pinned:
            assert any(text in line for line in lines)


def test_the_pinned_options_come_after_the_last_row_of_the_table_and_the_cursor_reaches_them() -> (
    None
):
    programs = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, 24))
    last_row = press(programs, Key.DOWN)

    assert last_row.item.runs_all
    lines = screen_lines(last_row)
    assert any("Program 24" in line for line in lines)  # a tabela mostra o seu fim
    assert not any("Program 00" in line for line in lines)


def test_the_run_all_options_share_the_same_style_and_name_case() -> None:
    texts = load_texts("en")

    assert render._pinned_style(False) == f"bold {ACCENT}"
    for key in ("cleanup.fast", "cleanup.all", "programs.update_all"):
        assert texts[key] == texts[key].upper()


def test_the_drive_table_shows_media_type_size_and_free_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drive = Drive("C", "Windows", "drive0", "SSD", 2 * 1024**3, 1024**3)
    monkeypatch.setattr(tables, "list_drives", lambda: [drive])
    navigation = Navigation(menus=(tables.drives_menu(),))

    lines = screen_lines(navigation)

    assert any(
        all(heading in line for heading in ("Drive", "Type", "Size", "Free")) for line in lines
    )
    row = next(line for line in lines if "C: Windows" in line and "2.0 GB" in line)
    assert "SSD" in row and "1.0 GB" in row and "~" not in row


def test_restart_as_administrator_is_shown_only_without_administrator() -> None:
    def settings(administrator: bool) -> str:
        navigation = Navigation(
            menus=(MAIN_MENU, SETTINGS_MENU), selected=(2, 0), administrator=administrator
        )
        return "\n".join(screen_lines(navigation))

    without = settings(administrator=False)
    with_admin = settings(administrator=True)

    assert "Restart as administrator" in without
    assert "Restart as administrator" not in with_admin


def test_a_text_cell_without_a_translation_is_shown_as_it_is() -> None:
    items = (MenuItem("store.item", label="Some App", cells=("0.20.65.0",)),)
    table = Menu("programs.title", items, (("programs.column.version", 14),))

    lines = screen_lines(Navigation(menus=(MAIN_MENU, table), selected=(0, 0)))

    assert any("Some App" in line and "0.20.65.0" in line for line in lines)


def test_the_sort_key_appears_in_the_controls_of_the_tables_only() -> None:
    programs = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, 0))

    assert "1-4 Sort" in screen_lines(programs)[-2]
    assert "Sort" not in screen_lines(Navigation())[-2]


def test_the_sorted_column_shows_the_direction_in_its_title() -> None:
    programs = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, 0))
    by_size = press(press(programs, Key.COLUMN_4), Key.COLUMN_4)

    assert any("Size ▼" in line for line in screen_lines(by_size))
    assert not any("▲" in line or "▼" in line for line in screen_lines(programs))


def test_the_controls_stay_above_a_free_last_line_whatever_the_screen_shows() -> None:
    main_menu = Navigation()
    startup_list = Navigation(menus=(MAIN_MENU, startup_menu()), selected=(0, 0))
    scrolled = replace(startup_list, selected=(0, len(startup_list.menu.items) - 1))
    programs_list = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, 0))

    for navigation in (main_menu, startup_list, scrolled, programs_list):
        lines = screen_lines(navigation)

        assert lines[-2].startswith("  ↑ Up")
        assert not lines[-1].strip()
        assert len(lines) == WINDOW_LINES
