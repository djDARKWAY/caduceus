import sys
import winreg
from pathlib import Path

import pytest

from caduceus.maintenance.apps import open_with
from caduceus.maintenance.apps.open_with import clean_open_with, mru_without


def test_the_removed_entries_leave_the_recent_order_of_the_rest() -> None:
    assert mru_without("cabd", {"a", "d"}) == "cb"


def set_values(path: str, **values: str) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        for name, value in values.items():
            winreg.SetValueEx(key, "" if name == "default" else name, 0, winreg.REG_SZ, value)


def values_of(path: str) -> dict[str, str]:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
        pairs = [winreg.EnumValue(key, i) for i in range(winreg.QueryInfoKey(key)[1])]
    return {name: str(value) for name, value, _kind in pairs}


def key_exists(path: str) -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, path))
    except FileNotFoundError:
        return False
    return True


@pytest.fixture
def open_with_registry(
    test_key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str]:
    """As apps registadas e as listas «Abrir com» passam a ser as da chave de teste, e as cópias
    de segurança vão para uma pasta temporária. Devolve a chave das apps e a das extensões."""
    applications, machine = rf"{test_key}\Applications", rf"{test_key}\Machine"
    extensions = rf"{test_key}\FileExts"
    monkeypatch.setattr(open_with, "_APPLICATIONS_KEY", applications)
    monkeypatch.setattr(open_with, "_MACHINE_APPLICATIONS_KEY", machine)
    monkeypatch.setattr(open_with, "_FILE_EXTS_KEY", extensions)
    monkeypatch.setattr(open_with, "_backup_file", lambda name: tmp_path / f"{name}.reg")
    set_values(rf"{applications}\gone.exe\shell\open\command", default=r'"C:\Gone\gone.exe" "%1"')
    set_values(rf"{applications}\here.exe\shell\open\command", default=f'"{sys.executable}" "%1"')
    set_values(rf"{extensions}\.txt\OpenWithList", a="gone.exe", b="here.exe", MRUList="ab")
    return applications, extensions


@pytest.mark.usefixtures("open_with_registry")
def test_an_app_whose_file_is_gone_is_an_orphan_but_one_that_exists_is_not() -> None:
    assert open_with.orphan_applications() == ["gone.exe"]


def test_cleaning_removes_only_the_orphan_and_keeps_a_backup_of_what_it_touched(
    open_with_registry: tuple[str, str], tmp_path: Path
) -> None:
    applications, extensions = open_with_registry

    outcome = clean_open_with(lambda _: None)

    assert outcome.items == 1
    assert outcome.failures == ()
    assert not key_exists(rf"{applications}\gone.exe")
    assert key_exists(rf"{applications}\here.exe")
    assert values_of(rf"{extensions}\.txt\OpenWithList") == {"b": "here.exe", "MRUList": "b"}
    assert (tmp_path / "gone.exe.reg").is_file()
    assert (tmp_path / "fileexts.reg").is_file()


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
