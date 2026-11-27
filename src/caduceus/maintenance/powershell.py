"""
PowerShell

Corre um script do Windows PowerShell e devolve o que ele escreve (em UTF-8), para as
funcionalidades que leem dados que só o PowerShell dá (as tarefas agendadas, as aplicações da
Store). O script vai codificado em base64, por isso não há problemas de aspas nem de
caracteres.
"""

import base64
import os
import subprocess

from caduceus.config import POWERSHELL_TIMEOUT_SECONDS

POWERSHELL_FROM_SYSTEM32 = r"WindowsPowerShell\v1.0\powershell.exe"
_UTF8_OUTPUT = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"


def run_powershell(script: str) -> str | None:
    """O que o script escreveu, ou None se o PowerShell não existe, demorou demais ou falhou."""
    encoded = base64.b64encode((_UTF8_OUTPUT + script).encode("utf-16-le")).decode("ascii")
    executable = os.path.join(os.path.expandvars(r"%WINDIR%\System32"), POWERSHELL_FROM_SYSTEM32)
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=POWERSHELL_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")
