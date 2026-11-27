r"""
Programas instalados

Lista os programas instalados, tal como os Programas e Funcionalidades do Windows, e deixa
desinstalá-los. Os programas vêm das chaves `Uninstall` do registo (da máquina, em 64 e 32 bits, e
do utilizador). Ficam de fora os componentes do sistema, as atualizações e os programas que não se
podem desinstalar. Quem desinstala é o desinstalador do próprio programa: o Caduceus abre-o (o
Windows pede o UAC, se ele precisar de administrador), espera que feche e confirma no registo se o
programa saiu. Os programas MSI desinstalam-se com `msiexec /X`, porque o comando que registam
(`/I`) abre a reparação. Não se apagam restos no registo nem em pastas.

Quando o desinstalador já não existe e a pasta de instalação também não (o programa foi apagado à
mão), o programa não se pode desinstalar, e a sua entrada no registo é um resto. Nesse caso, em vez
de abrir o desinstalador, o Caduceus remove só essa entrada, depois de guardar uma cópia `.reg` dela
em `%LOCALAPPDATA%\Caduceus\removed-entries`. Só se deteta quando o comando aponta para um ficheiro
com caminho completo (o `msiexec` e os comandos sem caminho, como o `winget`, nunca contam como em
falta) e o programa regista a pasta onde se instalou, num disco local que está ligado.
"""

import ctypes
import os
import re
import winreg
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from caduceus.config import SETTINGS_FOLDER
from caduceus.maintenance.actions import Action, Outcome, Report, Row, Step
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.system_tool import free_bytes, run_system_tool

_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
_UNINSTALL_KEY_32 = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
_UNINSTALL_KEYS: tuple[tuple[int, str], ...] = (
    (winreg.HKEY_LOCAL_MACHINE, _UNINSTALL_KEY),
    (winreg.HKEY_LOCAL_MACHINE, _UNINSTALL_KEY_32),
    (winreg.HKEY_CURRENT_USER, _UNINSTALL_KEY),
)
_UPDATE_RELEASES = {"update", "hotfix", "security update"}
_MSI_PRODUCT = re.compile(r"\{[0-9A-F-]{36}\}", re.IGNORECASE)
_INSTALL_DATE = re.compile(r"(\d{4})(\d{2})(\d{2})")
_EXECUTABLE = re.compile(r"(.+?\.(?:exe|bat|cmd|com))(?=\s|$)", re.IGNORECASE)
_BYTES_PER_KB = 1024
_BACKUP_FOLDER = "removed-entries"
_HIVE_NAMES = {winreg.HKEY_LOCAL_MACHINE: "HKLM", winreg.HKEY_CURRENT_USER: "HKCU"}
_UNSAFE_FILE_NAME = re.compile(r"[^\w.-]+")
# Programas de que o Windows ou outros programas dependem: só se desinstalam com o Modo seguro OFF
_SYSTEM_SOFTWARE_WORDS = ("driver", "redistributable", "runtime", ".net", "chipset")

_SEE_MASK_NOCLOSEPROCESS = 0x40
_SEE_MASK_NOASYNC = 0x100
_SHOW_NORMAL = 1
_WAIT_TIMEOUT = 0x102
_WAIT_MILLISECONDS = 100
_ERROR_CANCELLED = 1223  # o utilizador recusou o pedido de administrador (UAC)


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_shell_execute = _shell32.ShellExecuteExW
_shell_execute.argtypes = [ctypes.POINTER(_ShellExecuteInfo)]
_shell_execute.restype = wintypes.BOOL
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_wait = _kernel32.WaitForSingleObject
_wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_wait.restype = wintypes.DWORD
_close_handle = _kernel32.CloseHandle
_close_handle.argtypes = [wintypes.HANDLE]
_close_handle.restype = wintypes.BOOL


@dataclass(frozen=True)
class InstalledProgram:
    name: str
    publisher: str
    version: str
    installed_on: str  # a data de instalação (AAAA-MM-DD), ou vazia se o programa não a regista
    size_bytes: int | None  # None se o programa não regista o tamanho
    uninstall_command: str
    hive: int
    key_path: str
    install_location: str = ""  # a pasta onde o programa se instalou, se o programa a regista

    @property
    def needs_safe_mode_off(self) -> bool:
        return any(word in self.name.lower() for word in _SYSTEM_SOFTWARE_WORDS)

    @property
    def entry_needs_admin(self) -> bool:
        """As entradas da máquina só se removem como administrador; as do utilizador, não."""
        return self.hive == winreg.HKEY_LOCAL_MACHINE

    @property
    def has_missing_uninstaller(self) -> bool:
        """O desinstalador não existe e a pasta de instalação também já não. Só o desinstalador em
        falta não chega (o programa pode lá estar, e o Python, por exemplo, não regista a pasta), e
        uma pasta num disco que não está ligado também não prova nada."""
        command = split_command(self.uninstall_command)
        if command is None or not os.path.isabs(command[0]) or os.path.isfile(command[0]):
            return False
        location = os.path.expandvars(self.install_location)
        drive = os.path.splitdrive(location)[0]
        is_local_drive = len(drive) == 2 and drive[1] == ":"  # os discos de rede podem demorar
        return is_local_drive and os.path.isdir(drive + "\\") and not os.path.exists(location)


def _values(hive: int, path: str) -> dict[str, object]:
    values: dict[str, object] = {}
    try:
        with winreg.OpenKey(hive, path) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                value_name, value, _kind = winreg.EnumValue(key, index)
                values[value_name] = value
    except OSError:
        return {}
    return values


def _installed_on(value: object) -> str:
    match = _INSTALL_DATE.fullmatch(str(value).strip())
    return "-".join(match.groups()) if match else ""


def _uninstall_command(values: dict[str, object], key_name: str) -> str:
    if values.get("WindowsInstaller") == 1 and _MSI_PRODUCT.fullmatch(key_name):
        return f"MsiExec.exe /X{key_name}"
    return str(values.get("UninstallString", "")).strip()


def _program(hive: int, root: str, key_name: str) -> InstalledProgram | None:
    path = rf"{root}\{key_name}"
    values = _values(hive, path)
    name = str(values.get("DisplayName", "")).strip()
    command = _uninstall_command(values, key_name)
    is_update = (
        "ParentKeyName" in values or str(values.get("ReleaseType", "")).lower() in _UPDATE_RELEASES
    )
    hidden = values.get("SystemComponent") == 1 or values.get("NoRemove") == 1
    if not name or not command or is_update or hidden:
        return None
    size = values.get("EstimatedSize")
    return InstalledProgram(
        name=name,
        publisher=str(values.get("Publisher", "")).strip(),
        version=str(values.get("DisplayVersion", "")).strip(),
        installed_on=_installed_on(values.get("InstallDate", "")),
        size_bytes=size * _BYTES_PER_KB if isinstance(size, int) and size > 0 else None,
        uninstall_command=command,
        hive=hive,
        key_path=path,
        install_location=str(values.get("InstallLocation", "")).strip().strip('"'),
    )


def _programs_in(hive: int, root: str) -> list[InstalledProgram]:
    try:
        with winreg.OpenKey(hive, root) as key:
            names = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return []  # a chave não existe, ou não se pode ler: não há programas deste tipo
    found = (_program(hive, root, name) for name in names)
    return [program for program in found if program is not None]


def list_installed_programs() -> list[InstalledProgram]:
    """Os programas instalados, ordenados pelo nome, de A a Z, sem repetidos entre 32 e 64 bits."""
    unique: dict[tuple[str, str], InstalledProgram] = {}
    for hive, root in _UNINSTALL_KEYS:
        for program in _programs_in(hive, root):
            unique.setdefault((program.name.casefold(), program.version), program)
    return sorted(unique.values(), key=lambda program: program.name.casefold())


def is_installed(program: InstalledProgram) -> bool:
    try:
        with winreg.OpenKey(program.hive, program.key_path):
            return True
    except OSError:
        return False


def split_command(command: str) -> tuple[str, str] | None:
    """O executável e os argumentos de um comando de desinstalação, ou None se não há executável."""
    command = os.path.expandvars(command.strip())
    if command.startswith('"'):
        executable, _quote, arguments = command[1:].partition('"')
    elif match := _EXECUTABLE.match(command):
        executable, arguments = match.group(1), command[match.end() :]
    else:
        # Sem extensão (por exemplo, `winget uninstall ...`): o Windows procura-o no PATH
        executable, _space, arguments = command.partition(" ")
    return (executable, arguments.strip()) if executable else None


def _run_uninstaller(executable: str, arguments: str, report: Report, step: Step) -> int:
    """Abre o desinstalador e espera que feche; devolve 0, ou o erro do Windows se não abriu."""
    info = _ShellExecuteInfo(
        cbSize=ctypes.sizeof(_ShellExecuteInfo),
        fMask=_SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_NOASYNC,
        lpVerb="open",
        lpFile=executable,
        lpParameters=arguments or None,
        nShow=_SHOW_NORMAL,
    )
    # O ShellExecuteEx (ao contrário do CreateProcess) pede o UAC aos desinstaladores que o exigem
    if not _shell_execute(ctypes.byref(info)):
        return ctypes.get_last_error()
    if not info.hProcess:
        return 0  # o Windows entregou o comando a um processo que já corria: não há o que esperar
    try:
        while _wait(info.hProcess, _WAIT_MILLISECONDS) == _WAIT_TIMEOUT:
            report(step)
    finally:
        _close_handle(info.hProcess)
    return 0


def uninstall_program(program: InstalledProgram) -> Action:
    """A ação que abre o desinstalador do programa e, quando ele fecha, diz se o programa saiu."""

    def uninstall(report: Report) -> Outcome:
        command = split_command(program.uninstall_command)
        if command is None:
            return Outcome(0, 0, notice="notice.uninstaller_not_opened")
        free_before = free_bytes()
        step = Step("apps.uninstall.step", 0, 0, {"name": program.name})
        report(step)
        error = _run_uninstaller(*command, report, step)
        if error == _ERROR_CANCELLED:
            return Outcome(0, 0, notice="notice.uninstall_cancelled")
        if error:
            return Outcome(0, 0, notice="notice.uninstaller_not_opened")
        if is_installed(program):
            return Outcome(0, 0, notice="notice.program_still_installed")
        freed = max(0, free_bytes() - free_before)
        row = Row("category.uninstalled_program", 1, freed, {"name": program.name})
        return Outcome(1, freed, rows=(row,))

    return uninstall


def _backup_file(program: InstalledProgram) -> Path:
    key_name = program.key_path.rsplit("\\", 1)[-1]
    folder = Path(os.path.expandvars("%LOCALAPPDATA%")) / SETTINGS_FOLDER / _BACKUP_FOLDER
    return folder / f"{_UNSAFE_FILE_NAME.sub('_', key_name)}.reg"


def _save_entry_backup(program: InstalledProgram, report: Report) -> bool:
    file = _backup_file(program)
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        key = f"{_HIVE_NAMES[program.hive]}\\{program.key_path}"
        return run_system_tool(
            "reg.exe", ["export", key, str(file), "/y"], report, "apps.uninstall.backup.step"
        )
    except OSError:
        return False


def remove_leftover_entry(program: InstalledProgram) -> Action:
    """A ação que remove a entrada de um programa cujo desinstalador já não existe, depois de
    guardar uma cópia dela. Não apaga ficheiros."""

    def remove(report: Report) -> Outcome:
        if program.entry_needs_admin and not is_admin():
            return Outcome(0, 0, admin_required=(program.name,))
        if not _save_entry_backup(program, report):
            return Outcome(0, 0, failures=(program.name,))
        try:
            winreg.DeleteKey(program.hive, program.key_path)
        except OSError:
            return Outcome(0, 0, failures=(program.name,))
        row = Row(
            "category.removed_entry",
            1,
            0,
            {"name": program.name},
            needs_admin=program.entry_needs_admin,
        )
        return Outcome(1, 0, rows=(row,))

    return remove
