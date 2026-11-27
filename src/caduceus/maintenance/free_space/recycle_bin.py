"""
Esvaziar a reciclagem

Apaga, em definitivo, o conteúdo da reciclagem de todas as unidades fixas (C:\\, D:\\, ...), uma
a uma, e indica quantos elementos e que espaço libertou. Usa a API de reciclagem do Windows.
"""

import ctypes
import string
from ctypes import wintypes

from caduceus.maintenance.actions import Outcome, Report, Row, Step

_DRIVE_FIXED = 3
_NO_CONFIRMATION_NO_PROGRESS_NO_SOUND = 0x1 | 0x2 | 0x4


class _BinInfo(ctypes.Structure):
    _fields_ = (
        ("size_of_struct", wintypes.DWORD),
        ("size", ctypes.c_int64),
        ("items", ctypes.c_int64),
    )


_shell32 = ctypes.WinDLL("shell32")
_query_bin = _shell32.SHQueryRecycleBinW
_query_bin.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_BinInfo)]
_query_bin.restype = ctypes.HRESULT
_empty_bin = _shell32.SHEmptyRecycleBinW
_empty_bin.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
_empty_bin.restype = ctypes.HRESULT


def _fixed_drives() -> list[str]:
    kernel32 = ctypes.windll.kernel32
    mask = kernel32.GetLogicalDrives()
    roots = [
        f"{letter}:\\" for index, letter in enumerate(string.ascii_uppercase) if mask >> index & 1
    ]
    return [root for root in roots if kernel32.GetDriveTypeW(root) == _DRIVE_FIXED]


def _query(drive: str) -> tuple[int, int]:
    info = _BinInfo(size_of_struct=ctypes.sizeof(_BinInfo))
    _query_bin(drive, ctypes.byref(info))
    return info.items, info.size


def _empty(drive: str) -> None:
    _empty_bin(None, drive, _NO_CONFIRMATION_NO_PROGRESS_NO_SOUND)


def estimate_recycle_bin() -> int:
    total = 0
    for drive in _fixed_drives():
        try:
            total += _query(drive)[1]
        except OSError:
            continue  # uma unidade que não responde não entra na estimativa
    return total


def empty_recycle_bin(report: Report) -> Outcome:
    drives = _fixed_drives()
    items = 0
    bytes_freed = 0
    failures: list[str] = []
    rows: list[Row] = []
    for done, drive in enumerate(drives):
        report(Step("cleanup.recycle_bin.step", done, len(drives), {"drive": drive}))
        try:
            drive_items, drive_bytes = _query(drive)
            if drive_items:
                _empty(drive)
        except OSError:
            failures.append(drive)
            continue
        rows.append(Row("category.recycle_bin", drive_items, drive_bytes, {"drive": drive}))
        items += drive_items
        bytes_freed += drive_bytes
    return Outcome(items, bytes_freed, tuple(failures), rows=tuple(rows))
