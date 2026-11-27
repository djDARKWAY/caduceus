"""
Plano de energia

Lê o plano ativo pela API de energia do Windows e aplica os planos predefinidos com `powercfg`.
Se não houver um plano de alto desempenho, tenta duplicar o modelo com um identificador fixo,
para poder reutilizar a cópia das próximas vezes.
"""

import ctypes
from ctypes import wintypes
from uuid import UUID

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.system_tool import run_system_tool

_BALANCED = UUID("381b4222-f694-41f0-9685-ff5bb260df2e")
_HIGH = UUID("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
_HIGH_COPY = UUID("f09943b8-58a0-42d8-9c0c-9076c59b9d61")
_STEP_KEY = "performance.power_plan.step"

_powrprof = ctypes.WinDLL("powrprof")
_get_active_scheme = _powrprof.PowerGetActiveScheme
_get_active_scheme.argtypes = [wintypes.HKEY, ctypes.POINTER(ctypes.c_void_p)]
_get_active_scheme.restype = wintypes.DWORD
_read_friendly_name = _powrprof.PowerReadFriendlyName
_read_friendly_name.argtypes = [
    wintypes.HKEY,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_read_friendly_name.restype = wintypes.DWORD
_local_free = ctypes.WinDLL("kernel32").LocalFree
_local_free.argtypes = [wintypes.HLOCAL]
_local_free.restype = wintypes.HLOCAL


def _active_scheme() -> UUID | None:
    pointer = ctypes.c_void_p()
    if _get_active_scheme(None, ctypes.byref(pointer)) or pointer.value is None:
        return None
    try:
        return UUID(bytes_le=ctypes.string_at(pointer, 16))
    finally:
        _local_free(pointer)


def _scheme_name(scheme: UUID) -> str | None:
    guid = ctypes.create_string_buffer(scheme.bytes_le)
    size = wintypes.DWORD()
    if _read_friendly_name(None, guid, None, None, None, ctypes.byref(size)) or not size.value:
        return None
    name = ctypes.create_unicode_buffer(size.value // ctypes.sizeof(ctypes.c_wchar))
    if _read_friendly_name(None, guid, None, None, name, ctypes.byref(size)):
        return None
    return name.value


def active_plan_name() -> str | None:
    active = _active_scheme()
    if active == _BALANCED:
        return "performance.power_plan.balanced"
    if active in (_HIGH, _HIGH_COPY):
        return "performance.power_plan.high"
    return _scheme_name(active) if active is not None else None


def balanced_is_active() -> bool:
    return _active_scheme() == _BALANCED


def high_performance_is_active() -> bool:
    return _active_scheme() in (_HIGH, _HIGH_COPY)


def _activate(scheme: UUID, report: Report) -> bool:
    return run_system_tool("powercfg.exe", ["/setactive", str(scheme)], report, _STEP_KEY)


def set_balanced(report: Report) -> Outcome:
    try:
        succeeded = _activate(_BALANCED, report)
    except OSError:
        succeeded = False
    return Outcome(0, 0, failures=() if succeeded else ("powercfg.exe",))


def _activate_high(report: Report) -> bool:
    if _scheme_name(_HIGH) is not None:
        return _activate(_HIGH, report)
    if _scheme_name(_HIGH_COPY) is None:
        run_system_tool(
            "powercfg.exe", ["/duplicatescheme", str(_HIGH), str(_HIGH_COPY)], report, _STEP_KEY
        )
        # A cópia pode ter sido criada por outra instância entretanto.
    return _activate(_HIGH_COPY, report)


def set_high_performance(report: Report) -> Outcome:
    try:
        succeeded = _activate_high(report)
    except OSError:
        succeeded = False
    return Outcome(0, 0, failures=() if succeeded else ("powercfg.exe",))
