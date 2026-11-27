import io
import winreg
from dataclasses import replace

import pytest
from rich.console import Console

from caduceus.config import SELECTED_STYLE, WINDOW_LINES
from caduceus.controllers import menus
from caduceus.controllers.keys import Key
from caduceus.controllers.menus import (
    MAIN_MENU,
    MEMORY_MENU,
    SETTINGS_MENU,
    MenuItem,
    item_label,
    programs_menu,
    startup_menu,
)
from caduceus.controllers.navigation import Navigation, press
from caduceus.maintenance.apps.installed_programs import InstalledProgram
from caduceus.maintenance.memory.startup_programs import StartupEntry, StartupSource
from caduceus.settings import Settings
from caduceus.ui import render
from caduceus.ui.i18n import load_texts
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
        for n in range(12)
    ]
    monkeypatch.setattr(menus, "list_startup_entries", lambda: startup)
    monkeypatch.setattr(menus, "list_installed_programs", lambda: programs)


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
    item = MEMORY_MENU.items[0]

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


def test_the_sort_key_appears_in_the_controls_of_the_tables_only() -> None:
    programs = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, 0))

    assert "1-2 Sort" in screen_lines(programs)[-2]
    assert "Sort" not in screen_lines(Navigation())[-2]


def test_the_sorted_column_shows_the_direction_in_its_title() -> None:
    programs = Navigation(menus=(MAIN_MENU, programs_menu()), selected=(0, 0))
    by_size = press(press(programs, Key.COLUMN_2), Key.COLUMN_2)

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
