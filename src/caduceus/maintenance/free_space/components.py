"""
Limpar os componentes do Windows

Corre o comando oficial do Windows, `DISM /Online /Cleanup-Image /StartComponentCleanup`, que
remove da pasta WinSxS os componentes de atualizações antigas. Nunca usa `/ResetBase`, por isso
continua a ser possível desinstalar atualizações. O DISM não diz o que apagou, e o espaço libertado
mede-se pela diferença de espaço livre no disco do sistema. Exige administrador.
"""

import os

from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.system_tool import free_bytes, run_system_tool

_SUCCESS_CODES = (0, 3010)  # 3010: concluído, falta reiniciar
_COMPONENT_STORE = r"%WINDIR%\WinSxS"


def clean_components(report: Report) -> Outcome:
    store = os.path.expandvars(_COMPONENT_STORE)
    if not is_admin():
        return Outcome(0, 0, admin_required=(store,))
    try:
        free_before = free_bytes()
        succeeded = run_system_tool(
            "dism.exe",
            ["/Online", "/Cleanup-Image", "/StartComponentCleanup"],
            report,
            "cleanup.components.step",
            _SUCCESS_CODES,
            reports_percent=True,
        )
        freed = max(0, free_bytes() - free_before) if succeeded else 0
    except OSError:
        succeeded = False
    if not succeeded:
        return Outcome(0, 0, failures=(store,))
    return Outcome(0, freed, rows=(Row("category.component_store", None, freed, needs_admin=True),))
