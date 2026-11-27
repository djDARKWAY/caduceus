"""
Libertar a memória de standby

Esvazia a lista de standby pelo gestor de memória do Windows. Mede a diferença nas páginas
livres e a zeros, porque a memória disponível do Windows já inclui a de standby.
"""

import ctypes
import mmap
from ctypes import wintypes

from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.admin import is_admin

_MEMORY_LIST_INFORMATION = 0x50
_PURGE_STANDBY_LIST = 4
_PROFILE_SINGLE_PROCESS = 13
_ROW_KEY = "performance.free_standby.result"
_FREED_KEY = "performance.free_standby.gain"


class _MemoryLists(ctypes.Structure):
    _fields_ = [
        ("zeroed", ctypes.c_size_t),
        ("free", ctypes.c_size_t),
        ("modified", ctypes.c_size_t),
        ("modified_no_write", ctypes.c_size_t),
        ("bad", ctypes.c_size_t),
        ("standby_by_priority", ctypes.c_size_t * 8),
        ("repurposed_by_priority", ctypes.c_size_t * 8),
        ("modified_page_file", ctypes.c_size_t),
    ]


_ntdll = ctypes.WinDLL("ntdll")
_query_memory_lists = _ntdll.NtQuerySystemInformation
_query_memory_lists.argtypes = [
    wintypes.ULONG,
    ctypes.POINTER(_MemoryLists),
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
_query_memory_lists.restype = wintypes.LONG
_set_memory_list = _ntdll.NtSetSystemInformation
_set_memory_list.argtypes = [wintypes.ULONG, ctypes.POINTER(ctypes.c_int), wintypes.ULONG]
_set_memory_list.restype = wintypes.LONG
_adjust_privilege = _ntdll.RtlAdjustPrivilege
_adjust_privilege.argtypes = [
    wintypes.ULONG,
    ctypes.c_ubyte,
    ctypes.c_ubyte,
    ctypes.POINTER(ctypes.c_ubyte),
]
_adjust_privilege.restype = wintypes.LONG


def _free_memory_bytes() -> int | None:
    lists = _MemoryLists()
    if _query_memory_lists(
        _MEMORY_LIST_INFORMATION, ctypes.byref(lists), ctypes.sizeof(lists), None
    ):
        return None
    return (int(lists.zeroed) + int(lists.free)) * mmap.PAGESIZE


def _purge_standby() -> bool:
    previous = ctypes.c_ubyte()
    if _adjust_privilege(_PROFILE_SINGLE_PROCESS, True, False, ctypes.byref(previous)):
        return False
    try:
        command = ctypes.c_int(_PURGE_STANDBY_LIST)
        status: int = _set_memory_list(
            _MEMORY_LIST_INFORMATION, ctypes.byref(command), ctypes.sizeof(command)
        )
    finally:
        discarded = ctypes.c_ubyte()
        restored: int = _adjust_privilege(
            _PROFILE_SINGLE_PROCESS, previous, False, ctypes.byref(discarded)
        )
    return status == 0 and restored == 0


def free_standby_memory(report: Report) -> Outcome:
    target = "SystemMemoryListInformation"
    if not is_admin():
        return Outcome(0, 0, admin_required=(target,))
    report(Step("performance.free_standby.step", 0, 0))
    before = _free_memory_bytes()
    if before is None or not _purge_standby():
        return Outcome(0, 0, failures=(target,))
    after = _free_memory_bytes()
    if after is None:
        return Outcome(0, 0, failures=(target,))
    gained = max(0, after - before)
    return Outcome(
        0, gained, rows=(Row(_ROW_KEY, None, gained, needs_admin=True),), freed_key=_FREED_KEY
    )
