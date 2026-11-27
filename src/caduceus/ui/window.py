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
    """Verdadeiro só na consola clássica: nas outras (Windows Terminal) a janela não é do programa."""
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
