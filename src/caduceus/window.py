"""
Janela

Fixa o tamanho da janela da consola e impede que se redimensione ou maximize. Só tem efeito na
consola clássica do Windows (conhost). O Windows Terminal não deixa os programas mudar a sua
janela, e nesse caso o Caduceus corre no tamanho que o terminal tiver.
"""

import ctypes
import os
from ctypes import wintypes

from caduceus.config import WINDOW_COLUMNS, WINDOW_LINES

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


def fix_console_size() -> None:
    os.system(f"mode con: cols={WINDOW_COLUMNS} lines={WINDOW_LINES} >nul")
    _lock_resizing()
