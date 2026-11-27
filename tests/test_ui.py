import pytest

from caduceus.ui.render import format_size


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
