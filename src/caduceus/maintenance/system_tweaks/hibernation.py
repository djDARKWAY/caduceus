r"""
Desligar a hibernação

Desliga a hibernação com o comando oficial do Windows, `powercfg /hibernate off`, o que apaga o
ficheiro `C:\hiberfil.sys` (cerca de 40% da memória RAM) e desliga também o arranque rápido. Não é
uma limpeza de disco, é um ajuste do sistema. O espaço libertado mede-se pela diferença de espaço
livre no disco do sistema. Exige administrador.
"""

from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.system_tool import free_bytes, run_system_tool, system_drive


def turn_off_hibernation(report: Report) -> Outcome:
    hibernation_file = system_drive() + r"\hiberfil.sys"
    if not is_admin():
        return Outcome(0, 0, admin_required=(hibernation_file,))
    free_before = free_bytes()
    try:
        succeeded = run_system_tool(
            "powercfg.exe", ["/hibernate", "off"], report, "hibernation.step"
        )
    except OSError:
        succeeded = False
    if not succeeded:
        return Outcome(0, 0, failures=(hibernation_file,))
    freed = max(0, free_bytes() - free_before)
    return Outcome(
        0, freed, rows=(Row("category.hibernation_file", None, freed, needs_admin=True),)
    )
