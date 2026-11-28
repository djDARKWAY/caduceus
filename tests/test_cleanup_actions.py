import os
import time
import winreg
from pathlib import Path

import pytest

from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.free_space import (
    cleaner,
    icon_cache,
    install_leftovers,
    previous_windows,
    recent_history,
    system_caches,
    temp_and_logs,
)


def make_file(root: Path, name: str, content: bytes = b"test") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_icon_and_thumbnail_databases_are_deleted_while_explorer_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    explorer = tmp_path / "Microsoft" / "Windows" / "Explorer"
    icon = make_file(explorer, "iconcache_32.db")
    thumbnail = make_file(explorer, "thumbcache_idx.db")
    kept = make_file(explorer, "iconcache-not-a-file.db\\data.txt")
    unrelated = make_file(explorer, "settings.db")
    restarted = []

    def stop() -> bool:
        return icon.exists() and thumbnail.exists()

    def start() -> bool:
        restarted.append(True)
        return not icon.exists() and not thumbnail.exists()

    monkeypatch.setattr(icon_cache, "stop_explorer", stop)
    monkeypatch.setattr(icon_cache, "start_explorer", start)

    assert icon_cache.estimate_icon_cache() == 8
    outcome = icon_cache.clean_icon_cache(lambda _: None)

    assert restarted and not outcome.failures
    assert (outcome.items, outcome.bytes_freed) == (2, 8)
    assert kept.exists() and unrelated.exists()


def test_rebuild_reports_an_explorer_restart_failure_alongside_the_bytes_freed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    make_file(tmp_path, r"Microsoft\Windows\Explorer\iconcache.db")
    monkeypatch.setattr(icon_cache, "stop_explorer", lambda: True)
    monkeypatch.setattr(icon_cache, "start_explorer", lambda: False)

    outcome = icon_cache.clean_icon_cache(lambda _: None)

    assert outcome.failures == ("explorer.exe",)
    assert outcome.bytes_freed == 4


def test_system_cache_estimate_includes_delivery_optimization_and_old_wer_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, user, machine = (tmp_path / name for name in ("Windows", "Local", "ProgramData"))
    monkeypatch.setenv("WINDIR", str(windows))
    monkeypatch.setenv("LOCALAPPDATA", str(user))
    monkeypatch.setenv("PROGRAMDATA", str(machine))
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(cleaner, "is_admin", lambda: True)
    delivery = make_file(
        windows,
        r"ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows"
        r"\DeliveryOptimization\Cache\download.bin",
    )
    archive = make_file(user, r"Microsoft\Windows\WER\ReportArchive\old\Report.wer")
    queue = make_file(machine, r"Microsoft\Windows\WER\ReportQueue\old\Report.wer")
    old_temp = make_file(machine, r"Microsoft\Windows\WER\Temp\old.tmp")
    fresh_report = make_file(machine, r"Microsoft\Windows\WER\ReportQueue\new\Report.wer")
    other = make_file(machine, r"Microsoft\Windows\WER\settings.dat")
    old = time.time() - 2 * 24 * 3600
    for file in (delivery, archive, queue, old_temp):
        os.utime(file, (old, old))

    assert system_caches.estimate_system_caches() == 16
    outcome = system_caches.clean_system_caches(lambda _: None)

    assert (outcome.items, outcome.bytes_freed) == (4, 16)
    assert not any(file.exists() for file in (delivery, archive, queue, old_temp))
    assert fresh_report.exists() and other.exists()


def test_system_crash_dumps_are_left_alone_without_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINDIR", str(tmp_path / "windows"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "programdata"))
    monkeypatch.setattr(cleaner, "is_admin", lambda: False)
    dump = make_file(tmp_path, r"windows\MEMORY.DMP")
    app_dump = make_file(tmp_path, r"user\CrashDumps\app.dmp")
    old = time.time() - 2 * 3600  # o motor deixa em paz o que tem menos de 1 hora
    os.utime(app_dump, (old, old))

    outcome = temp_and_logs.clean_temp_and_logs(lambda _: None)

    assert outcome.admin_required
    assert dump.exists()
    assert not app_dump.exists()  # os despejos das aplicações não exigem administrador


def test_system_crash_dumps_are_estimated_and_removed_without_touching_other_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINDIR", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "programdata"))
    monkeypatch.setattr(cleaner, "is_admin", lambda: True)
    full = make_file(tmp_path, "MEMORY.DMP")
    mini = make_file(tmp_path, r"Minidump\crash.dmp")
    kernel = make_file(tmp_path, r"LiveKernelReports\WATCHDOG\crash.dmp")
    other = make_file(tmp_path, "unrelated.dmp")

    assert temp_and_logs.estimate_temp_and_logs() == 12
    outcome = temp_and_logs.clean_temp_and_logs(lambda _: None)

    assert (outcome.items, outcome.bytes_freed) == (3, 12)
    assert not any(file.exists() for file in (full, mini, kernel))
    assert other.exists()


def test_temporary_files_and_logs_are_cleaned_in_one_go_each_by_its_own_age(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINDIR", str(tmp_path / "windows"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "programdata"))
    monkeypatch.setattr(cleaner, "is_admin", lambda: True)
    old_temp = make_file(tmp_path, r"temp\old.tmp")
    fresh_temp = make_file(tmp_path, r"temp\fresh.tmp")
    day_old_log = make_file(tmp_path, r"windows\Logs\CBS\today.log")
    orchestrator = make_file(tmp_path, r"programdata\USOShared\Logs\System\old.etl")
    other_orchestrator_file = make_file(tmp_path, r"programdata\USOShared\Logs\System\keep.txt")
    old_log = make_file(tmp_path, r"windows\Logs\CBS\old.log")
    now = time.time()
    for file, age_hours in (
        (old_temp, 2),
        (day_old_log, 2),
        (old_log, 48),
        (orchestrator, 48),
        (other_orchestrator_file, 48),
    ):
        os.utime(file, (now - age_hours * 3600, now - age_hours * 3600))

    outcome = temp_and_logs.clean_temp_and_logs(lambda _: None)

    assert not old_temp.exists() and not old_log.exists()
    assert not orchestrator.exists()  # os .etl do Windows Update, com mais de 24 horas
    assert other_orchestrator_file.exists()  # só os .etl
    assert fresh_temp.exists()  # menos de 1 hora
    assert day_old_log.exists()  # menos de 24 horas: ainda serve para diagnosticar
    assert {row.label_key for row in outcome.rows if row.items} == {
        "category.user_temp",
        "category.windows_logs",
    }


def test_system_caches_also_clean_the_defender_and_font_caches_but_never_the_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, user, machine = (tmp_path / name for name in ("Windows", "Local", "ProgramData"))
    monkeypatch.setenv("WINDIR", str(windows))
    monkeypatch.setenv("LOCALAPPDATA", str(user))
    monkeypatch.setenv("PROGRAMDATA", str(machine))
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(cleaner, "is_admin", lambda: True)
    support = make_file(machine, r"Microsoft\Windows Defender\Support\MPLog.log")
    history = make_file(machine, r"Microsoft\Windows Defender\Scans\History\CacheManager\c.bin")
    fonts = make_file(windows, r"ServiceProfiles\LocalService\AppData\Local\FontCache\f.dat")
    quarantine = make_file(machine, r"Microsoft\Windows Defender\Quarantine\q.bin")
    old = time.time() - 2 * 3600
    for file in (support, history, fonts, quarantine):
        os.utime(file, (old, old))

    outcome = system_caches.clean_system_caches(lambda _: None)

    assert not any(file.exists() for file in (support, history, fonts))
    assert quarantine.exists()
    assert {row.label_key for row in outcome.rows if row.items} == {
        "category.defender_cache",
        "category.font_cache",
    }


def test_previous_windows_cleanup_runs_both_cleanups_and_adds_up_their_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leftovers = Outcome(2, 8, rows=(Row("category.leftovers", 2, 8),))
    old = Outcome(0, 100, rows=(Row("category.windows_old", None, 100),), failures=("old",))
    monkeypatch.setattr(previous_windows, "clean_install_leftovers", lambda _report: leftovers)
    monkeypatch.setattr(previous_windows, "clean_windows_old", lambda _report: old)

    outcome = previous_windows.clean_previous_windows(lambda _: None)

    assert (outcome.items, outcome.bytes_freed, outcome.failures) == (2, 108, ("old",))
    assert [row.label_key for row in outcome.rows] == ["category.windows_old", "category.leftovers"]


def test_previous_windows_cleanup_deletes_nothing_while_windows_setup_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = Outcome(0, 0, failures=("setup",), notice="cleanup.install_leftovers.setup_running")

    def windows_old_must_not_run(_report: Report) -> Outcome:
        raise AssertionError("o Windows.old não devia ser limpo com o Setup a decorrer")

    monkeypatch.setattr(previous_windows, "clean_install_leftovers", lambda _report: running)
    monkeypatch.setattr(previous_windows, "clean_windows_old", windows_old_must_not_run)

    assert previous_windows.clean_previous_windows(lambda _: None) is running


@pytest.mark.parametrize(
    ("old", "leftovers", "expected"), [(5, 3, 8), (None, 3, None), (5, None, None), (0, 0, 0)]
)
def test_previous_windows_estimate_adds_both_and_is_unknown_if_either_is(
    monkeypatch: pytest.MonkeyPatch, old: int | None, leftovers: int | None, expected: int | None
) -> None:
    monkeypatch.setattr(previous_windows, "estimate_windows_old", lambda: old)
    monkeypatch.setattr(previous_windows, "estimate_install_leftovers", lambda: leftovers)

    assert previous_windows.estimate_previous_windows() == expected


def test_old_setup_cleanup_only_deletes_the_two_named_system_drive_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(install_leftovers, "is_admin", lambda: True)
    monkeypatch.setattr(install_leftovers, "_setup_in_progress", lambda: False)
    monkeypatch.setattr(cleaner, "is_admin", lambda: True)
    upgrade = make_file(tmp_path, r"$WINDOWS.~BT\Sources\setup.exe")
    setup = make_file(tmp_path, r"$Windows.~WS\setup.exe")
    old_windows = make_file(tmp_path, r"Windows.old\sample.txt")
    prefix = make_file(tmp_path, r"$WINDOWS.~BT-keep\sample.txt")

    assert install_leftovers.estimate_install_leftovers() == 8
    outcome = install_leftovers.clean_install_leftovers(lambda _: None)

    assert (outcome.items, outcome.bytes_freed, outcome.failures) == (2, 8, ())
    assert not upgrade.parents[1].exists() and not setup.parent.exists()
    assert old_windows.exists() and prefix.exists()


@pytest.mark.parametrize("administrator", [False, True])
def test_old_setup_cleanup_leaves_files_if_setup_is_running_or_administrator_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, administrator: bool
) -> None:
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(install_leftovers, "is_admin", lambda: administrator)
    monkeypatch.setattr(install_leftovers, "_setup_in_progress", lambda: True)
    setup = make_file(tmp_path, r"$Windows.~WS\setup.exe")

    outcome = install_leftovers.clean_install_leftovers(lambda _: None)

    assert setup.exists()
    assert outcome.admin_required == (() if administrator else (str(setup.parent),))
    assert outcome.failures == ((str(setup.parent),) if administrator else ())


def test_recent_history_counts_shortcuts_jump_lists_and_run_commands_separately(
    tmp_path: Path, test_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(recent_history, "_RUN_MRU", test_key)
    monkeypatch.setattr(cleaner, "is_admin", lambda: False)
    recent = tmp_path / "Microsoft" / "Windows" / "Recent"
    shortcut = make_file(recent, "example.lnk")
    automatic = make_file(recent, r"AutomaticDestinations\example.automaticDestinations-ms")
    custom = make_file(recent, r"CustomDestinations\example.customDestinations-ms")
    pinned = make_file(recent, r"AutomaticDestinations\F01B4D95CF55D32A.automaticDestinations-ms")
    desktop_ini = make_file(recent, "desktop.ini")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, test_key) as key:
        winreg.SetValueEx(key, "a", 0, winreg.REG_SZ, "example-a")
        winreg.SetValueEx(key, "b", 0, winreg.REG_SZ, "example-b")
        winreg.SetValueEx(key, "MRUList", 0, winreg.REG_SZ, "ba")
        winreg.SetValueEx(key, "Unrelated", 0, winreg.REG_SZ, "kept")

        outcome = recent_history.clear_recent_history(lambda _: None)

        assert winreg.QueryInfoKey(key)[1] == 1
        assert winreg.QueryValueEx(key, "Unrelated")[0] == "kept"
    assert outcome.items == 4 and not outcome.failures
    assert [row.items for row in outcome.rows] == [1, 1, 2]
    assert not any(file.exists() for file in (shortcut, automatic))
    assert all(file.exists() for file in (custom, pinned, desktop_ini))
