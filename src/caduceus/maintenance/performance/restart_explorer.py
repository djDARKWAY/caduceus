"""
Fechar e reabrir o Explorer

Fecha a shell da sessão atual pelo comando «Sair do Explorer», para o Windows não a relançar
antes de a cache de ícones poder ser limpa. Volta a abrir o Explorer e espera pela barra de
tarefas. Usado pela limpeza da cache de ícones.
"""

import ctypes
import os
import time
from ctypes import wintypes

from caduceus.config import EXPLORER_EXE

_EXIT_EXPLORER = 0x05B4  # mensagem usada por «Sair do Explorer» na barra de tarefas
_SYNCHRONIZE = 0x00100000
_WAIT_SECONDS = 5

_user32 = ctypes.WinDLL("user32")
_find_window = _user32.FindWindowW
_find_window.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_find_window.restype = wintypes.HWND
_get_shell_window = _user32.GetShellWindow
_get_shell_window.restype = wintypes.HWND
_window_process = _user32.GetWindowThreadProcessId
_window_process.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_window_process.restype = wintypes.DWORD
_post_message = _user32.PostMessageW
_post_message.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_post_message.restype = wintypes.BOOL

_kernel32 = ctypes.WinDLL("kernel32")
_open_process = _kernel32.OpenProcess
_open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_open_process.restype = wintypes.HANDLE
_wait = _kernel32.WaitForSingleObject
_wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_wait.restype = wintypes.DWORD
_close_handle = _kernel32.CloseHandle
_close_handle.argtypes = [wintypes.HANDLE]


def stop_explorer() -> bool:
    """Devolve se a shell da sessão já fechou e deixou de manter ficheiros em uso."""
    tray = _find_window("Shell_TrayWnd", None)
    if not tray:
        return not _get_shell_window()
    pid = wintypes.DWORD()
    if not _window_process(tray, ctypes.byref(pid)):
        return False
    process = _open_process(_SYNCHRONIZE, False, pid.value)
    if not process:
        return False
    try:
        return bool(_post_message(tray, _EXIT_EXPLORER, 0, 0)) and (
            _wait(process, _WAIT_SECONDS * 1000) == 0
        )
    finally:
        _close_handle(process)


def start_explorer() -> bool:
    """Devolve se a barra de tarefas já está de volta, mesmo que o Windows a tenha relançado."""
    if _find_window("Shell_TrayWnd", None):
        return True
    if not _get_shell_window():
        executable = os.path.join(os.environ.get("WINDIR", ""), EXPLORER_EXE)
        if not os.path.isabs(executable):
            return False
        try:
            os.startfile(executable)
        except OSError:
            return False
    deadline = time.monotonic() + _WAIT_SECONDS
    while time.monotonic() < deadline:
        if _find_window("Shell_TrayWnd", None):
            return True
        time.sleep(0.1)
    return False
