"""
Memória dos processos

Lê, só em leitura, a memória que cada programa em execução está a usar (o conjunto de trabalho, em
bytes), somada por ficheiro executável: um programa com vários processos (um navegador, o Discord)
conta como um só. Os processos que o Windows não deixa inspecionar ficam de fora.
"""

import ctypes
import os
from ctypes import wintypes

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MAX_PROCESSES = 4096
_MAX_PATH_CHARS = 32768


class _MemoryCounters(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("page_fault_count", wintypes.DWORD),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
    )


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_enum_processes = _kernel32.K32EnumProcesses
_enum_processes.argtypes = [
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
_enum_processes.restype = wintypes.BOOL
_open_process = _kernel32.OpenProcess
_open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_open_process.restype = wintypes.HANDLE
_close_handle = _kernel32.CloseHandle
_close_handle.argtypes = [wintypes.HANDLE]
_close_handle.restype = wintypes.BOOL
_image_name = _kernel32.QueryFullProcessImageNameW
_image_name.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_image_name.restype = wintypes.BOOL
_memory_info = _kernel32.K32GetProcessMemoryInfo
_memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MemoryCounters), wintypes.DWORD]
_memory_info.restype = wintypes.BOOL


def _process_ids() -> list[int]:
    ids = (wintypes.DWORD * _MAX_PROCESSES)()
    returned = wintypes.DWORD()
    if not _enum_processes(ids, ctypes.sizeof(ids), ctypes.byref(returned)):
        return []
    return list(ids[: returned.value // ctypes.sizeof(wintypes.DWORD)])


def _executable_and_memory(process_id: int) -> tuple[str, int] | None:
    handle = _open_process(_PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return None
    try:
        path = ctypes.create_unicode_buffer(_MAX_PATH_CHARS)
        length = wintypes.DWORD(_MAX_PATH_CHARS)
        counters = _MemoryCounters(cb=ctypes.sizeof(_MemoryCounters))
        if not _image_name(handle, 0, path, ctypes.byref(length)):
            return None
        if not _memory_info(handle, ctypes.byref(counters), counters.cb):
            return None
        return os.path.normcase(path.value), counters.working_set_size
    finally:
        _close_handle(handle)


def memory_by_executable() -> dict[str, int]:
    """Bytes de memória em uso, por caminho do executável (em minúsculas e com `\\`)."""
    totals: dict[str, int] = {}
    for process_id in _process_ids():
        found = _executable_and_memory(process_id)
        if found is not None:
            path, size = found
            totals[path] = totals.get(path, 0) + size
    return totals
