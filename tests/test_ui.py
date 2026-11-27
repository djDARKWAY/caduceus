import io
from dataclasses import replace

import pytest
from rich.console import Console

from caduceus.config import SELECTED_STYLE
from caduceus.controllers.menus import MAIN_MENU, MEMORY_MENU, MenuItem, startup_menu
from caduceus.controllers.navigation import Navigation
from caduceus.settings import Settings
from caduceus.ui import render
from caduceus.ui.i18n import load_texts
from caduceus.ui.render import format_estimate, format_size


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

    assert render.item_label(texts, item) == "Example app"
    assert render.item_label(texts, MenuItem("menu.exit")) == texts["menu.exit"]


@pytest.mark.parametrize(
    ("count", "index", "expected"),
    [(5, 4, range(0, 5)), (30, 0, range(0, 10)), (30, 15, range(10, 20)), (30, 29, range(20, 30))],
)
def test_the_list_scrolls_to_keep_the_selected_row_visible(
    count: int, index: int, expected: range
) -> None:
    assert render._visible_rows(count, index) == expected


def screen_lines(navigation: Navigation, height: int = 30) -> list[str]:
    console = Console(width=120, height=height, record=True, file=io.StringIO())
    console.print(render.render_screen(load_texts("en"), navigation))
    return console.export_text().splitlines()


def test_the_controls_stay_on_the_last_line_whatever_the_screen_shows() -> None:
    main_menu = Navigation()
    startup_list = Navigation(menus=(MAIN_MENU, startup_menu()), selected=(0, 0))
    scrolled = replace(startup_list, selected=(0, len(startup_list.menu.items) - 1))

    for navigation in (main_menu, startup_list, scrolled):
        lines = screen_lines(navigation)

        assert lines[-1].startswith("  ↑ Up")
        assert len(lines) == 30
