"""
Limpar os componentes do Windows

Corre o comando oficial do Windows, `DISM /Online /Cleanup-Image /StartComponentCleanup`, que
remove da pasta WinSxS os componentes de atualizações antigas. Nunca usa `/ResetBase`, por isso
continua a ser possível desinstalar atualizações. O DISM não diz o que apagou, e o espaço libertado
mede-se pela diferença de espaço livre no disco do sistema. Apaga também os registos e a cache de
análises do Windows Defender (`Support` e `Scans\\History\\CacheManager`, em `%PROGRAMDATA%`), que
ele volta a criar, sem tocar na quarentena. Exige administrador.
"""

import os

from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.free_space.cleaner import Location, clean_locations
from caduceus.maintenance.system_tool import free_bytes, run_system_tool

_SUCCESS_CODES = (0, 3010)  # 3010: concluído, falta reiniciar
_COMPONENT_STORE = r"%WINDIR%\WinSxS"
# Registos e cache de análises do Windows Defender: ele volta a criá-los. A quarentena não se toca
_DEFENDER = r"%PROGRAMDATA%\Microsoft\Windows Defender"
DEFENDER_LOCATIONS = (
    Location(_DEFENDER + r"\Support", "category.defender_cache", needs_admin=True),
    Location(
        _DEFENDER + r"\Scans\History\CacheManager", "category.defender_cache", needs_admin=True
    ),
)


def _clean_component_store(report: Report) -> Outcome:
    store = os.path.expandvars(_COMPONENT_STORE)
    try:
        free_before = free_bytes()
        succeeded = run_system_tool(
            "dism.exe",
            ["/Online", "/Cleanup-Image", "/StartComponentCleanup"],
            report,
            "components.step",
            _SUCCESS_CODES,
            reports_percent=True,
        )
        freed = max(0, free_bytes() - free_before) if succeeded else 0
    except OSError:
        succeeded = False
    if not succeeded:
        return Outcome(0, 0, failures=(store,))
    return Outcome(0, freed, rows=(Row("category.component_store", None, freed, needs_admin=True),))


def clean_components(report: Report) -> Outcome:
    if not is_admin():
        return Outcome(0, 0, admin_required=(os.path.expandvars(_COMPONENT_STORE),))
    defender = clean_locations(DEFENDER_LOCATIONS, report)
    store = _clean_component_store(report)
    return Outcome(
        defender.items,
        defender.bytes_freed + store.bytes_freed,
        failures=store.failures + defender.failures,
        admin_required=defender.admin_required,
        rows=store.rows + defender.rows,
    )
