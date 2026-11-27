"""
Janela

Fixa o tamanho da janela da consola e impede que se redimensione ou maximize. Só tem efeito na
consola clássica do Windows (conhost). No Windows Terminal não se mexe em nada: ele não deixa os
programas mudar a sua janela, e o comando `mode` só lhe muda o tamanho que o programa julga ter,
por isso o ecrã seria desenhado mais largo do que a janela e quebrava. Aí o Caduceus corre no
tamanho que o terminal tiver, e o ecrã adapta-se a ele.
"""

import ctypes
import os
import subprocess
from ctypes import wintypes

from caduceus.config import WINDOW_COLUMNS, WINDOW_LINES

_MODE_COMMAND = r"%WINDIR%\System32\mode.com"
_WINDOWS_TERMINAL_VARIABLE = "WT_SESSION"
_CLASSIC_CONSOLE_CLASS = "ConsoleWindowClass"  # o Windows Terminal usa a PseudoConsoleWindow
_CLASS_NAME_CHARS = 64
_GWL_STYLE = -16
_WS_THICKFRAME = 0x00040000
_WS_MAXIMIZEBOX = 0x00010000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020


def _lock_resizing() -> None:
    window = ctypes.windll.kernel32.GetConsoleWindow()
    if not window:
        return
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, *[ctypes.c_int] * 5]
    style = user32.GetWindowLongW(window, _GWL_STYLE)
    user32.SetWindowLongW(window, _GWL_STYLE, style & ~(_WS_THICKFRAME | _WS_MAXIMIZEBOX))
    user32.SetWindowPos(
        window, None, 0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_FRAMECHANGED
    )


def _is_classic_console() -> bool:
    """Verdadeiro só na consola clássica: noutras (Windows Terminal) a janela não é do programa."""
    window = ctypes.windll.kernel32.GetConsoleWindow()
    if not window:
        return False
    name = ctypes.create_unicode_buffer(_CLASS_NAME_CHARS)
    ctypes.windll.user32.GetClassNameW(window, name, _CLASS_NAME_CHARS)
    return name.value == _CLASSIC_CONSOLE_CLASS


def fix_console_size() -> None:
    if _WINDOWS_TERMINAL_VARIABLE in os.environ or not _is_classic_console():
        return
    subprocess.run(
        [
            os.path.expandvars(_MODE_COMMAND),
            "con:",
            f"cols={WINDOW_COLUMNS}",
            f"lines={WINDOW_LINES}",
        ],
        stdout=subprocess.DEVNULL,
        check=False,
    )
    _lock_resizing()


_SHELLS = {"cmd.exe", "powershell.exe", "pwsh.exe"}
_TH32CS_SNAPPROCESS = 0x2
_PROCESS_TERMINATE = 0x1
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _ProcessEntry(ctypes.Structure):
    _fields_ = (
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("process_id", wintypes.DWORD),
        ("default_heap_id", ctypes.c_size_t),
        ("module_id", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent_process_id", wintypes.DWORD),
        ("priority", ctypes.c_long),
        ("flags", wintypes.DWORD),
        ("exe_file", ctypes.c_wchar * 260),
    )


def _running_processes() -> list[tuple[int, int, str]]:
    """Os processos em execução, como (identificador, identificador do pai, nome do executável)."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snapshot == _INVALID_HANDLE:
        return []
    processes: list[tuple[int, int, str]] = []
    entry = _ProcessEntry(size=ctypes.sizeof(_ProcessEntry))
    found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while found:
        processes.append((entry.process_id, entry.parent_process_id, entry.exe_file.lower()))
        found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    kernel32.CloseHandle(snapshot)
    return processes


def launching_shell(processes: list[tuple[int, int, str]], own_id: int) -> int | None:
    """O identificador do shell (cmd, PowerShell) que lançou este processo, ou None se foi outro."""
    names = {process_id: name for process_id, _parent, name in processes}
    parents = {process_id: parent for process_id, parent, _name in processes}
    parent = parents.get(own_id)
    if parent is not None and names.get(parent) in _SHELLS:
        return parent
    return None


def close_launching_shell() -> None:
    """Termina o shell que lançou o Caduceus, o que fecha a consola onde ele corria. Só se for
    mesmo um shell: se o Caduceus foi lançado por outro programa, não se mexe em nada."""
    shell = launching_shell(_running_processes(), os.getpid())
    if shell is None:
        return
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(_PROCESS_TERMINATE, False, shell)
    if handle:
        kernel32.TerminateProcess(handle, 0)  # saída com êxito: o Terminal fecha o separador
        kernel32.CloseHandle(handle)
