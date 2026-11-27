"""
Teclado

Lê uma tecla do terminal e traduz-a para as teclas de controlo do Caduceus, e descarta as que
ficaram à espera.
"""

import msvcrt
from enum import Enum


class Key(Enum):
    UP = "up"
    DOWN = "down"
    ENTER = "enter"
    BACK = "back"
    QUIT = "quit"
    OTHER = "other"


_EXTENDED_KEYS = {"H": Key.UP, "P": Key.DOWN}
_CHAR_KEYS = {"\r": Key.ENTER, "\x08": Key.BACK, "q": Key.QUIT, "Q": Key.QUIT, "\x03": Key.QUIT}


def discard_pending_keys() -> None:
    while msvcrt.kbhit():
        msvcrt.getwch()


def read_key() -> Key:
    char = msvcrt.getwch()
    if char in ("\x00", "\xe0"):
        return _EXTENDED_KEYS.get(msvcrt.getwch(), Key.OTHER)
    return _CHAR_KEYS.get(char, Key.OTHER)
