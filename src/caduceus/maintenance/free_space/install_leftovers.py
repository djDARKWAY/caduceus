r"""
Apagar os restos da instalação do Windows

Apaga `$WINDOWS.~BT` e `$Windows.~WS` na raiz do disco do sistema. Limita a limpeza a essas
pastas, porque o Limpeza de Disco pode abranger outras unidades ou outras instalações. Confirma
no fim se ainda restam ficheiros, tal como a limpeza do Windows.old.
"""

import stat
import winreg
from dataclasses import replace
from pathlib import Path

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations
from caduceus.maintenance.system_tool import system_drive

_NAMES = ("$WINDOWS.~BT", "$Windows.~WS")


def _existing_folders() -> tuple[Path, ...]:
    root = Path(system_drive() + "\\")
    if not root.is_absolute():
        return ()
    folders: list[Path] = []
    for name in _NAMES:
        folder = root / name
        try:
            info = folder.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            folders.append(folder)  # pode existir ainda que não se consiga ler
        else:
            if stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                folders.append(folder)
    return tuple(folders)


def _locations(folders: tuple[Path, ...]) -> tuple[Location, ...]:
    return tuple(
        Location(
            str(folder.parent),
            "cleanup.install_leftovers.result",
            pattern=folder.name,
            min_age_hours=0,
            needs_admin=True,
        )
        for folder in folders
    )


def _setup_in_progress() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\Setup") as key:
            return bool(winreg.QueryValueEx(key, "SystemSetupInProgress")[0])
    except FileNotFoundError:
        return False


def estimate_install_leftovers() -> int | None:
    folders = _existing_folders()
    if not folders:
        return 0
    return estimate_locations(_locations(folders)) if is_admin() else None


def clean_install_leftovers(report: Report) -> Outcome:
    folders = _existing_folders()
    if not folders:
        return Outcome(0, 0)
    paths = tuple(map(str, folders))
    if not is_admin():
        return Outcome(0, 0, admin_required=paths)
    try:
        if _setup_in_progress():
            return Outcome(0, 0, failures=paths, notice="cleanup.install_leftovers.setup_running")
    except OSError:
        return Outcome(0, 0, failures=paths)
    outcome = clean_locations(_locations(folders), report)
    failures = tuple(dict.fromkeys((*outcome.failures, *map(str, _existing_folders()))))
    return replace(outcome, failures=failures)
