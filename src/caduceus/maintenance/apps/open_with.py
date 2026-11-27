r"""
Menu «Abrir com»

Tira do menu «Abrir com» as aplicações que já não existem. Uma aplicação é órfã quando está
registada em `HKCU\Software\Classes\Applications` e o comando que regista aponta para um ficheiro
que já não está lá (e nenhum registo da máquina para o mesmo nome aponta para um que esteja). Para
cada uma, o Caduceus tira o nome das listas `OpenWithList` de todas as extensões (e das letras do
`MRUList`) e remove a chave dela. Antes guarda uma cópia `.reg` do que vai mexer em
`%LOCALAPPDATA%\Caduceus\removed-entries`. Só mexe no registo do utilizador, por isso não exige
administrador.
"""

import os
import re
import winreg
from pathlib import Path

from caduceus.config import SETTINGS_FOLDER
from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.apps.installed_programs import split_command
from caduceus.maintenance.system_tool import run_system_tool

_APPLICATIONS_KEY = r"Software\Classes\Applications"
_MACHINE_APPLICATIONS_KEY = r"SOFTWARE\Classes\Applications"
_FILE_EXTS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
_BACKUP_FOLDER = "removed-entries"
_MRU_LIST = "MRUList"
_UNSAFE_FILE_NAME = re.compile(r"[^\w.-]+")


def _command_target(hive: int, root: str, executable: str) -> str | None:
    """O ficheiro que o comando «abrir» registado para `executable` executa, ou None se não há."""
    try:
        with winreg.OpenKey(hive, rf"{root}\{executable}\shell\open\command") as key:
            command = str(winreg.QueryValueEx(key, "")[0])
    except OSError:
        return None
    split = split_command(command)
    return split[0] if split and os.path.isabs(split[0]) else None


def _names_registered(hive: int, root: str) -> list[str]:
    try:
        with winreg.OpenKey(hive, root) as key:
            return [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return []


def orphan_applications() -> list[str]:
    """Os nomes (por exemplo, `old.exe`) das aplicações registadas pelo utilizador que já não
    existem."""
    orphans = []
    for name in _names_registered(winreg.HKEY_CURRENT_USER, _APPLICATIONS_KEY):
        targets = [
            _command_target(winreg.HKEY_CURRENT_USER, _APPLICATIONS_KEY, name),
            _command_target(winreg.HKEY_LOCAL_MACHINE, _MACHINE_APPLICATIONS_KEY, name),
        ]
        registered = [target for target in targets if target is not None]
        if registered and not any(os.path.isfile(target) for target in registered):
            orphans.append(name)
    return sorted(orphans, key=str.casefold)


def mru_without(mru: str, removed_letters: set[str]) -> str:
    """O `MRUList` sem as letras das entradas removidas."""
    return "".join(letter for letter in mru if letter not in removed_letters)


def _clean_open_with_list(extension: str, orphans: set[str]) -> bool:
    """Tira as aplicações órfãs da lista da extensão; devolve se a lista ficou como devia."""
    path = rf"{_FILE_EXTS_KEY}\{extension}\OpenWithList"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
            values = {}
            for index in range(winreg.QueryInfoKey(key)[1]):
                name, value, _kind = winreg.EnumValue(key, index)
                values[name] = value
            removed = {
                name
                for name, value in values.items()
                if name != _MRU_LIST and str(value).casefold() in orphans
            }
            for name in removed:
                winreg.DeleteValue(key, name)
            if removed and isinstance(values.get(_MRU_LIST), str):
                mru = mru_without(values[_MRU_LIST], removed)
                winreg.SetValueEx(key, _MRU_LIST, 0, winreg.REG_SZ, mru)
    except FileNotFoundError:
        return True  # a extensão não tem lista: não há o que tirar
    except OSError:
        return False
    return True


def _backup_file(name: str) -> Path:
    folder = Path(os.path.expandvars("%LOCALAPPDATA%")) / SETTINGS_FOLDER / _BACKUP_FOLDER
    return folder / f"open-with-{_UNSAFE_FILE_NAME.sub('_', name)}.reg"


def _export(key: str, file: Path, report: Report) -> bool:
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        return run_system_tool(
            "reg.exe", ["export", key, str(file), "/y"], report, "apps.open_with.step"
        )
    except OSError:
        return False


def clean_open_with(report: Report) -> Outcome:
    """A ação que tira do menu «Abrir com» as aplicações que já não existem."""
    orphans = orphan_applications()
    if not orphans:
        return Outcome(0, 0, notice="notice.open_with_clean")
    if not _export(rf"HKCU\{_FILE_EXTS_KEY}", _backup_file("fileexts"), report):
        return Outcome(0, 0, failures=tuple(orphans))
    folded = {name.casefold() for name in orphans}
    removed: list[str] = []
    failures: list[str] = [
        f"{extension} (OpenWithList)"
        for extension in _names_registered(winreg.HKEY_CURRENT_USER, _FILE_EXTS_KEY)
        if not _clean_open_with_list(extension, folded)
    ]
    for name in orphans:
        key = rf"HKCU\{_APPLICATIONS_KEY}\{name}"
        done = _export(key, _backup_file(name), report) and run_system_tool(
            "reg.exe", ["delete", key, "/f"], report, "apps.open_with.step"
        )
        (removed if done else failures).append(name)
    rows = (Row("category.open_with_entries", len(removed), 0),) if removed else ()
    return Outcome(len(removed), 0, failures=tuple(failures), rows=rows)
