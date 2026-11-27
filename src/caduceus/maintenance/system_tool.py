"""
Ferramentas do sistema

Corre uma ferramenta de linha de comandos ou gráfica do Windows (`dism`, `vssadmin`, `powercfg`,
`cleanmgr`) sem janela congelada: enquanto ela corre, anuncia o passo em curso, com a percentagem
que a ferramenta escreve (se escrever alguma) ou como trabalho em curso (se não). A ferramenta corre
num grupo de processos próprio, por isso o Ctrl+C não lhe chega e não a interrompe a meio. Mede
também o espaço livre no disco do sistema, que é como estas ações dizem quanto libertaram.
"""

import os
import re
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from typing import IO

from caduceus.maintenance.actions import Report, Step

_SYSTEM_FOLDER = r"%WINDIR%\System32"
_SYSTEM_DRIVE = "%SystemDrive%"
_PERCENT = re.compile(rb"(?<!\d)(\d{1,3})(?:[.,]\d{1,2})?%")
_READ_SIZE = 256
_POLL_SECONDS = 0.1
_PERCENT_TAIL_SIZE = 7  # até seis caracteres da percentagem, mais o carácter anterior
_NO_CONTROLS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW


def system_drive() -> str:
    """O disco do sistema, sem a barra final (por exemplo, `C:`)."""
    return os.path.expandvars(_SYSTEM_DRIVE)


def free_bytes() -> int:
    return shutil.disk_usage(system_drive() + "\\").free


def parse_percent(output: bytes) -> int | None:
    """A última percentagem que a ferramenta escreveu, se houver."""
    matches = _PERCENT.findall(output)
    return min(int(matches[-1]), 100) if matches else None


def _report_percentages(
    output: IO[bytes], report: Report, step_key: str, values: Mapping[str, str]
) -> None:
    tail = b""
    while chunk := output.read(_READ_SIZE):
        data = tail + chunk
        if b"%" in chunk:
            percent = parse_percent(data)
            if percent is not None:
                report(Step(step_key, percent, 100, values))
        # O símbolo de percentagem pode chegar numa leitura posterior aos algarismos.
        tail = data.rsplit(b"%", 1)[-1][-_PERCENT_TAIL_SIZE:]


def run_system_tool(
    executable: str,
    arguments: Sequence[str],
    report: Report,
    step_key: str,
    success_codes: Sequence[int] = (0,),
    *,
    reports_percent: bool = False,
    values: Mapping[str, str] | None = None,
) -> bool:
    """Corre `executable` (da pasta System32, ou com caminho completo) e devolve se terminou com um
    código de sucesso. Os `values` completam o texto do passo."""
    step_values = values or {}
    command = [os.path.join(os.path.expandvars(_SYSTEM_FOLDER), executable), *arguments]
    report(Step(step_key, 0, 0, step_values))
    with subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if reports_percent else subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        bufsize=0,  # sem memória intermédia, a leitura devolve já o que a ferramenta escreveu
        creationflags=_NO_CONTROLS,
    ) as process:
        if process.stdout is not None:
            _report_percentages(process.stdout, report, step_key, step_values)
        while process.poll() is None:
            # Sem percentagem para mostrar, a barra de trabalho em curso continua a animar-se
            report(Step(step_key, 0, 0, step_values))
            time.sleep(_POLL_SECONDS)
        return process.wait() in success_codes
