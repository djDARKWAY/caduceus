import os
import uuid
import winreg
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from caduceus.controllers import menus
from caduceus.controllers.menus import AdminNeed, programs_menu
from caduceus.maintenance.actions import Report, Step
from caduceus.maintenance.apps import installed_programs
from caduceus.maintenance.apps.installed_programs import (
    InstalledProgram,
    is_installed,
    list_installed_programs,
    remove_leftover_entry,
    split_command,
    uninstall_program,
)

MSI_PRODUCT = "{11111111-2222-3333-4444-555555555555}"
ERROR_FILE_NOT_FOUND = 2
ERROR_CANCELLED = 1223


def delete_tree(path: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return  # a chave nunca chegou a existir, ou o desinstalador fictício já a apagou
    for child in children:
        delete_tree(rf"{path}\{child}")
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


@pytest.fixture
def uninstall_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Uma chave `Uninstall` só deste teste, no registo do utilizador, que se apaga no fim."""
    root = r"Software\CaduceusTests"
    path = rf"{root}\{uuid.uuid4().hex}"
    monkeypatch.setattr(installed_programs, "_UNINSTALL_KEYS", ((winreg.HKEY_CURRENT_USER, path),))
    yield path
    delete_tree(path)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)
    except OSError:
        pass  # a raiz só sai quando ficar vazia


def register(root: str, key_name: str, **values: str | int) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{root}\{key_name}") as key:
        for name, value in values.items():
            kind = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
            winreg.SetValueEx(key, name, 0, kind, value)


def test_programs_are_listed_by_name_with_their_size_and_install_date(uninstall_key: str) -> None:
    register(
        uninstall_key,
        "Zed",
        DisplayName="Zed Editor",
        UninstallString="zed.exe",
        EstimatedSize=2048,
        InstallDate="20250314",
    )
    register(uninstall_key, "Alpha", DisplayName="alpha tool", UninstallString="alpha.exe")

    programs = list_installed_programs()

    assert [program.name for program in programs] == ["alpha tool", "Zed Editor"]
    assert programs[0].size_bytes is None
    assert programs[1].size_bytes == 2048 * 1024
    assert programs[1].installed_on == "2025-03-14"


def test_components_updates_and_programs_that_cannot_be_removed_are_not_listed(
    uninstall_key: str,
) -> None:
    register(uninstall_key, "Kept", DisplayName="Kept", UninstallString="kept.exe")
    register(uninstall_key, "Part", DisplayName="Part", UninstallString="x.exe", SystemComponent=1)
    register(uninstall_key, "Fixed", DisplayName="Fixed", UninstallString="x.exe", NoRemove=1)
    register(uninstall_key, "KB1", DisplayName="KB1", UninstallString="x.exe", ParentKeyName="Kept")
    register(
        uninstall_key, "Hotfix", DisplayName="Fix", UninstallString="x.exe", ReleaseType="Hotfix"
    )
    register(uninstall_key, "NoCommand", DisplayName="No command")
    register(uninstall_key, "NoName", UninstallString="x.exe")

    assert [program.name for program in list_installed_programs()] == ["Kept"]


def test_a_windows_installer_program_is_uninstalled_and_not_repaired(uninstall_key: str) -> None:
    register(
        uninstall_key,
        MSI_PRODUCT,
        DisplayName="Packaged",
        UninstallString=f"MsiExec.exe /I{MSI_PRODUCT}",
        WindowsInstaller=1,
    )

    [program] = list_installed_programs()

    assert program.uninstall_command == f"MsiExec.exe /X{MSI_PRODUCT}"


def test_the_same_program_registered_twice_is_listed_once(uninstall_key: str) -> None:
    register(uninstall_key, "A", DisplayName="Tool", DisplayVersion="1.0", UninstallString="a.exe")
    register(uninstall_key, "B", DisplayName="Tool", DisplayVersion="1.0", UninstallString="b.exe")

    assert len(list_installed_programs()) == 1


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (r'"C:\Program Files\A\un.exe" /S', (r"C:\Program Files\A\un.exe", "/S")),
        (r"C:\Program Files\A\un.exe --remove", (r"C:\Program Files\A\un.exe", "--remove")),
        ("MsiExec.exe /X{GUID}", ("MsiExec.exe", "/X{GUID}")),
        (r"C:\A\remove.exe", (r"C:\A\remove.exe", "")),
        ("winget uninstall --id Tool", ("winget", "uninstall --id Tool")),
        ("", None),
        ('""', None),
    ],
)
def test_the_uninstaller_is_split_from_its_arguments(
    command: str, expected: tuple[str, str] | None
) -> None:
    assert split_command(command) == expected


def test_drivers_and_runtimes_can_only_be_uninstalled_with_safe_mode_off() -> None:
    def named(name: str) -> InstalledProgram:
        return InstalledProgram(name, "", "", "", None, "x.exe", winreg.HKEY_CURRENT_USER, "")

    assert named("NVIDIA Graphics Driver 560.94").needs_safe_mode_off
    assert named("Microsoft Visual C++ 2015-2022 Redistributable (x64)").needs_safe_mode_off
    assert not named("Spotify").needs_safe_mode_off


def registered_program(root: str) -> InstalledProgram:
    register(root, "Example", DisplayName="Example", UninstallString='"C:\\Ex\\un.exe" /S')
    [program] = list_installed_programs()
    return program


def no_report(_step: Step) -> None:
    return None


def test_a_program_whose_uninstaller_removed_it_is_reported_as_uninstalled(
    uninstall_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    program = registered_program(uninstall_key)
    launched: list[tuple[str, str]] = []

    def fake_uninstaller(executable: str, arguments: str, _report: Report, _step: Step) -> int:
        launched.append((executable, arguments))
        delete_tree(program.key_path)
        return 0

    free_space = iter([1000, 5000])
    monkeypatch.setattr(installed_programs, "_run_uninstaller", fake_uninstaller)
    monkeypatch.setattr(installed_programs, "free_bytes", lambda: next(free_space))

    outcome = uninstall_program(program)(no_report)

    assert launched == [("C:\\Ex\\un.exe", "/S")]
    assert not is_installed(program)
    assert outcome.items == 1
    assert outcome.bytes_freed == 4000
    assert outcome.notice is None


@pytest.mark.parametrize(
    ("error", "notice"),
    [
        (0, "notice.program_still_installed"),
        (ERROR_CANCELLED, "notice.uninstall_cancelled"),
        (ERROR_FILE_NOT_FOUND, "notice.uninstaller_not_opened"),
    ],
)
def test_a_program_that_was_not_uninstalled_says_why_and_stays_listed(
    uninstall_key: str, monkeypatch: pytest.MonkeyPatch, error: int, notice: str
) -> None:
    program = registered_program(uninstall_key)
    monkeypatch.setattr(installed_programs, "_run_uninstaller", lambda *_args: error)
    monkeypatch.setattr(installed_programs, "free_bytes", lambda: 0)

    outcome = uninstall_program(program)(no_report)

    assert outcome.notice == notice
    assert outcome.items == 0
    assert is_installed(program)


GONE_FOLDER = r"C:\Caduceus tests\no such folder"


def program_running(
    command: str, hive: int = winreg.HKEY_CURRENT_USER, location: str = GONE_FOLDER
) -> InstalledProgram:
    return InstalledProgram(
        "Example", "", "", "", None, command, hive, r"Software\CaduceusTests\x", location
    )


def test_a_program_is_a_leftover_when_its_uninstaller_and_its_folder_are_both_gone() -> None:
    assert program_running(r'"C:\Caduceus tests\unins000.exe" /SILENT').has_missing_uninstaller


def test_a_program_whose_uninstaller_file_exists_is_not_a_leftover(tmp_path: Path) -> None:
    uninstaller = tmp_path / "unins000.exe"
    uninstaller.write_bytes(b"")

    assert not program_running(f'"{uninstaller}" /SILENT').has_missing_uninstaller


def test_a_program_whose_folder_still_exists_is_not_a_leftover_even_without_its_uninstaller(
    tmp_path: Path,
) -> None:
    command = rf'"{tmp_path}\unins000.exe"'

    assert not program_running(command, location=str(tmp_path)).has_missing_uninstaller


def test_a_program_that_does_not_register_its_folder_is_not_taken_as_a_leftover() -> None:
    command = r'"C:\Caduceus tests\python-installer.exe" /uninstall'

    assert not program_running(command, location="").has_missing_uninstaller


def test_a_folder_on_a_drive_that_is_not_connected_is_not_taken_as_a_leftover() -> None:
    absent = next(letter for letter in "ZYXWVUTSR" if not os.path.exists(f"{letter}:\\"))

    command = rf'"{absent}:\Games\unins000.exe"'

    assert not program_running(command, location=rf"{absent}:\Games").has_missing_uninstaller


@pytest.mark.parametrize("command", ["MsiExec.exe /X{GUID}", "winget uninstall --id Tool", ""])
def test_a_command_without_a_full_path_is_never_taken_as_a_missing_uninstaller(
    command: str,
) -> None:
    assert not program_running(command).has_missing_uninstaller


def test_removing_a_leftover_entry_saves_a_backup_first_and_deletes_only_the_entry(
    uninstall_key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    program = registered_program(uninstall_key)
    saved: list[tuple[str, list[str], bool]] = []

    def fake_reg_export(
        executable: str, arguments: list[str], _report: Report, _step_key: str
    ) -> bool:
        saved.append((executable, arguments, is_installed(program)))  # a entrada ainda lá está
        return True

    monkeypatch.setattr(installed_programs, "run_system_tool", fake_reg_export)

    outcome = remove_leftover_entry(program)(no_report)

    backup = tmp_path / "Caduceus" / "removed-entries" / "Example.reg"
    key = rf"HKCU\{uninstall_key}\Example"
    assert saved == [("reg.exe", ["export", key, str(backup), "/y"], True)]
    assert not is_installed(program)
    assert outcome.items == 1
    assert outcome.bytes_freed == 0
    assert outcome.rows[0].values == {"name": "Example"}


def test_if_the_backup_cannot_be_saved_the_entry_is_kept(
    uninstall_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    program = registered_program(uninstall_key)
    monkeypatch.setattr(installed_programs, "run_system_tool", lambda *_args: False)

    outcome = remove_leftover_entry(program)(no_report)

    assert outcome.failures == ("Example",)
    assert is_installed(program)


def test_a_machine_entry_is_not_touched_without_administrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_to_run(*_args: object) -> bool:
        raise AssertionError("nothing may be saved or removed without administrator")

    monkeypatch.setattr(installed_programs, "is_admin", lambda: False)
    monkeypatch.setattr(installed_programs, "run_system_tool", refuse_to_run)
    program = program_running(r'"C:\Nowhere\un.exe"', winreg.HKEY_LOCAL_MACHINE)

    outcome = remove_leftover_entry(program)(no_report)

    assert outcome.admin_required == ("Example",)


def test_a_program_with_a_missing_uninstaller_offers_to_clean_the_leftover_instead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    machine = winreg.HKEY_LOCAL_MACHINE
    gone = program_running(r'"C:\Caduceus tests\un.exe"', machine)
    runtime = replace(
        program_running(r'"C:\Caduceus tests\un.exe"'), name="Some Runtime", key_path="b"
    )
    here = program_running("MsiExec.exe /X{GUID}", machine)
    monkeypatch.setattr(menus, "list_installed_programs", lambda: [gone, runtime, here])

    stale_machine, stale_user, healthy = programs_menu().items

    assert stale_machine.confirm_key == "apps.uninstall.stale.confirm"
    assert stale_machine.admin is AdminNeed.ALL
    assert not stale_machine.risky
    assert stale_user.admin is None
    assert not stale_user.risky  # um runtime sem desinstalador não há o que proteger
    assert healthy.confirm_key == "apps.uninstall.confirm"
