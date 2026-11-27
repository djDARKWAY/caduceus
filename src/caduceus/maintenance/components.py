"""
Limpar os componentes do Windows

Corre o comando oficial do Windows, `DISM /Online /Cleanup-Image /StartComponentCleanup`, que
remove da pasta WinSxS os componentes de atualizações antigas. Nunca usa `/ResetBase`, por isso
continua a ser possível desinstalar atualizações. O DISM não diz o que apagou, e o espaço libertado
mede-se pela diferença de espaço livre no disco do sistema. Exige administrador.
"""

import os
import re
import shutil
import subprocess

from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.admin import is_admin

_PERCENT = re.compile(rb"(\d{1,3})(?:\.\d)?%")
_SUCCESS_CODES = (0, 3010)  # 3010: concluído, falta reiniciar
_READ_SIZE = 256
_COMPONENT_STORE = r"%WINDIR%\WinSxS"
_DISM = r"%WINDIR%\System32\dism.exe"
# Grupo de processos próprio: o Ctrl+C não chega ao DISM, que não deve ser interrompido a meio
_NO_CONTROLS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW


def parse_percent(output: bytes) -> int | None:
    """A última percentagem que o DISM escreveu, se houver."""
    matches = _PERCENT.findall(output)
    return int(matches[-1]) if matches else None


def _run_dism(report: Report) -> bool:
    process = subprocess.Popen(
        [os.path.expandvars(_DISM), "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        creationflags=_NO_CONTROLS,
    )
    output = process.stdout
    while output is not None and (chunk := output.read(_READ_SIZE)):
        percent = parse_percent(chunk)
        if percent is not None:
            report(Step("components.step", min(percent, 100), 100))
    return process.wait() in _SUCCESS_CODES


def clean_components(report: Report) -> Outcome:
    store = os.path.expandvars(_COMPONENT_STORE)
    if not is_admin():
        return Outcome(0, 0, admin_required=(store,))
    drive = os.path.expandvars("%SystemDrive%\\")
    free_before = shutil.disk_usage(drive).free
    report(Step("components.step", 0, 0))
    try:
        succeeded = _run_dism(report)
    except OSError:
        return Outcome(0, 0, failures=(store,))
    if not succeeded:
        return Outcome(0, 0, failures=(store,))
    freed = max(0, shutil.disk_usage(drive).free - free_before)
    return Outcome(0, freed, rows=(Row("category.component_store", None, freed, needs_admin=True),))
