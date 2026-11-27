import os
import sys
import uuid
import winreg
from collections.abc import Iterator
from pathlib import Path

import pytest

from caduceus.maintenance.memory import startup_programs
from caduceus.maintenance.memory.executable_info import describe
from caduceus.maintenance.memory.process_memory import memory_by_executable
from caduceus.maintenance.memory.startup_programs import (
    StartupEntry,
    StartupSource,
    executable_of,
    impact_of,
    is_enabled,
    list_startup_entries,
    memory_of,
    parse_enabled,
    set_enabled,
    toggle_startup,
)

MB = 1024 * 1024


def delete_tree(path: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return  # a chave nunca chegou a existir
    for child in children:
        delete_tree(rf"{path}\{child}")
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


@pytest.fixture
def test_key() -> Iterator[str]:
    """Uma chave só deste teste, no registo do utilizador, que se apaga no fim."""
    root = r"Software\CaduceusTests"
    path = rf"{root}\{uuid.uuid4().hex}"
    yield path
    delete_tree(path)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)
    except OSError:
        pass  # a raiz só sai quando ficar vazia


@pytest.fixture
def sandboxed_registry(test_key: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """As decisões de ligado/desligado passam a gravar-se na chave de teste, nunca na do Windows."""
    approved = {
        source: (winreg.HKEY_CURRENT_USER, rf"{test_key}\Approved") for source in StartupSource
    }
    monkeypatch.setattr(startup_programs, "_APPROVED", approved)
    return test_key


def entry(source: StartupSource = StartupSource.RUN_USER, name: str = "Example") -> StartupEntry:
    return StartupEntry(name, name, r"C:\Example\example.exe", source, None)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (r'"C:\Program Files\App\app.exe" --minimized', r"c:\program files\app\app.exe"),
        (r"C:\Tools\tool.exe /silent", r"c:\tools\tool.exe"),
        (r"C:\Program Files\App\app.exe -x", r"c:\program files\app\app.exe"),
        ("%SystemRoot%\\System32\\tool.exe", None),
        ("", None),
        ("just words", None),
    ],
)
def test_the_executable_is_read_from_the_startup_command(
    command: str, expected: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    if command.startswith("%SystemRoot%"):
        expected = r"c:\windows\system32\tool.exe"

    assert executable_of(command) == expected


def test_a_program_that_is_running_reports_its_memory() -> None:
    running = {r"c:\apps\app.exe": 50 * MB, r"c:\apps\other.exe": 9 * MB}

    assert memory_of(r'"C:\Apps\App.exe" --minimized', running) == 50 * MB
    assert memory_of(r"C:\Apps\missing.exe", running) is None


def test_a_squirrel_updater_reports_the_memory_of_the_app_it_starts() -> None:
    running = {
        r"c:\users\me\appdata\local\discord\app-1.0\discord.exe": 700 * MB,
        r"c:\users\me\appdata\local\discord\app-1.0\helper.exe": 100 * MB,
        r"c:\users\me\appdata\local\other\other.exe": 5 * MB,
    }
    command = r'"C:\Users\me\AppData\Local\Discord\Update.exe" --processStart Discord.exe'

    assert memory_of(command, running) == 800 * MB


def test_only_the_squirrel_updater_is_matched_by_folder() -> None:
    running = {r"c:\apps\tool\inner\worker.exe": 40 * MB}

    assert memory_of(r"C:\Apps\Tool\launcher.exe", running) is None


@pytest.mark.parametrize(
    ("memory", "expected"),
    [(None, None), (0, "low"), (99 * MB, "low"), (100 * MB, "medium"), (300 * MB, "high")],
)
def test_the_impact_grows_with_the_memory_in_use(memory: int | None, expected: str | None) -> None:
    assert impact_of(memory) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"", True),
        (b"\x02\x00\x00\x00" + bytes(8), True),
        (b"\x06\x00\x00\x00" + bytes(8), True),
        (b"\x03\x00\x00\x00" + bytes(8), False),
        (b"\x07\x00\x00\x00" + bytes(8), False),
    ],
)
def test_the_windows_startup_state_is_read_from_its_first_byte(data: bytes, expected: bool) -> None:
    assert parse_enabled(data) is expected


@pytest.mark.usefixtures("sandboxed_registry")
def test_a_program_without_a_saved_decision_is_enabled() -> None:
    assert is_enabled(entry())


def test_disabling_and_enabling_a_program_round_trips_in_the_windows_format(
    sandboxed_registry: str,
) -> None:
    example = entry()

    set_enabled(example, False, now_seconds=1_700_000_000)
    assert not is_enabled(example)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{sandboxed_registry}\Approved") as key:
        data, kind = winreg.QueryValueEx(key, example.name)
    assert kind == winreg.REG_BINARY
    assert len(data) == 12
    assert data[:4] == b"\x03\x00\x00\x00"

    set_enabled(example, True, now_seconds=1_700_000_000)
    assert is_enabled(example)


@pytest.mark.usefixtures("sandboxed_registry")
def test_toggling_a_program_flips_its_state_and_reports_nothing_wrong() -> None:
    example = entry()

    first = toggle_startup(example)(lambda _: None)
    disabled = is_enabled(example)
    second = toggle_startup(example)(lambda _: None)

    assert not first.failures and not first.admin_required
    assert not disabled
    assert not second.failures
    assert is_enabled(example)


@pytest.mark.usefixtures("sandboxed_registry")
def test_a_program_for_all_users_asks_for_administrator_and_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup_programs, "is_admin", lambda: False)
    machine = entry(StartupSource.RUN_MACHINE)

    outcome = toggle_startup(machine)(lambda _: None)

    assert outcome.admin_required == (machine.label,)
    assert is_enabled(machine)


def test_startup_programs_come_from_the_run_keys_and_the_startup_folders_heaviest_first(
    sandboxed_registry: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_path = rf"{sandboxed_registry}\Run"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, run_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Light", 0, winreg.REG_SZ, r'"C:\Apps\light.exe"')
        winreg.SetValueEx(key, "Heavy", 0, winreg.REG_SZ, r'"C:\Apps\heavy.exe" --go')
    folder = tmp_path / "Startup"
    folder.mkdir()
    (folder / "Shortcut.lnk").write_bytes(b"x")
    (folder / "desktop.ini").write_bytes(b"x")
    monkeypatch.setattr(
        startup_programs,
        "_RUN_KEYS",
        ((StartupSource.RUN_USER, winreg.HKEY_CURRENT_USER, run_path),),
    )
    monkeypatch.setattr(startup_programs, "_FOLDERS", ((StartupSource.FOLDER_USER, str(folder)),))
    monkeypatch.setattr(startup_programs, "_service_entries", lambda _running: [])
    monkeypatch.setattr(
        startup_programs,
        "memory_by_executable",
        lambda: {r"c:\apps\light.exe": 10 * MB, r"c:\apps\heavy.exe": 500 * MB},
    )

    entries = list_startup_entries()

    assert [found.label for found in entries] == ["Heavy", "Light", "Shortcut"]
    assert entries[0].memory_bytes == 500 * MB
    assert entries[2].memory_bytes is None
    assert entries[2].source is StartupSource.FOLDER_USER


def test_the_memory_of_the_running_programs_includes_this_one() -> None:
    assert os.path.normcase(sys.executable) in memory_by_executable()


def add_service(
    base: str,
    name: str,
    *,
    start: int = 2,
    kind: int = 0x10,
    image: str | None = None,
    **extra: int,
) -> None:
    path = rf"{base}\Services\{name}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, start)
        winreg.SetValueEx(key, "Type", 0, winreg.REG_DWORD, kind)
        winreg.SetValueEx(key, "ImagePath", 0, winreg.REG_SZ, image or f'"{sys.executable}"')
        for value_name, number in extra.items():
            winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, number)


@pytest.fixture
def sandboxed_services(test_key: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Só os serviços da chave de teste, sem programas de arranque nem processos reais."""
    monkeypatch.setattr(startup_programs, "_SERVICES_HIVE", winreg.HKEY_CURRENT_USER)
    monkeypatch.setattr(startup_programs, "_SERVICES_KEY", rf"{test_key}\Services")
    monkeypatch.setattr(startup_programs, "_RUN_KEYS", ())
    monkeypatch.setattr(startup_programs, "_FOLDERS", ())
    monkeypatch.setattr(startup_programs, "memory_by_executable", dict)
    return test_key


def test_only_third_party_services_that_start_automatically_are_listed(
    sandboxed_services: str,
) -> None:
    add_service(sandboxed_services, "Automatic")
    add_service(sandboxed_services, "Manual", start=3)
    add_service(sandboxed_services, "Driver", kind=0x1)
    add_service(sandboxed_services, "OfWindows", image=r"C:\Windows\System32\cmd.exe")

    entries = list_startup_entries()

    assert [(entry.name, entry.source) for entry in entries] == [
        ("Automatic", StartupSource.SERVICE)
    ]
    assert entries[0].needs_admin


def test_a_service_switched_off_goes_to_manual_and_can_be_switched_on_again(
    sandboxed_services: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_service(sandboxed_services, "Automatic", DelayedAutostart=1)
    monkeypatch.setattr(startup_programs, "is_admin", lambda: True)
    service = list_startup_entries()[0]
    path = rf"{sandboxed_services}\Services\Automatic"

    toggle_startup(service)(lambda _: None)
    still_listed = [entry.name for entry in list_startup_entries()]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
        start = winreg.QueryValueEx(key, "Start")[0]
        delayed = winreg.QueryValueEx(key, "DelayedAutostart")[0]

    assert not is_enabled(service)
    assert (start, delayed) == (3, 1)
    assert still_listed == ["Automatic"]

    toggle_startup(service)(lambda _: None)

    assert is_enabled(service)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
        assert winreg.QueryValueEx(key, "Start")[0] == 2
        with pytest.raises(FileNotFoundError):
            winreg.QueryValueEx(key, "CaduceusDisabledStartup")


def test_a_program_is_shown_by_the_name_in_its_file_properties() -> None:
    command = f'"{sys.executable}" --minimized'

    assert startup_programs._readable_label(command, "technical_name") != "technical_name"
    assert startup_programs._readable_label("not a program", "technical_name") == "technical_name"


def test_the_squirrel_updater_keeps_the_technical_name_because_every_app_calls_it_update() -> None:
    command = r'"C:\Users\me\AppData\Local\Discord\Update.exe" --processStart Discord.exe'

    assert startup_programs._readable_label(command, "Discord") == "Discord"


def test_a_file_without_properties_has_no_readable_name(tmp_path: Path) -> None:
    empty = tmp_path / "empty.exe"
    empty.write_bytes(b"")

    assert describe(str(empty)).name is None
    assert describe(str(tmp_path / "missing.exe")).name is None


def test_microsoft_files_are_recognised_by_their_manufacturer() -> None:
    windows_tool = os.path.expandvars(r"%WINDIR%\System32\cmd.exe")

    assert describe(windows_tool).from_microsoft
    assert not describe(sys.executable).from_microsoft


@pytest.mark.parametrize(
    ("source", "label", "expected"),
    [
        (StartupSource.SERVICE, "Norton Antivirus", True),
        (StartupSource.SERVICE, "FortiClient VPN Service Scheduler", True),
        (StartupSource.SERVICE, "MongoDB Server (MongoDB)", True),
        (StartupSource.SERVICE, "Google Updater Service", False),
        (StartupSource.SERVICE, "LGHUB Updater Service", False),
        (StartupSource.RUN_USER, "Bitwarden", False),
        (StartupSource.RUN_MACHINE, "Norton 360", False),
    ],
)
def test_only_the_delicate_services_need_safe_mode_off(
    source: StartupSource, label: str, expected: bool
) -> None:
    item = StartupEntry(label, label, r"C:pp.exe", source, None)

    assert item.needs_safe_mode_off is expected
