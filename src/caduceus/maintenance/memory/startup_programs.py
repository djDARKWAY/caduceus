r"""
Programas de arranque

Lista os programas que arrancam com o Windows e deixa ligá-los e desligá-los, tal como o Gestor de
Tarefas. Os programas vêm das chaves `Run` do registo (do utilizador e da máquina, em 64 e 32 bits)
e das pastas Arranque (do utilizador e de todos os utilizadores). Desligar não apaga nada: grava a
decisão em `Explorer\StartupApproved`, o sítio que o próprio Windows consulta, por isso o programa
continua instalado e pode ser ligado outra vez. Os programas da máquina exigem administrador.

Vêm também os serviços de terceiros com arranque automático (por exemplo, o do FortiClient), que
o Gestor de Tarefas não mostra no separador Arranque. Desligar um serviço passa-o a arranque
manual (`Start` = 3), nunca a desativado, e deixa uma marca no próprio serviço para o programa
ainda o listar e o poder ligar outra vez. Os serviços da Microsoft e os do Windows ficam de fora.

O impacto é estimado pela memória que o programa está a usar agora (o Gestor de Tarefas mede o
tempo de arranque, que não se consegue ler de forma fiável), por isso só se conhece para os
programas que estão em execução.
"""

import os
import re
import time
import winreg
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from caduceus.config import STARTUP_HIGH_IMPACT_MB, STARTUP_MEDIUM_IMPACT_MB
from caduceus.maintenance.actions import Action, Outcome, Report
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.memory.executable_info import describe
from caduceus.maintenance.memory.process_memory import memory_by_executable

_BYTES_PER_MB = 1024 * 1024
_SERVICES_HIVE = winreg.HKEY_LOCAL_MACHINE
_SERVICES_KEY = r"SYSTEM\CurrentControlSet\Services"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_KEY_32 = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
_USER_FOLDER = r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
_MACHINE_FOLDER = r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
# O formato que o Windows grava: quatro bytes com o estado (par = ligado, ímpar = desligado) e a
# data em que se desligou, em 8 bytes (FILETIME)
_ENABLED = b"\x02\x00\x00\x00" + bytes(8)
_DISABLED_MARK = b"\x03\x00\x00\x00"
_SERVICE_AUTOMATIC = 2
UPDATER_WORDS = ("update", "updater")
_SERVICE_MANUAL = 3
_SERVICE_PROCESS_TYPES = 0x10 | 0x20  # serviços que correm num processo (os restantes são drivers)
_SERVICE_MARK = "CaduceusDisabledStartup"
_WINDOWS_EPOCH_SECONDS = 11644473600
_FILETIME_TICKS_PER_SECOND = 10_000_000
_EXECUTABLE = re.compile(r"(.+?\.(?:exe|bat|cmd|com))(?=\s|$)", re.IGNORECASE)
_SQUIRREL_UPDATER = (
    "update.exe"  # Discord, Slack e outros arrancam por ele, e correm a partir de app-*
)


class StartupSource(Enum):
    RUN_USER = "run_user"
    RUN_MACHINE = "run_machine"
    RUN_MACHINE_32 = "run_machine_32"
    FOLDER_USER = "folder_user"
    FOLDER_MACHINE = "folder_machine"
    SERVICE = "service"


_MACHINE_SOURCES = {
    StartupSource.RUN_MACHINE,
    StartupSource.RUN_MACHINE_32,
    StartupSource.FOLDER_MACHINE,
    StartupSource.SERVICE,
}
# Onde cada fonte guarda a decisão de ligado/desligado: a chave raiz e o nome da subchave
_APPROVED: dict[StartupSource, tuple[int, str]] = {
    StartupSource.RUN_USER: (winreg.HKEY_CURRENT_USER, _APPROVED_KEY + r"\Run"),
    StartupSource.RUN_MACHINE: (winreg.HKEY_LOCAL_MACHINE, _APPROVED_KEY + r"\Run"),
    StartupSource.RUN_MACHINE_32: (winreg.HKEY_LOCAL_MACHINE, _APPROVED_KEY + r"\Run32"),
    StartupSource.FOLDER_USER: (winreg.HKEY_CURRENT_USER, _APPROVED_KEY + r"\StartupFolder"),
    StartupSource.FOLDER_MACHINE: (winreg.HKEY_LOCAL_MACHINE, _APPROVED_KEY + r"\StartupFolder"),
}
_RUN_KEYS: tuple[tuple[StartupSource, int, str], ...] = (
    (StartupSource.RUN_USER, winreg.HKEY_CURRENT_USER, _RUN_KEY),
    (StartupSource.RUN_MACHINE, winreg.HKEY_LOCAL_MACHINE, _RUN_KEY),
    (StartupSource.RUN_MACHINE_32, winreg.HKEY_LOCAL_MACHINE, _RUN_KEY_32),
)
_FOLDERS = (
    (StartupSource.FOLDER_USER, _USER_FOLDER),
    (StartupSource.FOLDER_MACHINE, _MACHINE_FOLDER),
)


@dataclass(frozen=True)
class StartupEntry:
    name: str  # o nome com que o Windows regista a decisão (o valor do registo ou o ficheiro)
    label: str
    command: str
    source: StartupSource
    memory_bytes: int | None  # None se o programa não está em execução

    @property
    def needs_admin(self) -> bool:
        return self.source in _MACHINE_SOURCES

    @property
    def needs_safe_mode_off(self) -> bool:
        """Os serviços exigem o Modo seguro desligado, exceto os de atualização, que se podem
        passar a manual sem risco: os de segurança, VPN, drivers e bases de dados, não."""
        is_updater = any(word in f"{self.label} {self.name}".lower() for word in UPDATER_WORDS)
        return self.source is StartupSource.SERVICE and not is_updater


def executable_of(command: str) -> str | None:
    """O caminho do executável de uma linha de comandos de arranque, ou None se não houver."""
    command = os.path.expandvars(command.strip())
    if command.startswith('"'):
        path = command[1:].split('"', 1)[0]
    else:
        match = _EXECUTABLE.match(command)
        if match is None:
            return None
        path = match.group(1)
    return os.path.normcase(path) if path else None


def memory_of(command: str, running: dict[str, int]) -> int | None:
    """A memória em uso pelo programa de uma linha de comandos de arranque, se estiver a correr."""
    executable = executable_of(command)
    if executable is None:
        return None
    if executable in running:
        return running[executable]
    if os.path.basename(executable) != _SQUIRREL_UPDATER:
        return None
    install_folder = os.path.dirname(executable) + os.sep
    inside = [size for path, size in running.items() if path.startswith(install_folder)]
    return sum(inside) if inside else None


def impact_of(memory_bytes: int | None) -> str | None:
    """`low`, `medium` ou `high`, conforme a memória em uso, ou None se não se conhece."""
    if memory_bytes is None:
        return None
    if memory_bytes >= STARTUP_HIGH_IMPACT_MB * _BYTES_PER_MB:
        return "high"
    if memory_bytes >= STARTUP_MEDIUM_IMPACT_MB * _BYTES_PER_MB:
        return "medium"
    return "low"


def _readable_label(command: str, fallback: str) -> str:
    """O nome legível do programa do comando, ou o nome técnico se o ficheiro não o traz."""
    executable = executable_of(command)
    if executable is None or os.path.basename(executable) == _SQUIRREL_UPDATER:
        return fallback  # o Update.exe chama-se «Update» em todos os programas que o usam
    return describe(executable).name or fallback if os.path.isfile(executable) else fallback


def _service_values(name: str) -> dict[str, object]:
    values: dict[str, object] = {}
    try:
        with winreg.OpenKey(_SERVICES_HIVE, rf"{_SERVICES_KEY}\{name}") as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                value_name, value, _kind = winreg.EnumValue(key, index)
                values[value_name] = value
    except OSError:
        return {}
    return values


def _service_entry(name: str, running: dict[str, int]) -> StartupEntry | None:
    values = _service_values(name)
    start, kind = values.get("Start"), values.get("Type")
    if not isinstance(kind, int) or not kind & _SERVICE_PROCESS_TYPES:
        return None
    if start != _SERVICE_AUTOMATIC and _SERVICE_MARK not in values:
        return None
    command = str(values.get("ImagePath", ""))
    executable = executable_of(command)
    windows_folder = os.path.normcase(os.path.expandvars("%WINDIR%")) + os.sep
    if (
        executable is None
        or executable.startswith(windows_folder)
        or not os.path.isfile(executable)
    ):
        return None  # os serviços do Windows (e os que se alojam no svchost) não se tocam
    info = describe(executable)
    if info.from_microsoft:
        return None
    display = str(values.get("DisplayName", ""))
    label = display if display and not display.startswith("@") else info.name or name
    return StartupEntry(name, label, command, StartupSource.SERVICE, memory_of(command, running))


def _service_entries(running: dict[str, int]) -> list[StartupEntry]:
    try:
        with winreg.OpenKey(_SERVICES_HIVE, _SERVICES_KEY) as services:
            names = [winreg.EnumKey(services, i) for i in range(winreg.QueryInfoKey(services)[0])]
    except OSError:
        return []
    found = (_service_entry(name, running) for name in names)
    return [entry for entry in found if entry is not None]


def _run_entries(running: dict[str, int]) -> list[StartupEntry]:
    entries: list[StartupEntry] = []
    for source, hive, path in _RUN_KEYS:
        try:
            with winreg.OpenKey(hive, path) as key:
                for index in range(winreg.QueryInfoKey(key)[1]):
                    name, value, _kind = winreg.EnumValue(key, index)
                    command = str(value)
                    label = _readable_label(command, name)
                    entries.append(
                        StartupEntry(name, label, command, source, memory_of(command, running))
                    )
        except OSError:
            continue  # a chave não existe, ou não se pode ler: não há programas deste tipo
    return entries


def _folder_entries(running: dict[str, int]) -> list[StartupEntry]:
    entries: list[StartupEntry] = []
    for source, folder in _FOLDERS:
        try:
            files = sorted(Path(os.path.expandvars(folder)).iterdir())
        except OSError:
            continue
        for file in files:
            if file.is_file() and file.name.lower() != "desktop.ini":
                command = str(file)
                label = _readable_label(command, file.stem)
                entries.append(
                    StartupEntry(file.name, label, command, source, memory_of(command, running))
                )
    return entries


def list_startup_entries() -> list[StartupEntry]:
    """Os programas de arranque, ordenados pelo nome, de A a Z."""
    running = memory_by_executable()
    entries = _run_entries(running) + _folder_entries(running) + _service_entries(running)
    return sorted(entries, key=lambda entry: entry.label.casefold())


def parse_enabled(data: bytes) -> bool:
    return not data or data[0] % 2 == 0


def _service_key_path(entry: StartupEntry) -> str:
    return rf"{_SERVICES_KEY}\{entry.name}"


def is_enabled(entry: StartupEntry) -> bool:
    if entry.source is StartupSource.SERVICE:
        try:
            with winreg.OpenKey(_SERVICES_HIVE, _service_key_path(entry)) as key:
                return bool(winreg.QueryValueEx(key, "Start")[0] == _SERVICE_AUTOMATIC)
        except OSError:
            return False
    hive, path = _APPROVED[entry.source]
    try:
        with winreg.OpenKey(hive, path) as key:
            data, _kind = winreg.QueryValueEx(key, entry.name)
    except OSError:
        return True  # sem decisão gravada, o Windows arranca o programa
    return parse_enabled(bytes(data))


def _disabled_value(now_seconds: float) -> bytes:
    ticks = int((now_seconds + _WINDOWS_EPOCH_SECONDS) * _FILETIME_TICKS_PER_SECOND)
    return _DISABLED_MARK + ticks.to_bytes(8, "little")


def _set_service_enabled(entry: StartupEntry, enabled: bool) -> None:
    path = _service_key_path(entry)
    with winreg.OpenKey(_SERVICES_HIVE, path, 0, winreg.KEY_SET_VALUE) as key:
        start = _SERVICE_AUTOMATIC if enabled else _SERVICE_MANUAL
        winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, start)
        if enabled:
            try:
                winreg.DeleteValue(key, _SERVICE_MARK)
            except FileNotFoundError:
                pass  # o serviço nunca foi desligado por aqui
        else:
            winreg.SetValueEx(key, _SERVICE_MARK, 0, winreg.REG_DWORD, 1)


def set_enabled(entry: StartupEntry, enabled: bool, now_seconds: float) -> None:
    if entry.source is StartupSource.SERVICE:
        _set_service_enabled(entry, enabled)
        return
    hive, path = _APPROVED[entry.source]
    value = _ENABLED if enabled else _disabled_value(now_seconds)
    with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, entry.name, 0, winreg.REG_BINARY, value)


def toggle_startup(entry: StartupEntry) -> Action:
    """A ação que liga o programa se estiver desligado e o desliga se estiver ligado."""

    def toggle(_report: Report) -> Outcome:
        if entry.needs_admin and not is_admin():
            return Outcome(0, 0, admin_required=(entry.label,))
        try:
            set_enabled(entry, not is_enabled(entry), time.time())
        except OSError:
            return Outcome(0, 0, failures=(entry.label,))
        return Outcome(0, 0)

    return toggle
