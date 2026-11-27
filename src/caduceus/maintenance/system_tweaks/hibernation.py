r"""
Hibernação

Liga ou desliga a hibernação com o comando oficial do Windows (`powercfg /hibernate on|off`),
conforme o estado atual (lido do registo, sem administrador). Desligar apaga o ficheiro
`C:\hiberfil.sys` (cerca de 40% da memória RAM) e desliga também o arranque rápido; ligar volta a
reservar esse espaço. Não é uma limpeza de disco, é um ajuste do sistema. O espaço libertado ao
desligar mede-se pela diferença de espaço livre no disco do sistema. Exige administrador.
"""

import winreg

from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.system_tool import free_bytes, run_system_tool, system_drive

_POWER_KEY = r"SYSTEM\CurrentControlSet\Control\Power"
_HIBERNATION_VALUE = "HibernateEnabled"


def is_hibernation_on() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _POWER_KEY) as key:
            return bool(winreg.QueryValueEx(key, _HIBERNATION_VALUE)[0])
    except OSError:
        return False  # sem o valor, o Windows não tem a hibernação ligada


def toggle_hibernation(report: Report) -> Outcome:
    hibernation_file = system_drive() + r"\hiberfil.sys"
    if not is_admin():
        return Outcome(0, 0, admin_required=(hibernation_file,))
    turning_off = is_hibernation_on()
    free_before = free_bytes()
    try:
        succeeded = run_system_tool(
            "powercfg.exe",
            ["/hibernate", "off" if turning_off else "on"],
            report,
            "hibernation.step",
        )
    except OSError:
        succeeded = False
    if not succeeded:
        return Outcome(0, 0, failures=(hibernation_file,))
    if not turning_off:
        return Outcome(0, 0, rows=(Row("category.hibernation_on", None, 0, needs_admin=True),))
    freed = max(0, free_bytes() - free_before)
    return Outcome(
        0, freed, rows=(Row("category.hibernation_file", None, freed, needs_admin=True),)
    )
