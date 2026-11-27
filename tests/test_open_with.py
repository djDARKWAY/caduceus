import pytest

from caduceus.maintenance.apps import open_with
from caduceus.maintenance.apps.open_with import clean_open_with, mru_without


def test_the_removed_entries_leave_the_recent_order_of_the_rest() -> None:
    assert mru_without("cabd", {"a", "d"}) == "cb"


def test_an_app_whose_file_is_gone_is_an_orphan_but_one_that_exists_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = {"gone.exe": r"C:\Gone\gone.exe", "here.exe": r"C:\Here\here.exe", "none.exe": None}
    monkeypatch.setattr(open_with, "_names_registered", lambda _hive, _root: list(targets))
    monkeypatch.setattr(
        open_with, "_command_target", lambda hive, _root, name: targets[name] if hive else None
    )
    monkeypatch.setattr("os.path.isfile", lambda path: "Here" in path)

    assert open_with.orphan_applications() == ["gone.exe"]


def test_a_menu_without_orphans_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(open_with, "orphan_applications", list)

    assert clean_open_with(lambda _: None).notice == "notice.open_with_clean"


def test_orphans_are_only_removed_after_a_backup_and_a_failed_backup_removes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(open_with, "orphan_applications", lambda: ["gone.exe"])
    monkeypatch.setattr(open_with, "_export", lambda *_args: False)

    def refuse(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("nothing may be removed without a backup")

    monkeypatch.setattr(open_with, "run_system_tool", refuse)

    outcome = clean_open_with(lambda _: None)

    assert outcome.failures == ("gone.exe",)
    assert outcome.items == 0
