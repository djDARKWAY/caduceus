import pytest

from caduceus.maintenance import recycle_bin
from caduceus.maintenance.actions import Step


@pytest.fixture
def emptied(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    drives = {"C:\\": (3, 3000), "D:\\": (0, 0), "E:\\": (2, 500)}
    emptied: list[str] = []
    monkeypatch.setattr(recycle_bin, "_fixed_drives", lambda: list(drives))
    monkeypatch.setattr(recycle_bin, "_query", lambda drive: drives[drive])
    monkeypatch.setattr(recycle_bin, "_empty", emptied.append)
    return emptied


@pytest.mark.usefixtures("emptied")
def test_totals_add_up_across_drives() -> None:
    outcome = recycle_bin.empty_recycle_bin(lambda _: None)

    assert (outcome.items, outcome.bytes_freed, outcome.failures) == (5, 3500, ())


def test_a_bin_that_is_already_empty_is_left_alone(emptied: list[str]) -> None:
    recycle_bin.empty_recycle_bin(lambda _: None)

    assert emptied == ["C:\\", "E:\\"]


@pytest.mark.usefixtures("emptied")
def test_progress_reports_each_drive_before_emptying_it() -> None:
    steps: list[Step] = []

    recycle_bin.empty_recycle_bin(steps.append)

    assert [(step.done, step.total, step.values["drive"]) for step in steps] == [
        (0, 3, "C:\\"),
        (1, 3, "D:\\"),
        (2, 3, "E:\\"),
    ]


def test_a_drive_that_fails_is_reported_and_the_others_are_still_cleaned(
    emptied: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_on_c(drive: str) -> None:
        if drive == "C:\\":
            raise OSError
        emptied.append(drive)

    monkeypatch.setattr(recycle_bin, "_empty", fail_on_c)

    outcome = recycle_bin.empty_recycle_bin(lambda _: None)

    assert outcome.failures == ("C:\\",)
    assert (outcome.items, outcome.bytes_freed) == (2, 500)
    assert emptied == ["E:\\"]
