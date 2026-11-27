import os
import subprocess
import time
from pathlib import Path

import pytest

from caduceus.maintenance import cleaner
from caduceus.maintenance.actions import Outcome, Step
from caduceus.maintenance.cleaner import Location, clean_locations, estimate_locations


@pytest.fixture(autouse=True)
def administrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cleaner, "is_admin", lambda: True)


def write(path: Path, size: int = 10, age_hours: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if age_hours:
        modified = time.time() - age_hours * 3600
        os.utime(path, (modified, modified))


def make_junction(link: Path, target: Path) -> None:
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
    )


def clean(*locations: Location) -> Outcome:
    return clean_locations(locations, lambda _: None)


def test_everything_inside_the_folder_goes_but_the_folder_stays(tmp_path: Path) -> None:
    write(tmp_path / "a.txt", size=10)
    write(tmp_path / "sub" / "b.txt", size=20)

    outcome = clean(Location(str(tmp_path), "category.test"))

    assert (outcome.items, outcome.bytes_freed) == (2, 30)
    assert tmp_path.is_dir()
    assert list(tmp_path.iterdir()) == []


def test_files_newer_than_the_minimum_age_are_kept(tmp_path: Path) -> None:
    write(tmp_path / "old.tmp", age_hours=48)
    write(tmp_path / "new.tmp", age_hours=1)

    outcome = clean(Location(str(tmp_path), "category.test", min_age_hours=24))

    assert outcome.items == 1
    assert [path.name for path in tmp_path.iterdir()] == ["new.tmp"]


def test_only_names_matching_the_pattern_are_deleted(tmp_path: Path) -> None:
    write(tmp_path / "thumbcache_32.db")
    write(tmp_path / "thumbcache_96.db")
    write(tmp_path / "keep.txt")

    outcome = clean(Location(str(tmp_path), "category.test", pattern="thumbcache_*.db"))

    assert outcome.items == 2
    assert [path.name for path in tmp_path.iterdir()] == ["keep.txt"]


def test_a_location_that_does_not_exist_is_ignored(tmp_path: Path) -> None:
    assert clean(Location(str(tmp_path / "missing"), "category.test")) == Outcome(0, 0)


def test_environment_variables_in_the_path_are_expanded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADUCEUS_TEST_FOLDER", str(tmp_path))
    write(tmp_path / "a.txt")

    assert clean(Location("%CADUCEUS_TEST_FOLDER%", "category.test")).items == 1


def test_a_location_that_needs_administrator_is_reported_and_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cleaner, "is_admin", lambda: False)
    write(tmp_path / "a.txt")

    outcome = clean(Location(str(tmp_path), "category.test", needs_admin=True))

    assert outcome.admin_required == (str(tmp_path),)
    assert outcome.items == 0
    assert (tmp_path / "a.txt").exists()


def test_a_protected_folder_that_cannot_even_be_checked_asks_for_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(_path: Path) -> bool:
        raise PermissionError

    monkeypatch.setattr(cleaner, "is_admin", lambda: False)
    monkeypatch.setattr(Path, "is_dir", deny)

    outcome = clean(Location(str(tmp_path), "category.test", needs_admin=True))

    assert outcome.admin_required == (str(tmp_path),)
    assert outcome.failures == ()


def test_a_folder_that_cannot_be_read_as_a_normal_user_is_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(_path: Path) -> bool:
        raise PermissionError

    monkeypatch.setattr(Path, "is_dir", deny)

    outcome = clean(Location(str(tmp_path), "category.test"))

    assert outcome.failures == (str(tmp_path),)


def test_a_junction_is_never_followed_outside_the_folder(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write(outside / "keep.txt")
    root = tmp_path / "root"
    root.mkdir()
    make_junction(root / "link", outside)

    outcome = clean(Location(str(root), "category.test"))

    assert outcome.items == 0
    assert (outside / "keep.txt").exists()


def test_a_target_folder_that_is_a_junction_is_refused_and_its_destination_untouched(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    write(outside / "keep.txt")
    make_junction(tmp_path / "link", outside)

    outcome = clean(Location(str(tmp_path / "link"), "category.test"))

    assert outcome.failures == (str(tmp_path / "link"),)
    assert outcome.items == 0
    assert (outside / "keep.txt").exists()


def test_a_target_folder_below_a_junction_is_refused_and_its_destination_untouched(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    write(outside / "cache" / "keep.txt")
    make_junction(tmp_path / "link", outside)
    below = tmp_path / "link" / "cache"

    outcome = clean(Location(str(below), "category.test"))

    assert outcome.failures == (str(below),)
    assert (outside / "cache" / "keep.txt").exists()


def test_a_file_that_cannot_be_deleted_is_left_alone_and_not_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_path: Path, _missing_ok: bool = False) -> None:
        raise PermissionError

    monkeypatch.setattr(Path, "unlink", refuse)
    write(tmp_path / "locked.tmp")

    outcome = clean(Location(str(tmp_path), "category.test"))

    assert (outcome.items, outcome.bytes_freed) == (0, 0)
    assert (tmp_path / "locked.tmp").exists()


def test_progress_reports_each_entry_with_what_is_being_cleaned(tmp_path: Path) -> None:
    for name in ("a.txt", "b.txt", "c.txt"):
        write(tmp_path / name)
    steps: list[Step] = []

    clean_locations([Location(str(tmp_path), "category.test")], steps.append)

    assert [(step.done, step.total) for step in steps] == [(0, 3), (1, 3), (2, 3)]
    assert {step.values["path"] for step in steps} == {
        str(tmp_path / name) for name in ("a.txt", "b.txt", "c.txt")
    }


def test_results_are_grouped_by_category_in_the_order_of_the_locations(tmp_path: Path) -> None:
    write(tmp_path / "a" / "x.txt", size=10)
    write(tmp_path / "b" / "y.txt", size=20)
    write(tmp_path / "c" / "z.txt", size=5)
    (tmp_path / "empty").mkdir()

    outcome = clean(
        Location(str(tmp_path / "a"), "category.first"),
        Location(str(tmp_path / "empty"), "category.second"),
        Location(str(tmp_path / "b"), "category.first"),
        Location(str(tmp_path / "c"), "category.third"),
    )

    assert [(row.label_key, row.items, row.bytes_freed) for row in outcome.rows] == [
        ("category.first", 2, 30),
        ("category.second", 0, 0),
        ("category.third", 1, 5),
    ]


def test_the_estimate_counts_what_would_be_freed_and_deletes_nothing(tmp_path: Path) -> None:
    write(tmp_path / "old.tmp", size=10, age_hours=48)
    write(tmp_path / "sub" / "old2.tmp", size=20, age_hours=48)
    write(tmp_path / "new.tmp", size=100, age_hours=1)

    estimate = estimate_locations([Location(str(tmp_path), "category.test", min_age_hours=24)])

    assert estimate == 30
    assert len(list(tmp_path.rglob("*.tmp"))) == 3


def test_the_estimate_skips_locations_that_need_an_administrator_when_not_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cleaner, "is_admin", lambda: False)
    write(tmp_path / "a.txt", size=10)

    assert estimate_locations([Location(str(tmp_path), "category.test", needs_admin=True)]) == 0


def test_the_estimate_never_follows_a_junction(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write(outside / "big.bin", size=1000)
    root = tmp_path / "root"
    root.mkdir()
    make_junction(root / "link", outside)

    assert estimate_locations([Location(str(root), "category.test")]) == 0


def test_the_estimate_ignores_a_target_folder_that_is_or_is_below_a_junction(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    write(outside / "cache" / "big.bin", size=1000)
    make_junction(tmp_path / "link", outside)

    assert estimate_locations([Location(str(tmp_path / "link"), "category.test")]) == 0
    assert estimate_locations([Location(str(tmp_path / "link" / "cache"), "category.test")]) == 0


def test_a_star_in_the_path_cleans_every_matching_folder_and_only_those(tmp_path: Path) -> None:
    write(tmp_path / "Default" / "Cache" / "a.bin", size=10)
    write(tmp_path / "Profile 1" / "Cache" / "b.bin", size=20)
    write(tmp_path / "Default" / "Cookies" / "keep.db", size=5)

    outcome = clean(Location(str(tmp_path / "*" / "Cache"), "category.test"))

    assert (outcome.items, outcome.bytes_freed) == (2, 30)
    assert (tmp_path / "Default" / "Cookies" / "keep.db").exists()


def test_a_star_that_matches_nothing_is_not_an_error(tmp_path: Path) -> None:
    assert clean(Location(str(tmp_path / "*" / "Cache"), "category.test")) == Outcome(0, 0)


def test_the_estimate_and_the_cleaning_agree_on_a_star_path(tmp_path: Path) -> None:
    write(tmp_path / "Default" / "Cache" / "a.bin", size=10)
    write(tmp_path / "Profile 1" / "Cache" / "b.bin", size=20)
    location = Location(str(tmp_path / "*" / "Cache"), "category.test")

    assert estimate_locations([location]) == 30
    assert clean(location).bytes_freed == 30


def test_a_folder_found_by_a_star_that_is_a_junction_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write(outside / "Cache" / "keep.bin", size=10)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    make_junction(profiles / "Default", outside)

    outcome = clean(Location(str(profiles / "*" / "Cache"), "category.test"))

    assert outcome.failures == (str(profiles / "Default" / "Cache"),)
    assert (outside / "Cache" / "keep.bin").exists()
