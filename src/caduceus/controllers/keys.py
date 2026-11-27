"""
Teclado

Lê uma tecla do terminal e traduz-a para as teclas de controlo do Caduceus, e descarta as que
ficaram à espera. Os algarismos de 1 a 9 são as teclas das colunas das tabelas.
"""

import msvcrt
from enum import Enum


class Key(Enum):
    UP = "up"
    DOWN = "down"
    ENTER = "enter"
    BACK = "back"
    QUIT = "quit"
    COLUMN_1 = "column_1"
    COLUMN_2 = "column_2"
    COLUMN_3 = "column_3"
    COLUMN_4 = "column_4"
    COLUMN_5 = "column_5"
    COLUMN_6 = "column_6"
    COLUMN_7 = "column_7"
    COLUMN_8 = "column_8"
    COLUMN_9 = "column_9"
    OTHER = "other"

    @property
    def column(self) -> int | None:
        """A coluna que a tecla escolhe (a contar do zero), ou None se não é uma tecla de coluna."""
        return _COLUMN_KEYS.get(self)


_COLUMN_KEYS = {Key[f"COLUMN_{number}"]: number - 1 for number in range(1, 10)}
_EXTENDED_KEYS = {"H": Key.UP, "P": Key.DOWN}
_CHAR_KEYS = {"\r": Key.ENTER, "\x08": Key.BACK, "\x03": Key.QUIT} | {
    str(number): Key[f"COLUMN_{number}"] for number in range(1, 10)
}


def discard_pending_keys() -> None:
    while msvcrt.kbhit():
        msvcrt.getwch()


def read_key() -> Key:
    char = msvcrt.getwch()
    if char in ("\x00", "\xe0"):
        return _EXTENDED_KEYS.get(msvcrt.getwch(), Key.OTHER)
    return _CHAR_KEYS.get(char, Key.OTHER)
