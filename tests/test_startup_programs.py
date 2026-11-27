import os
import sys
import uuid
import winreg
from collections.abc import Iterator
from pathlib import Path

import pytest

from caduceus.maintenance.memory import startup_programs
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


@pytest.fixture
def test_key() -> Iterator[str]:
    """Uma chave só deste teste, no registo do utilizador, que se apaga no fim."""
    root = r"Software\CaduceusTests"
    path = rf"{root}\{uuid.uuid4().hex}"
    yield path
    for key in (path + r"\Run", path + r"\Approved", path, root):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except OSError:
            pass  # só existe o que o teste criou, e a raiz só sai quando ficar vazia


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
