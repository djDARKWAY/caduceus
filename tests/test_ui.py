import pytest

from caduceus.config import SELECTED_STYLE
from caduceus.controllers.menus import MEMORY_MENU
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
